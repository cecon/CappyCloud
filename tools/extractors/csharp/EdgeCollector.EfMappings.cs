using Microsoft.CodeAnalysis;

namespace Cappy.RoslynExtractor;

internal sealed partial class EdgeCollector
{
    private readonly HashSet<string> efMappingEdgesEmitted = new(StringComparer.Ordinal);
    private readonly Dictionary<string, HashSet<string>> efMappingTargetsByEntity = new(StringComparer.Ordinal);
    private readonly HashSet<string> efMappingConflictReported = new(StringComparer.Ordinal);

    private void AddEfTableMappings(string relative, SemanticModel model, SyntaxNode root)
    {
        foreach (var mapping in EfTableMappingDetector.Detect(model, root, relative, diagnostics))
        {
            var sourceId = state.IdFor(mapping.EntityType);
            if (sourceId is null)
            {
                continue;
            }
            var targetExternal = mapping.TargetExternal;
            TrackMappingConflict(relative, sourceId, mapping);
            if (!efMappingEdgesEmitted.Add($"{sourceId}->{targetExternal}"))
            {
                continue;
            }
            state.AddEdge(
                EdgeFactory.External(
                    sourceId,
                    targetExternal,
                    "maps_to_table",
                    relative,
                    mapping.Evidence,
                    "high",
                    MappingAttrs(mapping)
                )
            );
        }
    }

    private void TrackMappingConflict(
        string relative,
        string sourceId,
        EfTableMapping mapping
    )
    {
        var targets = efMappingTargetsByEntity.GetValueOrDefault(sourceId);
        if (targets is null)
        {
            targets = new HashSet<string>(StringComparer.Ordinal);
            efMappingTargetsByEntity[sourceId] = targets;
        }
        targets.Add(mapping.TargetExternal);
        if (targets.Count <= 1 || !efMappingConflictReported.Add(sourceId))
        {
            return;
        }
        var evidence = SourceFacts.Evidence(mapping.Evidence);
        diagnostics.Add(new ExtractorDiagnostic
        {
            Code = "ef_mapping_conflict",
            Level = "warning",
            Phase = "ef",
            File = relative,
            Line = evidence.Start,
            Message = $"Conflicting EF table mappings declared for {mapping.EntityType.Name}.",
        });
    }

    private static Dictionary<string, object?> MappingAttrs(EfTableMapping mapping)
    {
        var attrs = new Dictionary<string, object?>
        {
            ["mapping_source"] = mapping.MappingSource,
            ["schema"] = mapping.Schema,
        };
        if (!string.IsNullOrWhiteSpace(mapping.ConfigurationClass))
        {
            attrs["configuration_class"] = mapping.ConfigurationClass;
        }
        if (mapping.ExtraAttrs is not null)
        {
            foreach (var attr in mapping.ExtraAttrs)
            {
                attrs[attr.Key] = attr.Value;
            }
        }
        return attrs;
    }
}
