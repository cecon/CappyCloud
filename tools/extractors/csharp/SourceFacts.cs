using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.Text;

namespace Cappy.RoslynExtractor;

internal static class SourceFacts
{
    public static (int Start, int End, string Snippet) Evidence(SyntaxNode node)
    {
        var span = node.SyntaxTree.GetLineSpan(node.Span);
        var start = span.StartLinePosition.Line + 1;
        var end = span.EndLinePosition.Line + 1;
        return (start, end, Snippet(node));
    }

    public static string Snippet(SyntaxNode node)
    {
        var text = node.ToString().Replace("\r", " ").Replace("\n", " ");
        text = string.Join(" ", text.Split(' ', StringSplitOptions.RemoveEmptyEntries));
        return text.Length <= 240 ? text : text[..240];
    }

    public static int Line(Location location)
    {
        var span = location.GetLineSpan();
        return span.StartLinePosition.Line + 1;
    }

    public static int EndLine(Location location)
    {
        var span = location.GetLineSpan();
        return span.EndLinePosition.Line + 1;
    }

    public static string RelativePath(string repoPath, SyntaxTree tree)
    {
        return CliOptions.NormalizePath(Path.GetRelativePath(repoPath, tree.FilePath));
    }
}
