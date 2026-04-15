"""
Parseia arquivos de código com tree-sitter e extrai:
  - CodeChunk : trecho de código para gerar embedding (função, classe, bloco)
  - ASTNode   : nó do grafo (File, Function, Class, Method, Module)
  - ASTRelation: aresta do grafo (CALLS, IMPORTS, INHERITS, CONTAINS)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Extensão → nome de linguagem tree-sitter
_LANG_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

# Linguagens suportadas no momento
_SUPPORTED_LANGS = frozenset(_LANG_BY_EXT.values())


# ── Estruturas de dados ───────────────────────────────────────

@dataclass
class CodeChunk:
    file_path: str
    language: str
    chunk_type: str          # function | class | method | module
    chunk_name: Optional[str]
    start_line: int
    end_line: int
    content: str


@dataclass
class ASTNode:
    node_type: str           # File | Function | Class | Method | Module
    name: str
    file_path: str
    language: str
    start_line: int
    end_line: int
    parent_name: Optional[str] = None  # nome da classe para Method


@dataclass
class ASTRelation:
    from_type: str
    from_name: str
    from_file: str
    relation: str            # CALLS | IMPORTS | INHERITS | CONTAINS | DEFINES
    to_type: str
    to_name: str
    to_file: Optional[str] = None


@dataclass
class ParseResult:
    chunks: list[CodeChunk] = field(default_factory=list)
    nodes: list[ASTNode] = field(default_factory=list)
    relations: list[ASTRelation] = field(default_factory=list)


# ── Cache de parsers ──────────────────────────────────────────

_parsers: dict[str, object] = {}


def _get_parser(language: str):
    """Retorna (e cria, se necessário) um parser tree-sitter para a linguagem."""
    if language in _parsers:
        return _parsers[language]

    try:
        from tree_sitter import Language, Parser  # type: ignore

        if language == "python":
            import tree_sitter_python as ts_lang  # type: ignore
        elif language == "javascript":
            import tree_sitter_javascript as ts_lang  # type: ignore
        elif language == "typescript":
            import tree_sitter_typescript as ts_lang  # type: ignore

            # tree-sitter-typescript expõe .language_typescript() e .language_tsx()
            lang_obj = Language(ts_lang.language_typescript())
            parser = Parser(lang_obj)
            _parsers[language] = parser
            return parser
        else:
            return None

        lang_obj = Language(ts_lang.language())
        parser = Parser(lang_obj)
        _parsers[language] = parser
        return parser

    except Exception as exc:
        log.warning("Falha ao criar parser para %s: %s", language, exc)
        return None


# ── Helpers ───────────────────────────────────────────────────

def _node_text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _child_by_field(node, field_name: str):
    child = node.child_by_field_name(field_name)
    return child


def _line(node) -> int:
    return node.start_point[0] + 1  # 1-based


def _end_line(node) -> int:
    return node.end_point[0] + 1


# ── Extratores por linguagem ──────────────────────────────────

def _extract_python(tree, source_bytes: bytes, file_path: str) -> ParseResult:
    result = ParseResult()
    source = source_bytes.decode("utf-8", errors="replace")

    file_node_name = Path(file_path).name
    result.nodes.append(ASTNode(
        node_type="File",
        name=file_node_name,
        file_path=file_path,
        language="python",
        start_line=1,
        end_line=source.count("\n") + 1,
    ))

    imports: list[str] = []
    classes_seen: set[str] = set()

    def walk(node, current_class: Optional[str] = None):
        t = node.type

        if t == "import_statement":
            for child in node.children:
                if child.type in ("dotted_name", "aliased_import"):
                    mod = _node_text(child, source_bytes).split(" as ")[0].strip()
                    imports.append(mod)
                    result.relations.append(ASTRelation(
                        from_type="File", from_name=file_node_name, from_file=file_path,
                        relation="IMPORTS",
                        to_type="Module", to_name=mod,
                    ))

        elif t == "import_from_statement":
            mod_node = _child_by_field(node, "module_name")
            if mod_node:
                mod = _node_text(mod_node, source_bytes).strip()
                imports.append(mod)
                result.relations.append(ASTRelation(
                    from_type="File", from_name=file_node_name, from_file=file_path,
                    relation="IMPORTS",
                    to_type="Module", to_name=mod,
                ))

        elif t == "class_definition":
            name_node = _child_by_field(node, "name")
            if name_node:
                class_name = _node_text(name_node, source_bytes)
                classes_seen.add(class_name)
                result.nodes.append(ASTNode(
                    node_type="Class",
                    name=class_name,
                    file_path=file_path,
                    language="python",
                    start_line=_line(node),
                    end_line=_end_line(node),
                ))
                result.relations.append(ASTRelation(
                    from_type="File", from_name=file_node_name, from_file=file_path,
                    relation="CONTAINS", to_type="Class", to_name=class_name,
                ))
                # Herança
                bases_node = _child_by_field(node, "superclasses")
                if bases_node:
                    for base_child in bases_node.children:
                        if base_child.type == "identifier":
                            base_name = _node_text(base_child, source_bytes)
                            result.relations.append(ASTRelation(
                                from_type="Class", from_name=class_name, from_file=file_path,
                                relation="INHERITS", to_type="Class", to_name=base_name,
                            ))

                result.chunks.append(CodeChunk(
                    file_path=file_path,
                    language="python",
                    chunk_type="class",
                    chunk_name=class_name,
                    start_line=_line(node),
                    end_line=_end_line(node),
                    content=_node_text(node, source_bytes),
                ))

                body = _child_by_field(node, "body")
                if body:
                    for child in body.children:
                        walk(child, current_class=class_name)
            return  # já visitou body acima

        elif t == "function_definition":
            name_node = _child_by_field(node, "name")
            if name_node:
                func_name = _node_text(name_node, source_bytes)
                node_type = "Method" if current_class else "Function"
                result.nodes.append(ASTNode(
                    node_type=node_type,
                    name=func_name,
                    file_path=file_path,
                    language="python",
                    start_line=_line(node),
                    end_line=_end_line(node),
                    parent_name=current_class,
                ))
                if current_class:
                    result.relations.append(ASTRelation(
                        from_type="Class", from_name=current_class, from_file=file_path,
                        relation="DEFINES", to_type="Method", to_name=func_name,
                    ))
                else:
                    result.relations.append(ASTRelation(
                        from_type="File", from_name=file_node_name, from_file=file_path,
                        relation="CONTAINS", to_type="Function", to_name=func_name,
                    ))

                result.chunks.append(CodeChunk(
                    file_path=file_path,
                    language="python",
                    chunk_type="method" if current_class else "function",
                    chunk_name=func_name,
                    start_line=_line(node),
                    end_line=_end_line(node),
                    content=_node_text(node, source_bytes),
                ))

                # Chamadas dentro da função
                _extract_calls_python(node, source_bytes, func_name, current_class, file_path, file_node_name, result)

        for child in node.children:
            if t != "class_definition":  # class já visitou body
                walk(child, current_class=current_class)

    walk(tree.root_node)
    return result


def _extract_calls_python(func_node, source_bytes, func_name, current_class, file_path, file_node_name, result):
    """Extrai chamadas de função dentro de um nó de função Python."""
    caller_name = f"{current_class}.{func_name}" if current_class else func_name
    caller_type = "Method" if current_class else "Function"

    def walk(node):
        if node.type == "call":
            func_child = node.child_by_field_name("function")
            if func_child:
                if func_child.type == "identifier":
                    callee = _node_text(func_child, source_bytes)
                    result.relations.append(ASTRelation(
                        from_type=caller_type, from_name=caller_name, from_file=file_path,
                        relation="CALLS", to_type="Function", to_name=callee,
                    ))
                elif func_child.type == "attribute":
                    attr = func_child.child_by_field_name("attribute")
                    if attr:
                        callee = _node_text(attr, source_bytes)
                        result.relations.append(ASTRelation(
                            from_type=caller_type, from_name=caller_name, from_file=file_path,
                            relation="CALLS", to_type="Function", to_name=callee,
                        ))
        for child in node.children:
            walk(child)

    walk(func_node)


def _extract_js_ts(tree, source_bytes: bytes, file_path: str, language: str) -> ParseResult:
    """Extrai AST de JavaScript/TypeScript (heurística simplificada)."""
    result = ParseResult()
    file_node_name = Path(file_path).name
    source = source_bytes.decode("utf-8", errors="replace")

    result.nodes.append(ASTNode(
        node_type="File",
        name=file_node_name,
        file_path=file_path,
        language=language,
        start_line=1,
        end_line=source.count("\n") + 1,
    ))

    def walk(node, current_class: Optional[str] = None):
        t = node.type

        if t in ("import_statement", "import_declaration"):
            src_node = node.child_by_field_name("source")
            if src_node:
                mod = _node_text(src_node, source_bytes).strip("'\"")
                result.relations.append(ASTRelation(
                    from_type="File", from_name=file_node_name, from_file=file_path,
                    relation="IMPORTS", to_type="Module", to_name=mod,
                ))

        elif t == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                class_name = _node_text(name_node, source_bytes)
                result.nodes.append(ASTNode(
                    node_type="Class",
                    name=class_name,
                    file_path=file_path,
                    language=language,
                    start_line=_line(node),
                    end_line=_end_line(node),
                ))
                result.relations.append(ASTRelation(
                    from_type="File", from_name=file_node_name, from_file=file_path,
                    relation="CONTAINS", to_type="Class", to_name=class_name,
                ))
                result.chunks.append(CodeChunk(
                    file_path=file_path,
                    language=language,
                    chunk_type="class",
                    chunk_name=class_name,
                    start_line=_line(node),
                    end_line=_end_line(node),
                    content=_node_text(node, source_bytes),
                ))
                for child in node.children:
                    walk(child, current_class=class_name)
                return

        elif t in ("function_declaration", "function_definition",
                   "method_definition", "arrow_function"):
            name_node = node.child_by_field_name("name")
            func_name = _node_text(name_node, source_bytes) if name_node else "<anonymous>"
            node_type = "Method" if current_class else "Function"
            result.nodes.append(ASTNode(
                node_type=node_type,
                name=func_name,
                file_path=file_path,
                language=language,
                start_line=_line(node),
                end_line=_end_line(node),
                parent_name=current_class,
            ))
            result.chunks.append(CodeChunk(
                file_path=file_path,
                language=language,
                chunk_type="method" if current_class else "function",
                chunk_name=func_name,
                start_line=_line(node),
                end_line=_end_line(node),
                content=_node_text(node, source_bytes),
            ))

        for child in node.children:
            walk(child, current_class=current_class)

    walk(tree.root_node)
    return result


# ── Ponto de entrada público ──────────────────────────────────

def parse_file(file_path: str, content: str) -> ParseResult:
    """
    Parseia um arquivo de código e retorna chunks, nós e relações AST.

    Retorna um ParseResult vazio se a extensão não for suportada.
    """
    ext = Path(file_path).suffix.lower()
    language = _LANG_BY_EXT.get(ext)
    if not language:
        return ParseResult()

    parser = _get_parser(language)
    if not parser:
        return ParseResult()

    try:
        source_bytes = content.encode("utf-8", errors="replace")
        tree = parser.parse(source_bytes)

        if language == "python":
            return _extract_python(tree, source_bytes, file_path)
        elif language in ("javascript", "typescript"):
            return _extract_js_ts(tree, source_bytes, file_path, language)
        else:
            return ParseResult()
    except Exception as exc:
        log.warning("Erro ao parsear %s: %s", file_path, exc)
        return ParseResult()


def supported_extensions() -> frozenset[str]:
    return frozenset(_LANG_BY_EXT.keys())
