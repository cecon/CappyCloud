using Microsoft.CodeAnalysis;

namespace Cappy.RoslynExtractor;

internal sealed record EfTableMapping(
    INamedTypeSymbol EntityType,
    string TableName,
    string? Schema,
    SyntaxNode Evidence,
    string MappingSource,
    string? ConfigurationClass = null,
    Dictionary<string, object?>? ExtraAttrs = null
)
{
    public string TargetExternal => string.IsNullOrWhiteSpace(Schema)
        ? $"table:{TableName}"
        : $"table:{Schema}.{TableName}";
}
