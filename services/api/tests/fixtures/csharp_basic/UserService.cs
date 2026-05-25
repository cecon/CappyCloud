using System;
using System.Collections.Generic;
using Demo.Data;
using Demo.Domain;

namespace Demo.Services;

public class BaseService
{
    protected void Audit(string message) { }
}

public sealed partial class UserService : BaseService, IUserStore
{
    private readonly SellerContext _context;
    public event EventHandler? Saved;

    public UserService(SellerContext context)
    {
        _context = context;
    }

    /// <exception cref="System.InvalidOperationException">Invalid user.</exception>
    public IEnumerable<User> ListActiveUsers()
    {
        var users = _context.Users;
        var sql = "SELECT Id, Name FROM dbo.Users JOIN dbo.Roles ON dbo.Roles.Id = dbo.Users.Id";
        Audit(sql);
        return users;
    }

    public void Save(User user)
    {
        if (string.IsNullOrWhiteSpace(user.Name))
        {
            throw new InvalidOperationException("Name is required");
        }
        Normalize(user);
        Saved?.Invoke(this, EventArgs.Empty);
    }

    private static void Normalize(User user)
    {
        user.Name = user.Name.Trim();
    }
}
