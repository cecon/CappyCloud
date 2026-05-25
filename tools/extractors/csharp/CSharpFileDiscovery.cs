namespace Cappy.RoslynExtractor;

internal static class CSharpFileDiscovery
{
    private static readonly string[] SkipDirs =
    [
        ".git",
        ".vs",
        "bin",
        "obj",
        "node_modules",
        "packages",
    ];

    public static IReadOnlyList<string> FindFiles(string repoPath, IReadOnlySet<string>? scopedPaths)
    {
        if (scopedPaths is { Count: > 0 })
        {
            var repoRoot = Path.GetFullPath(repoPath).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            return scopedPaths
                .Select(path => Path.GetFullPath(Path.Combine(repoPath, path.Replace('/', Path.DirectorySeparatorChar))))
                .Where(path => path.StartsWith(repoRoot, StringComparison.OrdinalIgnoreCase))
                .Where(File.Exists)
                .Where(path => path.EndsWith(".cs", StringComparison.OrdinalIgnoreCase))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
                .ToList();
        }

        return Directory
            .EnumerateFiles(repoPath, "*.cs", SearchOption.AllDirectories)
            .Where(path => !HasSkippedSegment(repoPath, path))
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private static bool HasSkippedSegment(string repoPath, string file)
    {
        var relative = Path.GetRelativePath(repoPath, file)
            .Replace('\\', '/')
            .Split('/', StringSplitOptions.RemoveEmptyEntries);
        return relative.Any(part => SkipDirs.Contains(part, StringComparer.OrdinalIgnoreCase));
    }
}
