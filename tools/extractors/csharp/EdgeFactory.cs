namespace Cappy.RoslynExtractor;

internal static class EdgeFactory
{
    public static GraphEdge Local(
        string source,
        string target,
        string type,
        string file,
        Microsoft.CodeAnalysis.SyntaxNode evidenceNode,
        string confidence = "high"
    )
    {
        var evidence = SourceFacts.Evidence(evidenceNode);
        return new GraphEdge
        {
            Id = $"roslyn:{source}->{target}:{type}",
            Source = source,
            Target = target,
            Type = type,
            Evidence = new EdgeEvidence
            {
                File = file,
                LineStart = evidence.Start,
                LineEnd = evidence.End,
                Snippet = evidence.Snippet,
            },
            Confidence = confidence,
        };
    }

    public static GraphEdge External(
        string source,
        string targetExternal,
        string type,
        string file,
        Microsoft.CodeAnalysis.SyntaxNode evidenceNode,
        string confidence,
        Dictionary<string, object?>? attrs = null
    )
    {
        var evidence = SourceFacts.Evidence(evidenceNode);
        return new GraphEdge
        {
            Id = $"roslyn:{source}->{targetExternal}:{type}",
            Source = source,
            TargetExternal = targetExternal,
            Type = type,
            Evidence = new EdgeEvidence
            {
                File = file,
                LineStart = evidence.Start,
                LineEnd = evidence.End,
                Snippet = evidence.Snippet,
            },
            Confidence = confidence,
            Attrs = attrs ?? [],
        };
    }
}
