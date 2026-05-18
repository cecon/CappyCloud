#!/usr/bin/env python3
"""Pre-commit hook: exige Alembic instalado ao alterar migrations."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

MIGRATIONS_DIR = Path("services/api/alembic/versions")


def is_migration(path: str) -> bool:
    p = Path(path)
    try:
        return p.suffix == ".py" and p.is_relative_to(MIGRATIONS_DIR)
    except AttributeError:
        try:
            p.relative_to(MIGRATIONS_DIR)
            return p.suffix == ".py"
        except ValueError:
            return False


def main(argv: list[str]) -> int:
    migration_files = [path for path in argv if is_migration(path)]
    if not migration_files:
        return 0

    alembic = shutil.which("alembic")
    if not alembic:
        print(
            "Erro: alterações em services/api/alembic/versions exigem o comando "
            "`alembic` disponível no PATH.\n\n"
            "Não crie migrations manualmente. Ative o ambiente da API e gere com:\n"
            "  cd services/api\n"
            "  alembic revision --autogenerate -m \"descricao_curta\"\n\n"
            "Arquivos bloqueados:\n"
            + "\n".join(f"  - {path}" for path in migration_files),
            file=sys.stderr,
        )
        return 1

    try:
        result = subprocess.run(
            [alembic, "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Erro: não foi possível executar `{alembic} --version`: {exc}", file=sys.stderr)
        return 1

    version = (result.stdout or result.stderr or "").strip()
    if version:
        print(f"Alembic detectado para validar fluxo de migration: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
