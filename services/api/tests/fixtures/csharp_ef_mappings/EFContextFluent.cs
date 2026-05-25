using Microsoft.EntityFrameworkCore;

namespace Demo.Mapping;

public sealed class MappingContext
{
    protected void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<EntityA>().ToTable("PhysicalA");
        modelBuilder.Entity<EntityB>().HasKey(item => item.Id).ToTable("PhysicalB", "dbo");
        modelBuilder.Entity<EntityC>();

        var split = modelBuilder.Entity<EntityC>();
        split.HasKey(item => item.Id);
        split.ToTable("PhysicalC");

        modelBuilder.Entity<EntityF>().ToTable("Y");
    }
}
