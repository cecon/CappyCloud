namespace Cappy.RoslynExtractor;

internal sealed class CSharpGraphExtractor(List<ExtractorDiagnostic> diagnostics)
{
    public async Task<GraphOutput> ExtractAsync(IReadOnlyList<LoadedDocument> documents)
    {
        var state = new ExtractionState();
        var nodeCollector = new NodeCollector(state, diagnostics);
        foreach (var document in documents)
        {
            await nodeCollector.CollectAsync(document);
        }

        var edgeCollector = new EdgeCollector(state, diagnostics);
        foreach (var document in documents)
        {
            await edgeCollector.CollectAsync(document);
        }

        return new GraphOutput
        {
            Nodes = state.Nodes.OrderBy(node => node.Id, StringComparer.Ordinal).ToList(),
            Edges = state.Edges.Values.OrderBy(edge => edge.Id, StringComparer.Ordinal).ToList(),
        };
    }
}
