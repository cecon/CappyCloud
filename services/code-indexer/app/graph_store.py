"""
Persistência do grafo AST no Neo4j.
Nós  : File, Function, Class, Method, Module
Arestas: CONTAINS, DEFINES, CALLS, IMPORTS, INHERITS
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from neo4j import AsyncGraphDatabase  # type: ignore

from .config import settings
from .ast_parser import ASTNode, ASTRelation

log = logging.getLogger(__name__)

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver:
        await _driver.close()
        _driver = None


async def ensure_indexes() -> None:
    """Cria índices e constraints do Neo4j (idempotente)."""
    driver = get_driver()
    async with driver.session() as session:
        for label in ("File", "Function", "Class", "Method", "Module"):
            await session.run(
                f"CREATE INDEX {label.lower()}_user_idx IF NOT EXISTS "
                f"FOR (n:{label}) ON (n.user_id, n.name)"
            )


async def delete_user_graph(user_id: str) -> None:
    """Remove todos os nós e arestas de um usuário."""
    driver = get_driver()
    async with driver.session() as session:
        await session.run(
            "MATCH (n {user_id: $uid}) DETACH DELETE n",
            uid=user_id,
        )


async def upsert_nodes(user_id: str, nodes: list[ASTNode]) -> None:
    if not nodes:
        return
    driver = get_driver()
    async with driver.session() as session:
        for node in nodes:
            await session.run(
                f"""
                MERGE (n:{node.node_type} {{user_id: $uid, name: $name, file_path: $fp}})
                SET n.language   = $lang,
                    n.start_line = $sl,
                    n.end_line   = $el,
                    n.parent_name = $parent
                """,
                uid=user_id,
                name=node.name,
                fp=node.file_path,
                lang=node.language,
                sl=node.start_line,
                el=node.end_line,
                parent=node.parent_name,
            )


async def upsert_relations(user_id: str, relations: list[ASTRelation]) -> None:
    if not relations:
        return
    driver = get_driver()
    async with driver.session() as session:
        for rel in relations:
            await session.run(
                f"""
                MERGE (a:{rel.from_type} {{user_id: $uid, name: $from_name, file_path: $fp}})
                MERGE (b:{rel.to_type}   {{user_id: $uid, name: $to_name}})
                MERGE (a)-[:{rel.relation}]->(b)
                """,
                uid=user_id,
                from_name=rel.from_name,
                fp=rel.from_file,
                to_name=rel.to_name,
            )


# ── Queries de busca ──────────────────────────────────────────

async def find_symbol(user_id: str, symbol: str, symbol_type: str = "all") -> list[dict]:
    """Retorna todos os nós que correspondem ao nome do símbolo."""
    driver = get_driver()
    labels = {
        "function": ["Function", "Method"],
        "class": ["Class"],
        "method": ["Method"],
        "all": ["Function", "Method", "Class"],
    }.get(symbol_type, ["Function", "Method", "Class"])

    results = []
    async with driver.session() as session:
        for label in labels:
            records = await session.run(
                f"""
                MATCH (n:{label} {{user_id: $uid}})
                WHERE n.name CONTAINS $sym
                RETURN n.name AS name, n.file_path AS file_path,
                       n.start_line AS start_line, n.end_line AS end_line,
                       labels(n)[0] AS type
                LIMIT 20
                """,
                uid=user_id,
                sym=symbol,
            )
            async for row in records:
                results.append(dict(row))
    return results


async def find_references(user_id: str, symbol: str, file_path: Optional[str] = None) -> list[dict]:
    """Encontra todos os nós que CALLS ou IMPORTS o símbolo."""
    driver = get_driver()
    results = []
    async with driver.session() as session:
        fp_filter = "AND target.file_path = $fp" if file_path else ""
        records = await session.run(
            f"""
            MATCH (caller)-[:CALLS|IMPORTS]->(target {{user_id: $uid, name: $sym}})
            WHERE caller.user_id = $uid {fp_filter}
            RETURN caller.name AS caller_name,
                   caller.file_path AS caller_file,
                   caller.start_line AS caller_line,
                   labels(caller)[0] AS caller_type,
                   labels(target)[0] AS target_type
            LIMIT 50
            """,
            uid=user_id,
            sym=symbol,
            fp=file_path or "",
        )
        async for row in records:
            results.append(dict(row))
    return results


async def get_call_graph(user_id: str, function: str, depth: int = 3) -> list[dict]:
    """Retorna o call graph a partir de uma função, até `depth` níveis."""
    driver = get_driver()
    results = []
    async with driver.session() as session:
        records = await session.run(
            f"""
            MATCH path = (root {{user_id: $uid, name: $fn}})-[:CALLS*1..{depth}]->(callee)
            WHERE callee.user_id = $uid
            UNWIND relationships(path) AS rel
            RETURN startNode(rel).name AS caller,
                   startNode(rel).file_path AS caller_file,
                   endNode(rel).name   AS callee,
                   endNode(rel).file_path AS callee_file
            """,
            uid=user_id,
            fn=function,
        )
        async for row in records:
            results.append(dict(row))
    return results
