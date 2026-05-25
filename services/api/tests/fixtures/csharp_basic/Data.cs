using System.Collections.Generic;
using Demo.Domain;

namespace Microsoft.EntityFrameworkCore
{
    public class DbContext
    {
    }
}

namespace Demo.Data
{
    public sealed class SellerContext : Microsoft.EntityFrameworkCore.DbContext
    {
        public List<User> Users { get; } = new();
    }
}
