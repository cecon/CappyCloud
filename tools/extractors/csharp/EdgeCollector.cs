using System.Text.RegularExpressions;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace Cappy.RoslynExtractor;

internal sealed partial class EdgeCollector(ExtractionState state, List<ExtractorDiagnostic> diagnostics)
{
    public async Task CollectAsync(LoadedDocument document)
    {
        var root = await document.Tree.GetRootAsync();
        var relative = document.RelativePath;
        AddDefines(relative, document.Model, root);
        AddInheritance(relative, document.Model, root);
        AddEfTableMappings(relative, document.Model, root);
        AddMethodEdges(relative, document.Model, root);
    }

    private void AddDefines(string relative, SemanticModel model, SyntaxNode root)
    {
        foreach (var typeNode in root.DescendantNodes().OfType<BaseTypeDeclarationSyntax>())
        {
            var typeSymbol = model.GetDeclaredSymbol(typeNode);
            var typeId = state.IdFor(typeSymbol);
            if (typeSymbol is null || typeId is null)
            {
                continue;
            }

            var parentId = ParentId(relative, typeSymbol);
            if (parentId is not null)
            {
                state.AddEdge(EdgeFactory.Local(parentId, typeId, "defines", relative, typeNode));
            }
        }

        foreach (var member in root.DescendantNodes().OfType<MemberDeclarationSyntax>())
        {
            foreach (var symbolAndNode in MemberSyntaxFacts.MemberSymbols(model, member))
            {
                var targetId = state.IdFor(symbolAndNode.Symbol);
                var sourceId = state.IdFor(symbolAndNode.Symbol.ContainingType);
                if (sourceId is not null && targetId is not null)
                {
                    state.AddEdge(EdgeFactory.Local(sourceId, targetId, "defines", relative, symbolAndNode.Node));
                }
            }
        }
    }

    private void AddInheritance(string relative, SemanticModel model, SyntaxNode root)
    {
        foreach (var typeNode in root.DescendantNodes().OfType<BaseTypeDeclarationSyntax>())
        {
            var symbol = model.GetDeclaredSymbol(typeNode);
            var sourceId = state.IdFor(symbol);
            if (symbol is null || sourceId is null)
            {
                continue;
            }
            if (symbol.BaseType is not null && symbol.BaseType.SpecialType != SpecialType.System_Object)
            {
                var evidence = typeNode.BaseList is null ? typeNode : (SyntaxNode)typeNode.BaseList;
                AddSymbolEdge(sourceId, symbol.BaseType, "extends", relative, evidence);
            }
            foreach (var iface in symbol.Interfaces)
            {
                var type = symbol.TypeKind == TypeKind.Interface ? "extends" : "implements";
                var evidence = typeNode.BaseList is null ? typeNode : (SyntaxNode)typeNode.BaseList;
                AddSymbolEdge(sourceId, iface, type, relative, evidence);
            }
        }
    }

    private void AddMethodEdges(string relative, SemanticModel model, SyntaxNode root)
    {
        foreach (var methodNode in MemberSyntaxFacts.MethodNodes(root))
        {
            var methodSymbol = MemberSyntaxFacts.MethodSymbol(model, methodNode);
            var sourceId = state.IdFor(methodSymbol);
            if (methodSymbol is null || sourceId is null)
            {
                continue;
            }

            AddCalls(relative, model, methodNode, sourceId);
            AddTypeReferences(relative, model, methodNode, methodSymbol, sourceId);
            AddThrows(relative, model, methodNode, sourceId);
            AddDbReferences(relative, model, methodNode, sourceId);
        }
    }

    private void AddCalls(string relative, SemanticModel model, SyntaxNode methodNode, string sourceId)
    {
        foreach (var invocation in methodNode.DescendantNodes().OfType<InvocationExpressionSyntax>())
        {
            if (model.GetSymbolInfo(invocation).Symbol is not IMethodSymbol target)
            {
                continue;
            }
            if (target.MethodKind is MethodKind.PropertyGet or MethodKind.PropertySet)
            {
                continue;
            }
            AddSymbolEdge(sourceId, target, "calls", relative, invocation);
        }

        foreach (var created in methodNode.DescendantNodes().OfType<ObjectCreationExpressionSyntax>())
        {
            if (model.GetSymbolInfo(created).Symbol is IMethodSymbol target)
            {
                AddSymbolEdge(sourceId, target, "calls", relative, created);
            }
        }
    }

    private void AddTypeReferences(
        string relative,
        SemanticModel model,
        SyntaxNode methodNode,
        IMethodSymbol methodSymbol,
        string sourceId
    )
    {
        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (var parameter in methodSymbol.Parameters)
        {
            AddTypeReference(sourceId, parameter.Type, relative, methodNode, seen);
        }
        AddTypeReference(sourceId, methodSymbol.ReturnType, relative, methodNode, seen);

        foreach (var declaration in methodNode.DescendantNodes().OfType<VariableDeclarationSyntax>())
        {
            var type = model.GetTypeInfo(declaration.Type).Type;
            if (AddTypeReference(sourceId, type, relative, declaration.Type, seen))
            {
                continue;
            }
        }
    }

    private void AddThrows(string relative, SemanticModel model, SyntaxNode methodNode, string sourceId)
    {
        foreach (var throwNode in methodNode.DescendantNodes().OfType<ThrowStatementSyntax>())
        {
            if (throwNode.Expression is ObjectCreationExpressionSyntax creation)
            {
                AddTypeEdge(sourceId, model.GetTypeInfo(creation).Type, "throws", relative, throwNode, "high");
            }
        }

        foreach (var match in ExceptionDocRegex().Matches(methodNode.GetLeadingTrivia().ToFullString()).Cast<Match>())
        {
            var name = match.Groups["name"].Value.Replace("T:", "", StringComparison.Ordinal);
            if (!string.IsNullOrWhiteSpace(name))
            {
                state.AddEdge(EdgeFactory.External(sourceId, $"assembly:xml-doc#{name}", "throws", relative, methodNode, "low"));
            }
        }
    }

    private void AddDbReferences(string relative, SemanticModel model, SyntaxNode methodNode, string sourceId)
    {
        foreach (var reference in DbReferenceDetector
            .Detect(model, methodNode, relative, diagnostics)
            .DistinctBy(item => item.Name))
        {
            state.AddEdge(
                EdgeFactory.External(
                    sourceId,
                    $"ref:{reference.Name}",
                    "references",
                    relative,
                    reference.Evidence,
                    "low",
                    new Dictionary<string, object?> { ["placeholder_kind"] = "db_reference_unresolved" }
                )
            );
        }
    }

    private bool AddTypeReference(
        string sourceId,
        ITypeSymbol? type,
        string relative,
        SyntaxNode evidence,
        HashSet<string> seen
    )
    {
        if (!TypeFacts.IsGraphType(type) || type is not INamedTypeSymbol named)
        {
            return false;
        }
        var key = SymbolIds.ForSymbol(named);
        if (!seen.Add(key))
        {
            return true;
        }
        AddTypeEdge(sourceId, named, "references_type", relative, evidence, "high");
        return true;
    }

    private void AddTypeEdge(
        string sourceId,
        ITypeSymbol? target,
        string type,
        string relative,
        SyntaxNode evidence,
        string confidence
    )
    {
        if (target is not INamedTypeSymbol named)
        {
            return;
        }
        AddSymbolEdge(sourceId, named, type, relative, evidence, confidence);
    }

    private void AddSymbolEdge(
        string sourceId,
        ISymbol target,
        string type,
        string relative,
        SyntaxNode evidence,
        string confidence = "high"
    )
    {
        var targetId = state.IdFor(target);
        if (targetId is not null)
        {
            state.AddEdge(EdgeFactory.Local(sourceId, targetId, type, relative, evidence, confidence));
            return;
        }
        if (target.ContainingAssembly is not null)
        {
            var externalConfidence = type == "calls" ? "medium" : confidence;
            state.AddEdge(
                EdgeFactory.External(
                    sourceId,
                    SymbolIds.External(target),
                    type,
                    relative,
                    evidence,
                    externalConfidence
                )
            );
        }
    }

    private string? ParentId(string relative, INamedTypeSymbol symbol)
    {
        if (symbol.ContainingType is not null)
        {
            return state.IdFor(symbol.ContainingType);
        }
        var namespaceName = symbol.ContainingNamespace?.IsGlobalNamespace == false
            ? SymbolIds.ForNamespace(symbol.ContainingNamespace.ToDisplayString())
            : null;
        return namespaceName is null ? null : state.IdFor(SymbolIds.NodeId(relative, namespaceName)) ?? state.IdFor(namespaceName);
    }

    [GeneratedRegex(@"<exception\s+cref=""(?<name>[^""]+)""", RegexOptions.IgnoreCase)]
    private static partial Regex ExceptionDocRegex();
}
