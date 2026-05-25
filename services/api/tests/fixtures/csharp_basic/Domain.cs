namespace Demo.Domain;

public interface IUserStore
{
    void Save(User user);
}

public abstract class Entity
{
    public int Id { get; protected set; }
}

public sealed class User : Entity
{
    public string Name { get; set; } = "";
    public bool Active { get; set; }
}
