namespace Cappy.RoslynExtractor;

internal sealed record CliOptions(string RepoPath, string OutPath, IReadOnlySet<string>? Paths)
{
    public static CliOptions Parse(string[] args)
    {
        var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        for (var index = 0; index < args.Length; index++)
        {
            var key = args[index];
            if (!key.StartsWith("--", StringComparison.Ordinal))
            {
                throw new ArgumentException($"Unexpected argument: {key}");
            }
            if (index + 1 >= args.Length)
            {
                throw new ArgumentException($"Missing value for {key}");
            }
            values[key] = args[++index];
        }

        if (!values.TryGetValue("--repo", out var repoPath) || string.IsNullOrWhiteSpace(repoPath))
        {
            throw new ArgumentException("--repo is required");
        }
        if (!values.TryGetValue("--out", out var outPath) || string.IsNullOrWhiteSpace(outPath))
        {
            throw new ArgumentException("--out is required");
        }

        IReadOnlySet<string>? paths = null;
        if (values.TryGetValue("--paths", out var rawPaths) && !string.IsNullOrWhiteSpace(rawPaths))
        {
            paths = rawPaths
                .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Select(NormalizePath)
                .Where(path => path.EndsWith(".cs", StringComparison.OrdinalIgnoreCase))
                .ToHashSet(StringComparer.OrdinalIgnoreCase);
        }

        return new CliOptions(
            Path.GetFullPath(repoPath),
            Path.GetFullPath(outPath),
            paths is { Count: > 0 } ? paths : null
        );
    }

    public static string NormalizePath(string path)
    {
        return path.Replace('\\', '/').TrimStart('/');
    }
}
