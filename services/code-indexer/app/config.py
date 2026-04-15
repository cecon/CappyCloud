from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL + pgvector
    database_url: str = "postgresql://cappy:cappypass@postgres:5432/cappycloud"

    # Neo4j
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "cappyneo4j"

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = 64

    # Chunking
    max_chunk_chars: int = 1500
    chunk_overlap_chars: int = 200

    class Config:
        env_file = ".env"


settings = Settings()
