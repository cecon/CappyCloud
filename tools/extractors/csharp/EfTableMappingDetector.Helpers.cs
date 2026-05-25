using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace Cappy.RoslynExtractor;

internal static partial class EfTableMappingDetector
{
    private static void DetectCustomModelBuilderConfigurations(
        SemanticModel model,
        SyntaxNode root,
        string relative,
        List<ExtractorDiagnostic> diagnostics,
        List<EfTableMapping> mappings
    )
    {
        foreach (var classNode in root.DescendantNodes().OfType<ClassDeclarationSyntax>())
        {
            if (
                model.GetDeclaredSymbol(classNode) is not INamedTypeSymbol configuration
                || !IsCustomConfigurationClass(configuration)
            )
            {
                continue;
            }
            foreach (var constructor in classNode.Members.OfType<ConstructorDeclarationSyntax>())
            {
                if (!HasModelBuilderParameter(model, constructor))
                {
                    continue;
                }
                AddFluentMappingsFromScope(
                    model,
                    constructor,
                    relative,
                    diagnostics,
                    mappings,
                    "entity_type_configuration",
                    SymbolIds.ForSymbol(configuration)
                );
            }
        }
    }

    private static void AddFluentMappingsFromScope(
        SemanticModel model,
        SyntaxNode scope,
        string relative,
        List<ExtractorDiagnostic> diagnostics,
        List<EfTableMapping> mappings,
        string mappingSource,
        string? configurationClass
    )
    {
        var localEntities = LocalEntityBuilders(model, scope, relative, diagnostics);
        foreach (var invocation in scope.DescendantNodes().OfType<InvocationExpressionSyntax>())
        {
            if (!IsToTableInvocation(invocation))
            {
                continue;
            }
            if (!TryReadTableName(invocation, out var tableName, out var schema))
            {
                AddDiagnostic(
                    diagnostics,
                    relative,
                    invocation,
                    "ef_fluent_non_literal_table",
                    $"Could not resolve literal table name for {invocation}."
                );
                continue;
            }
            if (!TryResolveEntityForToTable(model, invocation, localEntities, out var entity))
            {
                AddDiagnostic(
                    diagnostics,
                    relative,
                    invocation,
                    "ef_fluent_unresolved_generic",
                    $"Could not resolve entity type for {invocation}."
                );
                continue;
            }
            mappings.Add(new EfTableMapping(
                entity,
                tableName,
                schema,
                invocation,
                mappingSource,
                configurationClass
            ));
        }
    }

    private static void AddLambdaEntityBuilders(
        SemanticModel model,
        SyntaxNode scope,
        Dictionary<ISymbol, INamedTypeSymbol> entities
    )
    {
        foreach (var invocation in scope.DescendantNodes().OfType<InvocationExpressionSyntax>())
        {
            if (!TryResolveEntityInvocation(model, invocation, out var entity))
            {
                continue;
            }
            foreach (var lambda in invocation.ArgumentList.Arguments
                .Select(arg => arg.Expression)
                .OfType<LambdaExpressionSyntax>())
            {
                var parameter = FirstLambdaParameter(lambda);
                var symbol = parameter is null ? null : model.GetDeclaredSymbol(parameter);
                if (symbol is not null)
                {
                    entities[symbol] = entity;
                }
            }
        }
    }

    private static ParameterSyntax? FirstLambdaParameter(LambdaExpressionSyntax lambda)
    {
        return lambda switch
        {
            SimpleLambdaExpressionSyntax simple => simple.Parameter,
            ParenthesizedLambdaExpressionSyntax parenthesized =>
                parenthesized.ParameterList.Parameters.FirstOrDefault(),
            _ => null,
        };
    }

    private static bool IsCustomConfigurationClass(INamedTypeSymbol symbol)
    {
        return symbol.Name.EndsWith("Mapping", StringComparison.Ordinal)
            || symbol.AllInterfaces.Any(iface => iface.Name == "IEntityConfiguration");
    }

    private static IEnumerable<InvocationExpressionSyntax> ConfigurationToTableInvocations(
        ClassDeclarationSyntax classNode
    )
    {
        var bodies = classNode.Members
            .Where(member => member is MethodDeclarationSyntax { Identifier.ValueText: "Configure" }
                or ConstructorDeclarationSyntax)
            .Cast<SyntaxNode>();
        foreach (var body in bodies)
        {
            foreach (var invocation in body.DescendantNodes().OfType<InvocationExpressionSyntax>())
            {
                if (IsToTableInvocation(invocation))
                {
                    yield return invocation;
                }
            }
        }
    }

    private static bool TryReadTableName(
        SyntaxNode node,
        out string tableName,
        out string? schema
    )
    {
        tableName = "";
        schema = null;
        return node switch
        {
            AttributeSyntax attribute => TryReadAttributeTableName(attribute, out tableName, out schema),
            InvocationExpressionSyntax invocation => TryReadInvocationTableName(invocation, out tableName, out schema),
            _ => false,
        };
    }

    private static bool TryReadAttributeTableName(
        AttributeSyntax attribute,
        out string tableName,
        out string? schema
    )
    {
        tableName = "";
        schema = null;
        var arguments = attribute.ArgumentList?.Arguments;
        if (arguments is null || arguments.Value.Count == 0)
        {
            return false;
        }
        if (!TryStringLiteral(arguments.Value[0].Expression, out tableName))
        {
            return false;
        }
        var schemaArg = arguments.Value.FirstOrDefault(arg =>
            arg.NameEquals?.Name.Identifier.ValueText == "Schema"
            || arg.NameColon?.Name.Identifier.ValueText == "schema"
        );
        if (schemaArg is not null)
        {
            TryStringLiteral(schemaArg.Expression, out schema);
        }
        else if (arguments.Value.Count > 1)
        {
            TryStringLiteral(arguments.Value[1].Expression, out schema);
        }
        return !string.IsNullOrWhiteSpace(tableName);
    }

    private static bool TryReadInvocationTableName(
        InvocationExpressionSyntax invocation,
        out string tableName,
        out string? schema
    )
    {
        tableName = "";
        schema = null;
        if (invocation.ArgumentList.Arguments.Count == 0)
        {
            return false;
        }
        var arguments = invocation.ArgumentList.Arguments;
        if (!TryStringLiteral(arguments[0].Expression, out tableName))
        {
            return false;
        }
        var schemaArg = arguments.FirstOrDefault(arg => arg.NameColon?.Name.Identifier.ValueText == "schema");
        if (schemaArg is not null)
        {
            TryStringLiteral(schemaArg.Expression, out schema);
        }
        else if (arguments.Count > 1)
        {
            TryStringLiteral(arguments[1].Expression, out schema);
        }
        return !string.IsNullOrWhiteSpace(tableName);
    }

    private static bool TryStringLiteral(ExpressionSyntax expression, out string value)
    {
        value = "";
        if (expression is LiteralExpressionSyntax { Token.Value: string literal })
        {
            value = literal;
            return !string.IsNullOrWhiteSpace(value);
        }
        return false;
    }

    private static bool IsTableAttribute(SemanticModel model, AttributeSyntax attribute)
    {
        var symbol = model.GetSymbolInfo(attribute).Symbol as IMethodSymbol;
        var type = symbol?.ContainingType ?? model.GetTypeInfo(attribute).Type as INamedTypeSymbol;
        var fullName = type?.ToDisplayString(SymbolDisplayFormat.FullyQualifiedFormat)
            .Replace("global::", "", StringComparison.Ordinal);
        return fullName == "System.ComponentModel.DataAnnotations.Schema.TableAttribute";
    }

    private static bool IsToTableInvocation(InvocationExpressionSyntax invocation)
    {
        return invocation.Expression is MemberAccessExpressionSyntax { Name.Identifier.ValueText: "ToTable" };
    }

    private static void AddDiagnostic(
        List<ExtractorDiagnostic> diagnostics,
        string relative,
        SyntaxNode syntax,
        string code,
        string message,
        string level = "info"
    )
    {
        var evidence = SourceFacts.Evidence(syntax);
        diagnostics.Add(new ExtractorDiagnostic
        {
            Code = code,
            Level = level,
            Phase = "ef",
            File = relative,
            Line = evidence.Start,
            Message = message,
        });
    }
}
