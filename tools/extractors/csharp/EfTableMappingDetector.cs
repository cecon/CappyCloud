using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace Cappy.RoslynExtractor;

internal static partial class EfTableMappingDetector
{
    public static IEnumerable<EfTableMapping> Detect(
        SemanticModel model,
        SyntaxNode root,
        string relative,
        List<ExtractorDiagnostic> diagnostics
    )
    {
        var mappings = new List<EfTableMapping>();
        DetectDataAnnotations(model, root, relative, diagnostics, mappings);
        DetectOnModelCreating(model, root, relative, diagnostics, mappings);
        DetectEntityTypeConfigurations(model, root, relative, diagnostics, mappings);
        DetectCustomModelBuilderConfigurations(model, root, relative, diagnostics, mappings);
        return mappings.OrderBy(item => item.Evidence.SpanStart);
    }

    private static void DetectDataAnnotations(
        SemanticModel model,
        SyntaxNode root,
        string relative,
        List<ExtractorDiagnostic> diagnostics,
        List<EfTableMapping> mappings
    )
    {
        foreach (var classNode in root.DescendantNodes().OfType<ClassDeclarationSyntax>())
        {
            if (model.GetDeclaredSymbol(classNode) is not INamedTypeSymbol entity)
            {
                continue;
            }
            foreach (var attribute in classNode.AttributeLists.SelectMany(list => list.Attributes))
            {
                if (!IsTableAttribute(model, attribute))
                {
                    continue;
                }
                if (!TryReadTableName(attribute, out var tableName, out var schema))
                {
                    AddDiagnostic(
                        diagnostics,
                        relative,
                        attribute,
                        "ef_table_attr_non_literal",
                        $"Could not resolve literal table name for {entity.Name}."
                    );
                    continue;
                }
                mappings.Add(new EfTableMapping(
                    entity,
                    tableName,
                    schema,
                    attribute,
                    "data_annotation",
                    null,
                    new Dictionary<string, object?> { ["entity_inferred"] = true }
                ));
            }
        }
    }

    private static void DetectOnModelCreating(
        SemanticModel model,
        SyntaxNode root,
        string relative,
        List<ExtractorDiagnostic> diagnostics,
        List<EfTableMapping> mappings
    )
    {
        foreach (var method in root.DescendantNodes().OfType<MethodDeclarationSyntax>())
        {
            if (method.Identifier.ValueText != "OnModelCreating" || !HasModelBuilderParameter(model, method))
            {
                continue;
            }
            var localEntities = LocalEntityBuilders(model, method, relative, diagnostics);
            foreach (var invocation in method.DescendantNodes().OfType<InvocationExpressionSyntax>())
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
                    "fluent_on_model_creating"
                ));
            }
        }
    }

    private static void DetectEntityTypeConfigurations(
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
                || !TypeFacts.TryGetEfConfigurationEntityType(configuration, out var entity)
            )
            {
                continue;
            }
            foreach (var invocation in ConfigurationToTableInvocations(classNode))
            {
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
                mappings.Add(new EfTableMapping(
                    entity,
                    tableName,
                    schema,
                    invocation,
                    "entity_type_configuration",
                    SymbolIds.ForSymbol(configuration)
                ));
            }
        }
    }

    private static bool HasModelBuilderParameter(SemanticModel model, BaseMethodDeclarationSyntax method)
    {
        return method.ParameterList.Parameters.Any(parameter =>
            TypeFacts.IsModelBuilder(model.GetTypeInfo(parameter.Type!).Type)
        );
    }

    private static Dictionary<ISymbol, INamedTypeSymbol> LocalEntityBuilders(
        SemanticModel model,
        SyntaxNode scope,
        string relative,
        List<ExtractorDiagnostic> diagnostics
    )
    {
        var entities = new Dictionary<ISymbol, INamedTypeSymbol>(SymbolEqualityComparer.Default);
        foreach (var variable in scope.DescendantNodes().OfType<VariableDeclaratorSyntax>())
        {
            if (
                variable.Initializer?.Value is not { } initializer
                || !TryResolveEntityInvocation(model, initializer, out var entity)
            )
            {
                continue;
            }
            if (model.GetDeclaredSymbol(variable) is { } local)
            {
                entities[local] = entity;
            }
            else
            {
                AddDiagnostic(
                    diagnostics,
                    relative,
                    variable,
                    "ef_fluent_unresolved_generic",
                    $"Could not resolve local entity builder for {variable.Identifier.ValueText}."
                );
            }
        }
        AddLambdaEntityBuilders(model, scope, entities);
        return entities;
    }

    private static bool TryResolveEntityForToTable(
        SemanticModel model,
        InvocationExpressionSyntax toTable,
        Dictionary<ISymbol, INamedTypeSymbol> localEntities,
        out INamedTypeSymbol entity
    )
    {
        entity = null!;
        if (toTable.Expression is not MemberAccessExpressionSyntax memberAccess)
        {
            return false;
        }
        return TryResolveBuilderExpression(model, memberAccess.Expression, localEntities, out entity);
    }

    private static bool TryResolveBuilderExpression(
        SemanticModel model,
        ExpressionSyntax expression,
        Dictionary<ISymbol, INamedTypeSymbol> localEntities,
        out INamedTypeSymbol entity
    )
    {
        entity = null!;
        if (expression is InvocationExpressionSyntax invocation)
        {
            return TryResolveEntityInvocation(model, invocation, out entity)
                || (
                    invocation.Expression is MemberAccessExpressionSyntax member
                    && TryResolveBuilderExpression(model, member.Expression, localEntities, out entity)
                );
        }
        if (expression is MemberAccessExpressionSyntax memberAccess)
        {
            return TryResolveBuilderExpression(model, memberAccess.Expression, localEntities, out entity);
        }
        if (expression is IdentifierNameSyntax identifier)
        {
            var symbol = model.GetSymbolInfo(identifier).Symbol;
            if (symbol is null || !localEntities.TryGetValue(symbol, out var resolved))
            {
                return false;
            }
            entity = resolved;
            return true;
        }
        return false;
    }

    private static bool TryResolveEntityInvocation(
        SemanticModel model,
        SyntaxNode expression,
        out INamedTypeSymbol entity
    )
    {
        entity = null!;
        if (
            expression is not InvocationExpressionSyntax invocation
            || invocation.Expression is not MemberAccessExpressionSyntax memberAccess
            || memberAccess.Name.Identifier.ValueText != "Entity"
            || !TypeFacts.IsModelBuilder(model.GetTypeInfo(memberAccess.Expression).Type)
        )
        {
            return false;
        }
        if (memberAccess.Name is GenericNameSyntax generic && generic.TypeArgumentList.Arguments.Count == 1)
        {
            return TypeFacts.TryGetConcreteEntityType(
                model.GetTypeInfo(generic.TypeArgumentList.Arguments[0]).Type,
                out entity
            );
        }
        if (invocation.ArgumentList.Arguments.FirstOrDefault()?.Expression is TypeOfExpressionSyntax typeOf)
        {
            return TypeFacts.TryGetConcreteEntityType(model.GetTypeInfo(typeOf.Type).Type, out entity);
        }
        return false;
    }

}
