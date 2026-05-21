"""Pydantic schemas for lightweight repository graph exploration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RepositoryGraphStats(BaseModel):
    files: int = 0
    code_files: int = 0
    modules: int = 0
    links: int = 0
    isolated: int = 0
    symbols: int = 0
    entrypoints: int = 0
    unreferenced_files: int = 0
    ui_actions: int = 0
    flows: int = 0


class RepositoryGraphNode(BaseModel):
    id: str
    label: str
    type: str
    path: str = ""
    file_count: int = 0
    import_count: int = 0
    imported_by_count: int = 0
    isolated: bool = False


class RepositoryGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    weight: int = 1


class RepositoryGraphFinding(BaseModel):
    id: str
    type: str
    severity: str = "low"
    title: str
    detail: str
    node_id: str
    path: str = ""


class RepositoryGraphFile(BaseModel):
    id: str
    path: str
    label: str
    module: str = "root"
    extension: str = ""
    line_count: int = 0
    symbol_count: int = 0
    imports: list[str] = Field(default_factory=list)
    imported_by: list[str] = Field(default_factory=list)
    import_count: int = 0
    imported_by_count: int = 0
    isolated: bool = False
    entrypoint: bool = False
    unreferenced: bool = False
    symbols: list[str] = Field(default_factory=list)


class RepositoryGraphSymbol(BaseModel):
    id: str
    name: str
    kind: str
    file_path: str
    line: int = 0
    signature: str = ""
    exported: bool = False
    container: str = ""
    element: str = ""
    handler: str = ""


class RepositoryGraphSemanticNode(BaseModel):
    id: str
    label: str
    type: str
    path: str = ""
    line: int = 0
    detail: str = ""


class RepositoryGraphOut(BaseModel):
    slug: str
    repo_path: str
    generated_at: str
    stats: RepositoryGraphStats = Field(default_factory=RepositoryGraphStats)
    nodes: list[RepositoryGraphNode] = Field(default_factory=list)
    edges: list[RepositoryGraphEdge] = Field(default_factory=list)
    files: list[RepositoryGraphFile] = Field(default_factory=list)
    symbols: list[RepositoryGraphSymbol] = Field(default_factory=list)
    file_edges: list[RepositoryGraphEdge] = Field(default_factory=list)
    semantic_nodes: list[RepositoryGraphSemanticNode] = Field(default_factory=list)
    semantic_edges: list[RepositoryGraphEdge] = Field(default_factory=list)
    findings: list[RepositoryGraphFinding] = Field(default_factory=list)
