"""Regression tests for sandbox permission patch behavior."""

from __future__ import annotations

import re

from tests.unit.agent_runtime_test_loader import ROOT

PATCH_TEXT = (ROOT / "services/sandbox/patches/multimodal-grpc-handler.patch").read_text(
    encoding="utf-8"
)
ENV_INIT_TEXT = (ROOT / "services/sandbox/env_init.sh").read_text(encoding="utf-8")


def test_request_permissions_auto_allows_read_only_tools() -> None:
    assert "+const CAPPYCLOUD_READ_ONLY_TOOLS = new Set([" in PATCH_TEXT
    assert "'Read'" in PATCH_TEXT
    assert "'Grep'" in PATCH_TEXT
    assert "'Glob'" in PATCH_TEXT
    assert (
        "+    return CAPPYCLOUD_READ_ONLY_TOOLS.has(toolName) ? { behavior: 'allow' } : null"
        in PATCH_TEXT
    )


def test_request_permissions_keeps_mutating_tools_interactive() -> None:
    assert "+const CAPPYCLOUD_MUTATING_TOOLS = new Set([" in PATCH_TEXT
    assert "'Bash'" in PATCH_TEXT
    match = re.search(
        r"\+  if \(mode === 'request_permissions'\) \{\n(?P<body>.*?)\n\+  \}",
        PATCH_TEXT,
        flags=re.DOTALL,
    )
    assert match is not None
    assert "CAPPYCLOUD_READ_ONLY_TOOLS.has(toolName)" in match.group("body")
    assert "? { behavior: 'allow' } : null" in match.group("body")


def test_unknown_permission_mode_defaults_to_bypass_permissions() -> None:
    assert "+    return 'bypass_permissions'" in PATCH_TEXT
    assert (
        "+  return CAPPYCLOUD_PERMISSION_MODES.has(mode) ? mode : 'bypass_permissions'"
        in PATCH_TEXT
    )


def test_sandbox_bootstrap_does_not_require_opengateway_key() -> None:
    assert 'OPENGATEWAY_API_KEY="${OPENGATEWAY_API_KEY' not in ENV_INIT_TEXT
    assert 'OPENAI_API_KEY="${OPENAI_API_KEY:-cappycloud-runtime-bootstrap-key}"' in ENV_INIT_TEXT
    assert "provider_api_key" in ENV_INIT_TEXT
    assert "requestedProviderApiKey" in ENV_INIT_TEXT
    assert "provider override:" in ENV_INIT_TEXT
    assert "${requestedProviderApiKey}" not in ENV_INIT_TEXT


def test_sandbox_startup_env_is_a_concrete_openai_provider_selection() -> None:
    # OpenClaude only falls back to its Opengateway default profile when the
    # env does not already select a provider (hasConcreteProviderSelection).
    assert 'CLAUDE_CODE_USE_OPENAI="${CLAUDE_CODE_USE_OPENAI:-1}"' in ENV_INIT_TEXT
    assert 'OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://openrouter.ai/api/v1}"' in ENV_INIT_TEXT
    assert 'export CLAUDE_CODE_USE_OPENAI="${CLAUDE_CODE_USE_OPENAI}"' in ENV_INIT_TEXT
    assert 'export OPENAI_BASE_URL="${OPENAI_BASE_URL}"' in ENV_INIT_TEXT
    assert "/openclaude/src/utils/providerProfile.ts" not in ENV_INIT_TEXT


def test_azure_foundry_v1_patch_targets_request_executor() -> None:
    assert "/openclaude/src/services/api/openaiShim/requestExecutor.ts" in ENV_INIT_TEXT
    assert "CappyCloud Azure AI Foundry v1" in ENV_INIT_TEXT
    assert "isAzure && !isAzureOpenAIV1" in ENV_INIT_TEXT
    assert "return `${normalizedBaseUrl}/chat/completions`" in ENV_INIT_TEXT


def test_dynamic_model_and_provider_overrides_are_reset_after_request() -> None:
    assert "CappyCloud dynamic model override" in ENV_INIT_TEXT
    assert "CappyCloud provider override" in ENV_INIT_TEXT
    assert "process.env.OPENAI_MODEL = requestedModel" in ENV_INIT_TEXT
    assert "process.env.OPENAI_BASE_URL = requestedProviderBaseUrl" in ENV_INIT_TEXT
    assert "process.env.OPENAI_API_KEY = requestedProviderApiKey" in ENV_INIT_TEXT
    assert "process.env.OPENAI_MODEL = previousOpenAIModel" in ENV_INIT_TEXT
    assert "process.env.OPENAI_BASE_URL = previousOpenAIBaseUrl" in ENV_INIT_TEXT
    assert "process.env.OPENAI_API_KEY = previousOpenAIApiKey" in ENV_INIT_TEXT
