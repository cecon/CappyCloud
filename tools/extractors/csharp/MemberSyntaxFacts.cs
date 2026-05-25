using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace Cappy.RoslynExtractor;

internal static class MemberSyntaxFacts
{
    public static IMethodSymbol? MethodSymbol(SemanticModel model, SyntaxNode node)
    {
        return node switch
        {
            MethodDeclarationSyntax item => model.GetDeclaredSymbol(item) as IMethodSymbol,
            ConstructorDeclarationSyntax item => model.GetDeclaredSymbol(item) as IMethodSymbol,
            DestructorDeclarationSyntax item => model.GetDeclaredSymbol(item) as IMethodSymbol,
            OperatorDeclarationSyntax item => model.GetDeclaredSymbol(item) as IMethodSymbol,
            ConversionOperatorDeclarationSyntax item => model.GetDeclaredSymbol(item) as IMethodSymbol,
            LocalFunctionStatementSyntax item => model.GetDeclaredSymbol(item) as IMethodSymbol,
            _ => null,
        };
    }

    public static IEnumerable<SyntaxNode> MethodNodes(SyntaxNode root)
    {
        return root.DescendantNodes().Where(node =>
            node is MethodDeclarationSyntax
                or ConstructorDeclarationSyntax
                or DestructorDeclarationSyntax
                or OperatorDeclarationSyntax
                or ConversionOperatorDeclarationSyntax
                or LocalFunctionStatementSyntax
        );
    }

    public static IEnumerable<(ISymbol Symbol, SyntaxNode Node)> MemberSymbols(
        SemanticModel model,
        MemberDeclarationSyntax member
    )
    {
        switch (member)
        {
            case MethodDeclarationSyntax node when model.GetDeclaredSymbol(node) is { } symbol:
                yield return (symbol, node);
                break;
            case ConstructorDeclarationSyntax node when model.GetDeclaredSymbol(node) is { } symbol:
                yield return (symbol, node);
                break;
            case DestructorDeclarationSyntax node when model.GetDeclaredSymbol(node) is { } symbol:
                yield return (symbol, node);
                break;
            case OperatorDeclarationSyntax node when model.GetDeclaredSymbol(node) is { } symbol:
                yield return (symbol, node);
                break;
            case ConversionOperatorDeclarationSyntax node when model.GetDeclaredSymbol(node) is { } symbol:
                yield return (symbol, node);
                break;
            case PropertyDeclarationSyntax node when model.GetDeclaredSymbol(node) is { } symbol:
                yield return (symbol, node);
                break;
            case EventDeclarationSyntax node when model.GetDeclaredSymbol(node) is { } symbol:
                yield return (symbol, node);
                break;
            case FieldDeclarationSyntax node:
                foreach (var variable in node.Declaration.Variables)
                {
                    if (model.GetDeclaredSymbol(variable) is { } symbol)
                    {
                        yield return (symbol, variable);
                    }
                }
                break;
            case EventFieldDeclarationSyntax node:
                foreach (var variable in node.Declaration.Variables)
                {
                    if (model.GetDeclaredSymbol(variable) is { } symbol)
                    {
                        yield return (symbol, variable);
                    }
                }
                break;
        }
    }
}
