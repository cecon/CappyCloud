using Microsoft.CodeAnalysis;

namespace Cappy.RoslynExtractor;

internal static class TypeFacts
{
    private static readonly HashSet<SpecialType> PrimitiveSpecialTypes =
    [
        SpecialType.System_Boolean,
        SpecialType.System_Byte,
        SpecialType.System_Char,
        SpecialType.System_DateTime,
        SpecialType.System_Decimal,
        SpecialType.System_Double,
        SpecialType.System_Int16,
        SpecialType.System_Int32,
        SpecialType.System_Int64,
        SpecialType.System_Object,
        SpecialType.System_SByte,
        SpecialType.System_Single,
        SpecialType.System_String,
        SpecialType.System_UInt16,
        SpecialType.System_UInt32,
        SpecialType.System_UInt64,
        SpecialType.System_Void,
    ];

    public static bool IsPrimitive(ITypeSymbol? type)
    {
        return type is null || PrimitiveSpecialTypes.Contains(type.SpecialType);
    }

    public static bool IsGraphType(ITypeSymbol? type)
    {
        return type is INamedTypeSymbol named
            && !IsPrimitive(named)
            && !named.IsGenericType
            && named.TypeKind is TypeKind.Class or TypeKind.Interface or TypeKind.Struct or TypeKind.Enum;
    }

    public static bool IsDbContext(ITypeSymbol? type)
    {
        var current = type;
        while (current is not null)
        {
            var fullName = current.ToDisplayString(SymbolDisplayFormat.FullyQualifiedFormat);
            if (current.Name.EndsWith("DbContext", StringComparison.Ordinal))
            {
                return true;
            }
            if (
                current.Name == "DbContext"
                && (
                    fullName.Contains("EntityFramework", StringComparison.OrdinalIgnoreCase)
                    || fullName.Contains("System.Data.Entity", StringComparison.OrdinalIgnoreCase)
                )
            )
            {
                return true;
            }
            current = current.BaseType;
        }
        return false;
    }

    public static bool IsModelBuilder(ITypeSymbol? type)
    {
        var current = type;
        while (current is not null)
        {
            var fullName = current.ToDisplayString(SymbolDisplayFormat.FullyQualifiedFormat);
            if (current.Name is "ModelBuilder" or "DbModelBuilder")
            {
                return true;
            }
            current = current.BaseType;
        }
        return false;
    }

    public static bool TryGetDbSetEntityType(ITypeSymbol? type, out INamedTypeSymbol entityType)
    {
        entityType = null!;
        if (type is not INamedTypeSymbol named)
        {
            return false;
        }

        if (IsDbSetNamedType(named) && TryGetConcreteTypeArgument(named, out entityType))
        {
            return true;
        }

        foreach (var iface in named.AllInterfaces)
        {
            if (
                IsDbSetNamedType(iface)
                && TryGetConcreteTypeArgument(iface, out entityType)
            )
            {
                return true;
            }
        }
        return false;
    }

    public static bool TryUnwrapEnumerableEntityType(ITypeSymbol? type, out INamedTypeSymbol entityType)
    {
        entityType = null!;
        if (TryGetConcreteEntityType(type, out entityType))
        {
            return true;
        }

        if (type is not INamedTypeSymbol named || type.SpecialType == SpecialType.System_String)
        {
            return false;
        }

        if (IsEnumerableNamedType(named) && TryGetConcreteTypeArgument(named, out entityType))
        {
            return true;
        }

        foreach (var iface in named.AllInterfaces)
        {
            if (
                IsEnumerableNamedType(iface)
                && TryGetConcreteTypeArgument(iface, out entityType)
            )
            {
                return true;
            }
        }
        return false;
    }

    public static bool TryGetConcreteEntityType(ITypeSymbol? type, out INamedTypeSymbol entityType)
    {
        entityType = null!;
        if (
            type is not INamedTypeSymbol named
            || string.IsNullOrWhiteSpace(named.Name)
            || IsPrimitive(named)
            || named.IsGenericType
            || named.IsAnonymousType
            || named.TypeKind is TypeKind.TypeParameter or TypeKind.Error
        )
        {
            return false;
        }
        entityType = named;
        return true;
    }

    public static bool TryGetEfConfigurationEntityType(
        INamedTypeSymbol? configuration,
        out INamedTypeSymbol entityType
    )
    {
        entityType = null!;
        if (configuration is null)
        {
            return false;
        }

        foreach (var iface in configuration.AllInterfaces)
        {
            if (
                iface.Name == "IEntityTypeConfiguration"
                && iface.TypeArguments.Length == 1
                && TryGetConcreteEntityType(iface.TypeArguments[0], out entityType)
            )
            {
                return true;
            }
        }

        var current = configuration.BaseType;
        while (current is not null)
        {
            if (
                current.Name == "EntityTypeConfiguration"
                && current.TypeArguments.Length == 1
                && TryGetConcreteEntityType(current.TypeArguments[0], out entityType)
            )
            {
                return true;
            }
            current = current.BaseType;
        }
        return false;
    }

    private static bool TryGetConcreteTypeArgument(
        INamedTypeSymbol named,
        out INamedTypeSymbol entityType
    )
    {
        entityType = null!;
        if (
            named.TypeArguments.Length != 1
            || !TryGetConcreteEntityType(named.TypeArguments[0], out entityType)
        )
        {
            return false;
        }
        return true;
    }

    private static bool IsDbSetNamedType(INamedTypeSymbol named)
    {
        return named.Name is "DbSet" or "IDbSet" && named.TypeArguments.Length == 1;
    }

    private static bool IsEnumerableNamedType(INamedTypeSymbol named)
    {
        return named.Name is "IEnumerable" or "IReadOnlyCollection" or "ICollection" or "List"
            && named.TypeArguments.Length == 1;
    }

    public static string Accessibility(ISymbol symbol)
    {
        return symbol.DeclaredAccessibility switch
        {
            Microsoft.CodeAnalysis.Accessibility.Public => "public",
            Microsoft.CodeAnalysis.Accessibility.Private => "private",
            Microsoft.CodeAnalysis.Accessibility.Protected => "protected",
            Microsoft.CodeAnalysis.Accessibility.Internal => "internal",
            Microsoft.CodeAnalysis.Accessibility.ProtectedAndInternal => "protected_internal",
            Microsoft.CodeAnalysis.Accessibility.ProtectedOrInternal => "private_protected",
            _ => "not_applicable",
        };
    }
}
