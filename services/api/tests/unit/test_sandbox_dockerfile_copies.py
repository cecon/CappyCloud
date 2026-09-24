"""Todo módulo local exigido pelo session server precisa ser copiado para a imagem.

Um ``require('./x')`` sem o ``COPY`` correspondente derruba o session server no
boot (MODULE_NOT_FOUND) e o sandbox fica sem sessões.
"""

from __future__ import annotations

import re

from tests.unit.agent_runtime_test_loader import ROOT

SANDBOX = ROOT / "services/sandbox"


def test_modulos_locais_do_session_server_estao_no_dockerfile() -> None:
    dockerfile = (SANDBOX / "Dockerfile").read_text(encoding="utf-8")
    required: set[str] = set()
    for source in SANDBOX.glob("*.js"):
        required |= set(re.findall(r"require\('\./([\w-]+)'\)", source.read_text(encoding="utf-8")))

    missing = sorted(
        name for name in required if f"COPY services/sandbox/{name}.js /{name}.js" not in dockerfile
    )
    assert required, "nenhum require local encontrado — o teste perdeu a referência"
    assert missing == [], f"módulos sem COPY no Dockerfile: {missing}"
