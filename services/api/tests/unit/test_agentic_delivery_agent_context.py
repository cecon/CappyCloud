import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[3] / "cappycloud_agent" / "_agent_prompt_sections.py"
spec = importlib.util.spec_from_file_location("agent_prompt_sections_under_test", MODULE_PATH)
assert spec and spec.loader
prompt_sections = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prompt_sections)


def test_agent_context_renders_review_only_cycle_context() -> None:
    prompt = prompt_sections.render_agentic_cycle_context(
        {
            "cycle_id": "cycle-1",
            "work_package_id": "wp-1",
            "work_package_version": 2,
            "domain_key": "erp-a",
            "repository_ids": ["repo-1"],
        }
    )

    assert "Contexto do ciclo Agentic Delivery" in prompt
    assert "review-only" in prompt
    assert "`repo-1`" in prompt
