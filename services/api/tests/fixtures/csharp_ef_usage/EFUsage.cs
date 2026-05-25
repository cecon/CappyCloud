using System.Collections.Generic;
using System.Linq;
using Demo.Data;
using Demo.Domain;

namespace Demo.Services;

public sealed class EFUsage
{
    private readonly EFContext ctx = new();

    public IEnumerable<User> UsersTwice()
    {
        var first = ctx.Users;
        var second = ctx.Users;
        return first.Concat(second);
    }

    public void AccessConnection()
    {
        var connection = ctx.Connection;
    }

    public IQueryable<Order> SetOrder()
    {
        return ctx.Set<Order>();
    }

    public void GenericSet<T>()
        where T : class
    {
        var query = ctx.Set<T>();
    }

    public void AddUser(User user)
    {
        ctx.Users.Add(user);
    }

    public void AddOrders(List<Order> orders)
    {
        ctx.AddRange(orders);
    }

    public void Infrastructure(User entity)
    {
        ctx.SaveChanges();
        ctx.Entry(entity);
        ctx.Database.EnsureCreated();
    }

    public void Products()
    {
        var products = ctx.Products;
    }
}
