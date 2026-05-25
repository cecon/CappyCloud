using Microsoft.CodeAnalysis;

namespace Cappy.RoslynExtractor;

internal static class SymbolIds
{
    private static readonly SymbolDisplayFormat FullFormat = new(
        globalNamespaceStyle: SymbolDisplayGlobalNamespaceStyle.Omitted,
        typeQualificationStyle: SymbolDisplayTypeQualificationStyle.NameAndContainingTypesAndNamespaces,
        genericsOptions: SymbolDisplayGenericsOptions.IncludeTypeParameters,
        memberOptions: SymbolDisplayMemberOptions.IncludeContainingType
            | SymbolDisplayMemberOptions.IncludeParameters,
        parameterOptions: SymbolDisplayParameterOptions.IncludeType,
        miscellaneousOptions: SymbolDisplayMiscellaneousOptions.EscapeKeywordIdentifiers
    );

    public static string ForSymbol(ISymbol symbol)
    {
        return MakeSafe(symbol.ToDisplayString(FullFormat));
    }

    public static string ForNamespace(string name)
    {
        return MakeSafe(name);
    }

    public static string NodeId(string relativePath, string qualifiedName)
    {
        return $"roslyn:{relativePath}#{MakeSafe(qualifiedName)}";
    }

    public static string External(ISymbol symbol)
    {
        var assembly = symbol.ContainingAssembly?.Name;
        return $"assembly:{assembly ?? "unknown"}#{ForSymbol(symbol)}";
    }

    public static string MakeSafe(string value)
    {
        return string.IsNullOrWhiteSpace(value)
            ? "unknown"
            : value.Trim().Replace("<", "__").Replace(">", "__");
    }
}
