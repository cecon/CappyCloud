"""Shared loader for cappycloud_agent regression tests."""

from __future__ import annotations

import sys
import types
from importlib import util
from pathlib import Path


def _find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "services" / "cappycloud_agent").is_dir():
            return candidate
    raise RuntimeError("Não encontrei services/cappycloud_agent no worktree.")


ROOT = _find_repo_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_agent_pkg = types.ModuleType("services.cappycloud_agent")
_agent_pkg.__path__ = [str(ROOT / "services/cappycloud_agent")]  # type: ignore[attr-defined]
sys.modules.setdefault("services.cappycloud_agent", _agent_pkg)


def load_agent_module(name: str, path: Path) -> types.ModuleType:
    spec = util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


agent_context = load_agent_module(
    "services.cappycloud_agent._agent_context",
    ROOT / "services/cappycloud_agent/_agent_context.py",
)
agent_prompt_sections = load_agent_module(
    "services.cappycloud_agent._agent_prompt_sections",
    ROOT / "services/cappycloud_agent/_agent_prompt_sections.py",
)
pipeline_helpers = load_agent_module(
    "services.cappycloud_agent._pipeline_helpers",
    ROOT / "services/cappycloud_agent/_pipeline_helpers.py",
)
signoz_context = load_agent_module(
    "services.cappycloud_agent._signoz_context",
    ROOT / "services/cappycloud_agent/_signoz_context.py",
)
pipeline_event_stream = load_agent_module(
    "services.cappycloud_agent._pipeline_event_stream",
    ROOT / "services/cappycloud_agent/_pipeline_event_stream.py",
)
grpc_event_handlers = load_agent_module(
    "services.cappycloud_agent._grpc_event_handlers",
    ROOT / "services/cappycloud_agent/_grpc_event_handlers.py",
)
assistant_output = load_agent_module(
    "services.cappycloud_agent._assistant_output",
    ROOT / "services/cappycloud_agent/_assistant_output.py",
)
task_final_message = load_agent_module(
    "services.cappycloud_agent._task_final_message",
    ROOT / "services/cappycloud_agent/_task_final_message.py",
)
evidence_terms = load_agent_module(
    "services.cappycloud_agent._evidence_terms",
    ROOT / "services/cappycloud_agent/_evidence_terms.py",
)
evidence_repo_docs = load_agent_module(
    "services.cappycloud_agent._evidence_repo_docs",
    ROOT / "services/cappycloud_agent/_evidence_repo_docs.py",
)
evidence_docs = load_agent_module(
    "services.cappycloud_agent._evidence_docs",
    ROOT / "services/cappycloud_agent/_evidence_docs.py",
)
evidence_models = load_agent_module(
    "services.cappycloud_agent._evidence_models",
    ROOT / "services/cappycloud_agent/_evidence_models.py",
)
evidence_render = load_agent_module(
    "services.cappycloud_agent._evidence_render",
    ROOT / "services/cappycloud_agent/_evidence_render.py",
)
evidence_prefetch = load_agent_module(
    "services.cappycloud_agent._evidence_prefetch",
    ROOT / "services/cappycloud_agent/_evidence_prefetch.py",
)
