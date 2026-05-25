using Microsoft.EntityFrameworkCore;
using System.Data.Entity.ModelConfiguration;

namespace Demo.Mapping;

public interface IEntityConfiguration
{
}

public sealed class EntityDConfiguration : IEntityTypeConfiguration<EntityD>
{
    public void Configure(EntityTypeBuilder<EntityD> builder)
    {
        builder.ToTable("PhysicalD");
    }
}

public sealed class EntityEConfiguration : EntityTypeConfiguration<EntityE>
{
    public EntityEConfiguration()
    {
        this.ToTable("PhysicalE");
    }
}

public sealed class EntityGMapping : IEntityConfiguration
{
    public EntityGMapping(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<EntityG>(builder =>
        {
            builder.ToTable("PhysicalG");
        });
    }
}
