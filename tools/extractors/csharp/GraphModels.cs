using System.Text.Json.Serialization;

namespace Cappy.RoslynExtractor;

internal sealed record GraphOutput
{
    [JsonPropertyName("source_extractor")]
    public string SourceExtractor { get; init; } = ExtractorConstants.SourceExtractor;

    [JsonPropertyName("extractor_version")]
    public string ExtractorVersion { get; init; } = ExtractorConstants.ExtractorVersion;

    [JsonPropertyName("nodes")]
    public List<GraphNode> Nodes { get; init; } = [];

    [JsonPropertyName("edges")]
    public List<GraphEdge> Edges { get; init; } = [];

    [JsonPropertyName("diagnostics")]
    public List<ExtractorDiagnostic> Diagnostics { get; init; } = [];

    [JsonPropertyName("timings_ms")]
    public Dictionary<string, long> TimingsMs { get; init; } = [];
}

internal sealed record GraphNode
{
    public required string Id { get; init; }
    public required string Label { get; init; }
    public required string Type { get; init; }
    public required string Name { get; init; }
    public required string Path { get; init; }

    [JsonPropertyName("file_path")]
    public required string FilePath { get; init; }

    public int Line { get; init; }

    [JsonPropertyName("line_end")]
    public int LineEnd { get; init; }

    public string Detail { get; init; } = "";

    [JsonPropertyName("source_extractor")]
    public string SourceExtractor { get; init; } = ExtractorConstants.SourceExtractor;

    [JsonPropertyName("extractor_version")]
    public string ExtractorVersion { get; init; } = ExtractorConstants.ExtractorVersion;

    public Dictionary<string, object?> Attrs { get; init; } = [];
}

internal sealed record GraphEdge
{
    public required string Id { get; init; }
    public required string Source { get; init; }
    public string? Target { get; init; }

    [JsonPropertyName("target_external")]
    public string? TargetExternal { get; init; }

    public required string Type { get; init; }
    public int Weight { get; init; } = 1;
    public required EdgeEvidence Evidence { get; init; }
    public string Confidence { get; init; } = "high";

    [JsonPropertyName("source_extractor")]
    public string SourceExtractor { get; init; } = ExtractorConstants.SourceExtractor;

    [JsonPropertyName("extractor_version")]
    public string ExtractorVersion { get; init; } = ExtractorConstants.ExtractorVersion;

    public Dictionary<string, object?> Attrs { get; init; } = [];
}

internal sealed record EdgeEvidence
{
    public required string File { get; init; }

    [JsonPropertyName("line_start")]
    public int LineStart { get; init; }

    [JsonPropertyName("line_end")]
    public int LineEnd { get; init; }

    public string? Snippet { get; init; }
}

internal sealed record ExtractorDiagnostic
{
    public string? Code { get; init; }
    public string Level { get; init; } = "warning";
    public string Phase { get; init; } = "extract";
    public string File { get; init; } = "";
    public int Line { get; init; }
    public required string Message { get; init; }
}
