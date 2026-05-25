using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Serialization;
using Cappy.RoslynExtractor;

var total = Stopwatch.StartNew();
try
{
    var options = CliOptions.Parse(args);
    var output = await RunAsync(options, total);
    Directory.CreateDirectory(Path.GetDirectoryName(options.OutPath) ?? ".");

    var jsonOptions = new JsonSerializerOptions
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        WriteIndented = false,
    };
    await File.WriteAllTextAsync(options.OutPath, JsonSerializer.Serialize(output, jsonOptions));
    Console.WriteLine(
        $"cappy-roslyn-extractor completed nodes={output.Nodes.Count} edges={output.Edges.Count} elapsed_ms={total.ElapsedMilliseconds}"
    );
    return 0;
}
catch (ArgumentException exc)
{
    Console.Error.WriteLine(exc.Message);
    return 1;
}
catch (InvalidOperationException exc)
{
    Console.Error.WriteLine(exc.Message);
    return 1;
}

static async Task<GraphOutput> RunAsync(CliOptions options, Stopwatch total)
{
    if (!Directory.Exists(options.RepoPath))
    {
        throw new ArgumentException($"Repo path not found: {options.RepoPath}");
    }

    var discovery = Stopwatch.StartNew();
    var files = CSharpFileDiscovery.FindFiles(options.RepoPath, options.Paths);
    if (files.Count == 0)
    {
        throw new InvalidOperationException("No .cs files found.");
    }

    var output = new GraphOutput();
    output.TimingsMs["discover"] = discovery.ElapsedMilliseconds;

    var load = Stopwatch.StartNew();
    var workspace = await WorkspaceLoader.LoadAsync(options.RepoPath, files, output.Diagnostics);
    output.TimingsMs["load"] = load.ElapsedMilliseconds;

    var extract = Stopwatch.StartNew();
    var extractor = new CSharpGraphExtractor(output.Diagnostics);
    var graph = await extractor.ExtractAsync(workspace.Documents);
    output.Nodes.AddRange(graph.Nodes);
    output.Edges.AddRange(graph.Edges);
    output.TimingsMs["extract"] = extract.ElapsedMilliseconds;
    output.TimingsMs["total"] = total.ElapsedMilliseconds;
    return output;
}
