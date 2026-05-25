using Microsoft.CodeAnalysis;

namespace Cappy.RoslynExtractor;

internal sealed class ExtractionState
{
    public List<GraphNode> Nodes { get; } = [];
    public Dictionary<string, GraphEdge> Edges { get; } = [];
    public Dictionary<string, string> NodeByQualifiedName { get; } = new(StringComparer.Ordinal);
    public HashSet<string> NodeIds { get; } = new(StringComparer.Ordinal);

    public void AddNode(GraphNode node)
    {
        if (!NodeIds.Add(node.Id))
        {
            return;
        }
        Nodes.Add(node);
        NodeByQualifiedName.TryAdd(node.Name, node.Id);
    }

    public void AddEdge(GraphEdge edge)
    {
        if (edge.Target is null && edge.TargetExternal is null)
        {
            return;
        }
        Edges.TryAdd(edge.Id, edge);
    }

    public string? IdFor(ISymbol? symbol)
    {
        return symbol is null ? null : IdFor(SymbolIds.ForSymbol(symbol));
    }

    public string? IdFor(string qualifiedName)
    {
        return NodeByQualifiedName.GetValueOrDefault(SymbolIds.MakeSafe(qualifiedName));
    }
}
