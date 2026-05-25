using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Linq.Expressions;
using Demo.Domain;

namespace Microsoft.EntityFrameworkCore
{
    public class DatabaseFacade
    {
        public void EnsureCreated() { }
    }

    public class DbContext
    {
        public DatabaseFacade Database { get; } = new();
        public DbSet<TEntity> Set<TEntity>() where TEntity : class => new();
        public int SaveChanges() => 0;
        public object Entry(object entity) => entity;
        public void Add(object entity) { }
        public void AddRange(object entities) { }
    }

    public class DbSet<TEntity> : IQueryable<TEntity>
    {
        public Type ElementType => typeof(TEntity);
        public Expression Expression => throw new NotImplementedException();
        public IQueryProvider Provider => throw new NotImplementedException();
        public IEnumerator<TEntity> GetEnumerator() => throw new NotImplementedException();
        IEnumerator IEnumerable.GetEnumerator() => GetEnumerator();
        public void Add(TEntity entity) { }
    }

    public interface IDbSet<TEntity> : IQueryable<TEntity>
    {
    }
}

namespace Demo.Data
{
    public sealed class EFContext : Microsoft.EntityFrameworkCore.DbContext
    {
        public Microsoft.EntityFrameworkCore.DbSet<User> Users { get; } = new();
        public Microsoft.EntityFrameworkCore.DbSet<Order> Orders { get; } = new();
        public Microsoft.EntityFrameworkCore.IDbSet<Product> Products { get; } = default!;
        public string Connection { get; } = "";
    }
}
