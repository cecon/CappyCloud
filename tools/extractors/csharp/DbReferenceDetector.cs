using System.Text.RegularExpressions;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace Cappy.RoslynExtractor;

internal static partial class DbReferenceDetector
{
    // DbContext infrastructure members describe EF plumbing, not domain entities.
    private static readonly HashSet<string> InfrastructureMembers = new(StringComparer.Ordinal)
    {
        "SaveChanges",
        "SaveChangesAsync",
        "Database",
        "ChangeTracker",
        "Model",
        "DisposeAsync",
        "Dispose",
        "OnConfiguring",
        "OnModelCreating",
        "Entry",
        "Entries",
        "Attach",
        "AttachRange",
        "Detach",
        "Find",
        "FindAsync",
        "Update",
        "UpdateRange",
    };

    private static readonly HashSet<string> EntityArgumentMethods = new(StringComparer.Ordinal)
    {
        "Add",
        "AddAsync",
        "AddRange",
        "AddRangeAsync",
        "Remove",
        "RemoveRange",
    };

    private static readonly HashSet<string> RangeMethods = new(StringComparer.Ordinal)
    {
        "AddRange",
        "AddRangeAsync",
        "RemoveRange",
    };

    public static IEnumerable<DbReference> Detect(
        SemanticModel model,
        SyntaxNode methodNode,
        string relative,
        List<ExtractorDiagnostic> diagnostics
    )
    {
        var references = new List<DbReference>();
        DetectDbSetProperties(model, methodNode, relative, diagnostics, references);
        DetectEfInvocations(model, methodNode, relative, diagnostics, references);
        DetectSqlLiterals(methodNode, references);
        return references.OrderBy(item => item.Evidence.SpanStart);
    }

    private static void DetectDbSetProperties(
        SemanticModel model,
        SyntaxNode methodNode,
        string relative,
        List<ExtractorDiagnostic> diagnostics,
        List<DbReference> references
    )
    {
        foreach (var memberAccess in methodNode.DescendantNodes().OfType<MemberAccessExpressionSyntax>())
        {
            var ownerType = model.GetTypeInfo(memberAccess.Expression).Type;
            if (!TypeFacts.IsDbContext(ownerType))
            {
                continue;
            }

            var memberName = memberAccess.Name.Identifier.ValueText;
            if (InfrastructureMembers.Contains(memberName))
            {
                continue;
            }

            if (model.GetSymbolInfo(memberAccess).Symbol is not IPropertySymbol property)
            {
                continue;
            }

            if (TypeFacts.TryGetDbSetEntityType(property.Type, out var entityType))
            {
                references.Add(new DbReference(entityType.Name, memberAccess));
                continue;
            }

            if (property.Type is INamedTypeSymbol { Name: "DbSet" or "IDbSet" } dbSetType)
            {
                AddDiagnostic(
                    diagnostics,
                    relative,
                    memberAccess,
                    "ef_dbset_unresolved_generic",
                    $"Could not resolve DbSet entity type for {memberName}: {dbSetType}."
                );
            }
        }
    }

    private static void DetectEfInvocations(
        SemanticModel model,
        SyntaxNode methodNode,
        string relative,
        List<ExtractorDiagnostic> diagnostics,
        List<DbReference> references
    )
    {
        foreach (var invocation in methodNode.DescendantNodes().OfType<InvocationExpressionSyntax>())
        {
            if (invocation.Expression is not MemberAccessExpressionSyntax memberAccess)
            {
                continue;
            }

            var receiverType = model.GetTypeInfo(memberAccess.Expression).Type;
            var receiverIsDbContext = TypeFacts.IsDbContext(receiverType);
            var receiverIsDbSet = TypeFacts.TryGetDbSetEntityType(receiverType, out _);
            if (!receiverIsDbContext && !receiverIsDbSet)
            {
                continue;
            }

            var methodName = memberAccess.Name.Identifier.ValueText;
            if (InfrastructureMembers.Contains(methodName))
            {
                continue;
            }

            if (methodName == "Set" && receiverIsDbContext)
            {
                DetectSetInvocation(model, invocation, relative, diagnostics, references);
                continue;
            }

            if (EntityArgumentMethods.Contains(methodName))
            {
                DetectEntityArgumentInvocation(
                    model,
                    invocation,
                    methodName,
                    relative,
                    diagnostics,
                    references
                );
            }
        }
    }

    private static void DetectSetInvocation(
        SemanticModel model,
        InvocationExpressionSyntax invocation,
        string relative,
        List<ExtractorDiagnostic> diagnostics,
        List<DbReference> references
    )
    {
        var typeArguments = TypeArguments(invocation);
        if (
            typeArguments.Count == 1
            && TypeFacts.TryGetConcreteEntityType(model.GetTypeInfo(typeArguments[0]).Type, out var entityType)
        )
        {
            references.Add(new DbReference(entityType.Name, invocation));
            return;
        }

        AddDiagnostic(
            diagnostics,
            relative,
            invocation,
            "ef_set_unresolved_generic",
            $"Could not resolve concrete entity type for {invocation}."
        );
    }

    private static void DetectEntityArgumentInvocation(
        SemanticModel model,
        InvocationExpressionSyntax invocation,
        string methodName,
        string relative,
        List<ExtractorDiagnostic> diagnostics,
        List<DbReference> references
    )
    {
        var argument = invocation.ArgumentList.Arguments.FirstOrDefault()?.Expression;
        if (argument is null || argument.IsKind(SyntaxKind.NullLiteralExpression))
        {
            AddDiagnostic(diagnostics, relative, invocation, "ef_argument_untyped", $"Untyped EF argument in {invocation}.");
            return;
        }

        var argumentType = model.GetTypeInfo(argument).Type;
        var resolved = RangeMethods.Contains(methodName)
            ? TypeFacts.TryUnwrapEnumerableEntityType(argumentType, out var entityType)
            : TypeFacts.TryGetConcreteEntityType(argumentType, out entityType);
        if (resolved)
        {
            references.Add(new DbReference(entityType.Name, invocation));
            return;
        }

        var code = argumentType is null ? "ef_argument_untyped" : "ef_argument_ambiguous";
        AddDiagnostic(
            diagnostics,
            relative,
            invocation,
            code,
            $"Could not resolve EF entity argument for {invocation}."
        );
    }

    private static void DetectSqlLiterals(SyntaxNode methodNode, List<DbReference> references)
    {
        foreach (var literal in methodNode.DescendantNodes().OfType<LiteralExpressionSyntax>())
        {
            var value = literal.Token.ValueText;
            if (!SqlVerbRegex().IsMatch(value))
            {
                continue;
            }
            foreach (var table in ExtractSqlNames(value))
            {
                references.Add(new DbReference(table, literal));
            }
        }
    }

    private static SeparatedSyntaxList<TypeSyntax> TypeArguments(InvocationExpressionSyntax invocation)
    {
        return invocation.Expression switch
        {
            MemberAccessExpressionSyntax { Name: GenericNameSyntax generic } => generic.TypeArgumentList.Arguments,
            GenericNameSyntax generic => generic.TypeArgumentList.Arguments,
            _ => default,
        };
    }

    private static IEnumerable<string> ExtractSqlNames(string sql)
    {
        foreach (Match match in SqlTableRegex().Matches(sql))
        {
            var name = match.Groups["name"].Value.Trim().Trim('[', ']', '"', '`');
            if (!string.IsNullOrWhiteSpace(name))
            {
                yield return name;
            }
        }
    }

    private static void AddDiagnostic(
        List<ExtractorDiagnostic> diagnostics,
        string relative,
        SyntaxNode syntax,
        string code,
        string message
    )
    {
        var evidence = SourceFacts.Evidence(syntax);
        diagnostics.Add(new ExtractorDiagnostic
        {
            Code = code,
            Level = "info",
            Phase = "ef",
            File = relative,
            Line = evidence.Start,
            Message = message,
        });
    }

    [GeneratedRegex(@"\b(SELECT|INSERT|UPDATE|DELETE|FROM|JOIN)\b", RegexOptions.IgnoreCase)]
    private static partial Regex SqlVerbRegex();

    [GeneratedRegex(
        @"\b(?:FROM|JOIN|INTO|UPDATE)\s+(?<name>[A-Za-z_][\w\.\[\]""`]+)",
        RegexOptions.IgnoreCase
    )]
    private static partial Regex SqlTableRegex();
}

internal sealed record DbReference(string Name, SyntaxNode Evidence);
