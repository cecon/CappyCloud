using System;
using System.Linq.Expressions;

namespace System.ComponentModel.DataAnnotations.Schema
{
    [AttributeUsage(AttributeTargets.Class)]
    public sealed class TableAttribute(string name) : Attribute
    {
        public string Name { get; } = name;
        public string? Schema { get; set; }
    }
}

namespace Microsoft.EntityFrameworkCore
{
    public sealed class ModelBuilder
    {
        public EntityTypeBuilder<TEntity> Entity<TEntity>() where TEntity : class => new();
        public EntityTypeBuilder<object> Entity(Type type) => new();
    }

    public sealed class EntityTypeBuilder<TEntity>
        where TEntity : class
    {
        public EntityTypeBuilder<TEntity> HasKey(Expression<Func<TEntity, object>> key) => this;
        public EntityTypeBuilder<TEntity> ToTable(string name) => this;
        public EntityTypeBuilder<TEntity> ToTable(string name, string schema) => this;
    }

    public interface IEntityTypeConfiguration<TEntity>
        where TEntity : class
    {
        void Configure(EntityTypeBuilder<TEntity> builder);
    }
}

namespace System.Data.Entity.ModelConfiguration
{
    public abstract class EntityTypeConfiguration<TEntity>
        where TEntity : class
    {
        public EntityTypeConfiguration<TEntity> ToTable(string name) => this;
        public EntityTypeConfiguration<TEntity> ToTable(string name, string schema) => this;
    }
}
