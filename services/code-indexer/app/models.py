from typing import Optional
from pydantic import BaseModel


class IndexRequest(BaseModel):
    user_id: str
    container_id: str
    workspace_path: str = "/workspace/main"
    force: bool = False


class SemanticSearchRequest(BaseModel):
    user_id: str
    query: str
    limit: int = 10
    language: Optional[str] = None


class SymbolSearchRequest(BaseModel):
    user_id: str
    symbol: str
    symbol_type: str = "all"  # all | function | class | method


class ReferencesRequest(BaseModel):
    user_id: str
    symbol: str
    file_path: Optional[str] = None


class CallGraphRequest(BaseModel):
    user_id: str
    function: str
    depth: int = 3
