using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace Cappy.RoslynExtractor;

internal sealed class NodeCollector(ExtractionState state, List<ExtractorDiagnostic> diagnostics)
{
    public async Task CollectAsync(LoadedDocument document)
    {
        var root = await document.Tree.GetRootAsync();
        var relative = document.RelativePath;
        foreach (var namespaceNode in root.DescendantNodes().OfType<BaseNamespaceDeclarationSyntax>())
        {
            AddNamespace(relative, namespaceNode);
        }

        foreach (var typeNode in root.DescendantNodes().OfType<BaseTypeDeclarationSyntax>())
        {
            AddType(relative, document.Model, typeNode);
        }

        foreach (var member in root.DescendantNodes().OfType<MemberDeclarationSyntax>())
        {
            AddMember(relative, document.Model, member);
        }

        foreach (var local in root.DescendantNodes().OfType<LocalFunctionStatementSyntax>())
        {
            AddLocalFunction(relative, document.Model, local);
        }
    }

    private void AddNamespace(string relative, BaseNamespaceDeclarationSyntax node)
    {
        var qualified = SymbolIds.ForNamespace(node.Name.ToString());
        var evidence = SourceFacts.Evidence(node);
        state.AddNode(new GraphNode
        {
            Id = SymbolIds.NodeId(relative, qualified),
            Label = node.Name.ToString(),
            Type = "namespace",
            Name = qualified,
            Path = relative,
            FilePath = relative,
            Line = evidence.Start,
            LineEnd = evidence.End,
            Detail = "C# namespace",
            Attrs = new Dictionary<string, object?>
            {
                ["accessibility"] = "not_applicable",
                ["is_static"] = false,
                ["is_abstract"] = false,
                ["is_sealed"] = false,
                ["is_partial"] = false,
                ["kind_detail"] = "namespace",
            },
        });
    }

    private void AddType(string relative, SemanticModel model, BaseTypeDeclarationSyntax node)
    {
        var symbol = model.GetDeclaredSymbol(node);
        if (symbol is null)
        {
            diagnostics.Add(DiagnosticFor(relative, node, "Could not resolve type declaration."));
            return;
        }

        var kind = NodeKind(node, symbol);
        AddNode(relative, node, symbol, kind, kind);
    }

    private void AddMember(string relative, SemanticModel model, MemberDeclarationSyntax member)
    {
        switch (member)
        {
            case MethodDeclarationSyntax node:
                AddMethod(relative, model.GetDeclaredSymbol(node), node, "regular");
                break;
            case ConstructorDeclarationSyntax node:
                AddMethod(relative, model.GetDeclaredSymbol(node), node, "constructor");
                break;
            case DestructorDeclarationSyntax node:
                AddMethod(relative, model.GetDeclaredSymbol(node), node, "destructor");
                break;
            case OperatorDeclarationSyntax node:
                AddMethod(relative, model.GetDeclaredSymbol(node), node, "operator");
                break;
            case ConversionOperatorDeclarationSyntax node:
                AddMethod(relative, model.GetDeclaredSymbol(node), node, "operator");
                break;
            case PropertyDeclarationSyntax node:
                AddNode(relative, node, model.GetDeclaredSymbol(node), "property", "property");
                break;
            case EventDeclarationSyntax node:
                AddNode(relative, node, model.GetDeclaredSymbol(node), "event", "event");
                break;
            case FieldDeclarationSyntax node:
                foreach (var variable in node.Declaration.Variables)
                {
                    AddNode(relative, variable, model.GetDeclaredSymbol(variable), "field", "field");
                }
                break;
            case EventFieldDeclarationSyntax node:
                foreach (var variable in node.Declaration.Variables)
                {
                    AddNode(relative, variable, model.GetDeclaredSymbol(variable), "event", "event");
                }
                break;
        }
    }

    private void AddLocalFunction(string relative, SemanticModel model, LocalFunctionStatementSyntax node)
    {
        AddMethod(relative, model.GetDeclaredSymbol(node), node, "local");
    }

    private void AddMethod(string relative, ISymbol? symbol, SyntaxNode node, string detail)
    {
        AddNode(relative, node, symbol, "method", detail);
    }

    private void AddNode(
        string relative,
        SyntaxNode syntax,
        ISymbol? symbol,
        string kind,
        string kindDetail
    )
    {
        if (symbol is null)
        {
            diagnostics.Add(DiagnosticFor(relative, syntax, $"Could not resolve {kind} declaration."));
            return;
        }

        var qualified = SymbolIds.ForSymbol(symbol);
        var evidence = SourceFacts.Evidence(syntax);
        state.AddNode(new GraphNode
        {
            Id = SymbolIds.NodeId(relative, qualified),
            Label = symbol.Name,
            Type = kind,
            Name = qualified,
            Path = relative,
            FilePath = relative,
            Line = evidence.Start,
            LineEnd = evidence.End,
            Detail = $"C# {kind}",
            Attrs = Attributes(symbol, syntax, kindDetail),
        });
    }

    private static Dictionary<string, object?> Attributes(ISymbol symbol, SyntaxNode syntax, string kindDetail)
    {
        return new Dictionary<string, object?>
        {
            ["accessibility"] = TypeFacts.Accessibility(symbol),
            ["is_static"] = symbol.IsStatic,
            ["is_abstract"] = symbol.IsAbstract,
            ["is_sealed"] = symbol.IsSealed,
            ["is_partial"] = IsPartial(syntax),
            ["kind_detail"] = kindDetail,
        };
    }

    private static string NodeKind(BaseTypeDeclarationSyntax node, INamedTypeSymbol symbol)
    {
        if (node is RecordDeclarationSyntax recordNode)
        {
            return recordNode.ClassOrStructKeyword.IsKind(SyntaxKind.StructKeyword) ? "record" : "record";
        }
        return symbol.TypeKind switch
        {
            TypeKind.Class => "class",
            TypeKind.Interface => "interface",
            TypeKind.Struct => "struct",
            TypeKind.Enum => "enum",
            _ => "class",
        };
    }

    private static bool IsPartial(SyntaxNode syntax)
    {
        return syntax switch
        {
            TypeDeclarationSyntax node => node.Modifiers.Any(SyntaxKind.PartialKeyword),
            BaseMethodDeclarationSyntax node => node.Modifiers.Any(SyntaxKind.PartialKeyword),
            PropertyDeclarationSyntax node => node.Modifiers.Any(SyntaxKind.PartialKeyword),
            _ => false,
        };
    }

    private static ExtractorDiagnostic DiagnosticFor(string relative, SyntaxNode syntax, string message)
    {
        var evidence = SourceFacts.Evidence(syntax);
        return new ExtractorDiagnostic
        {
            Level = "warning",
            Phase = "semantic",
            File = relative,
            Line = evidence.Start,
            Message = message,
        };
    }
}
