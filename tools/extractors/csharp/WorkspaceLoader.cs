using Microsoft.Build.Locator;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.MSBuild;

namespace Cappy.RoslynExtractor;

internal sealed record LoadedDocument(string RelativePath, SyntaxTree Tree, SemanticModel Model);

internal sealed record LoadedWorkspace(IReadOnlyList<LoadedDocument> Documents);

internal static class WorkspaceLoader
{
    public static async Task<LoadedWorkspace> LoadAsync(
        string repoPath,
        IReadOnlyList<string> files,
        List<ExtractorDiagnostic> diagnostics
    )
    {
        var scoped = files.ToHashSet(StringComparer.OrdinalIgnoreCase);
        try
        {
            RegisterMsBuild(diagnostics);
            var loaded = await LoadFromMsBuildAsync(repoPath, scoped, diagnostics);
            if (loaded.Count > 0)
            {
                return new LoadedWorkspace(loaded);
            }
        }
        catch (Exception exc) when (exc is not OperationCanceledException)
        {
            diagnostics.Add(new ExtractorDiagnostic
            {
                Level = "warning",
                Phase = "workspace",
                Message = $"MSBuild workspace load failed; falling back to standalone parse: {exc.Message}",
            });
        }

        return new LoadedWorkspace(await LoadStandaloneAsync(repoPath, files, diagnostics));
    }

    private static async Task<List<LoadedDocument>> LoadFromMsBuildAsync(
        string repoPath,
        HashSet<string> scoped,
        List<ExtractorDiagnostic> diagnostics
    )
    {
        using var workspace = MSBuildWorkspace.Create();
        workspace.WorkspaceFailed += (_, args) =>
            diagnostics.Add(new ExtractorDiagnostic
            {
                Level = args.Diagnostic.Kind == WorkspaceDiagnosticKind.Failure ? "error" : "warning",
                Phase = "workspace",
                Message = args.Diagnostic.Message,
            });

        var solutions = Directory
            .EnumerateFiles(repoPath, "*.sln", SearchOption.TopDirectoryOnly)
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .ToList();
        if (solutions.Count > 0)
        {
            var solution = await workspace.OpenSolutionAsync(solutions[0]);
            return await LoadDocumentsAsync(repoPath, solution.Projects, scoped, diagnostics);
        }

        var projects = Directory
            .EnumerateFiles(repoPath, "*.csproj", SearchOption.AllDirectories)
            .Where(path => !path.Contains($"{Path.DirectorySeparatorChar}obj{Path.DirectorySeparatorChar}"))
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .ToList();
        if (projects.Count == 0)
        {
            return [];
        }

        var loadedProjects = new List<Project>();
        foreach (var projectPath in projects)
        {
            try
            {
                loadedProjects.Add(await workspace.OpenProjectAsync(projectPath));
            }
            catch (Exception exc) when (exc is not OperationCanceledException)
            {
                diagnostics.Add(new ExtractorDiagnostic
                {
                    Level = "warning",
                    Phase = "workspace",
                    File = CliOptions.NormalizePath(Path.GetRelativePath(repoPath, projectPath)),
                    Message = $"Could not load project: {exc.Message}",
                });
            }
        }
        return await LoadDocumentsAsync(repoPath, loadedProjects, scoped, diagnostics);
    }

    private static async Task<List<LoadedDocument>> LoadDocumentsAsync(
        string repoPath,
        IEnumerable<Project> projects,
        HashSet<string> scoped,
        List<ExtractorDiagnostic> diagnostics
    )
    {
        var result = new List<LoadedDocument>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var project in projects)
        {
            var compilation = await project.GetCompilationAsync();
            if (compilation is null)
            {
                continue;
            }

            foreach (var document in project.Documents)
            {
                if (document.FilePath is null || !scoped.Contains(document.FilePath) || !seen.Add(document.FilePath))
                {
                    continue;
                }
                var tree = await document.GetSyntaxTreeAsync();
                if (tree is null)
                {
                    continue;
                }
                RecordParseDiagnostics(repoPath, tree, diagnostics);
                result.Add(new LoadedDocument(Relative(repoPath, document.FilePath), tree, compilation.GetSemanticModel(tree)));
            }
        }
        return result;
    }

    private static async Task<List<LoadedDocument>> LoadStandaloneAsync(
        string repoPath,
        IReadOnlyList<string> files,
        List<ExtractorDiagnostic> diagnostics
    )
    {
        var trees = new List<SyntaxTree>();
        foreach (var file in files)
        {
            var text = await File.ReadAllTextAsync(file);
            var tree = CSharpSyntaxTree.ParseText(text, path: file);
            trees.Add(tree);
            RecordParseDiagnostics(repoPath, tree, diagnostics);
        }

        var compilation = CSharpCompilation.Create(
            "CappyStandalone",
            trees,
            AppDomain.CurrentDomain.GetAssemblies()
                .Where(assembly => !assembly.IsDynamic && !string.IsNullOrWhiteSpace(assembly.Location))
                .Select(assembly => MetadataReference.CreateFromFile(assembly.Location)),
            new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary)
        );
        return trees
            .Select(tree => new LoadedDocument(Relative(repoPath, tree.FilePath), tree, compilation.GetSemanticModel(tree)))
            .ToList();
    }

    private static void RegisterMsBuild(List<ExtractorDiagnostic> diagnostics)
    {
        if (MSBuildLocator.IsRegistered)
        {
            return;
        }
        try
        {
            MSBuildLocator.RegisterDefaults();
        }
        catch (Exception exc)
        {
            diagnostics.Add(new ExtractorDiagnostic
            {
                Level = "warning",
                Phase = "workspace",
                Message = $"MSBuild registration failed: {exc.Message}",
            });
        }
    }

    private static void RecordParseDiagnostics(string repoPath, SyntaxTree tree, List<ExtractorDiagnostic> diagnostics)
    {
        foreach (var diagnostic in tree.GetDiagnostics().Where(item => item.Severity == DiagnosticSeverity.Error))
        {
            var span = diagnostic.Location.GetLineSpan();
            diagnostics.Add(new ExtractorDiagnostic
            {
                Level = "error",
                Phase = "parse",
                File = Relative(repoPath, tree.FilePath),
                Line = span.StartLinePosition.Line + 1,
                Message = diagnostic.GetMessage(),
            });
        }
    }

    private static string Relative(string repoPath, string file)
    {
        return CliOptions.NormalizePath(Path.GetRelativePath(repoPath, file));
    }
}
