using System.ComponentModel.DataAnnotations.Schema;

namespace Demo.Mapping;

internal static class TableNames
{
    public const string NotLiteral = "PhysicalConstant";
}

[Table("PhysicalA")]
public sealed class EntityA
{
    public int Id { get; set; }
}

[Table("PhysicalB", Schema = "dbo")]
public sealed class EntityB
{
    public int Id { get; set; }
}

[Table(TableNames.NotLiteral)]
public sealed class EntityWithConstant
{
    public int Id { get; set; }
}

public sealed class EntityC
{
    public int Id { get; set; }
}

public sealed class EntityD
{
    public int Id { get; set; }
}

public sealed class EntityE
{
    public int Id { get; set; }
}

public sealed class EntityG
{
    public int Id { get; set; }
}

[Table("X")]
public sealed class EntityF
{
    public int Id { get; set; }
}
