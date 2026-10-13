"""Falha se o web-c3/ contiver arquivos ou textos do tema privado (Able Pro).

O CappyCloud é público; o C3Theme é privado e derivado do Able Pro (ThemeForest),
que não pode ser publicado. Ver specs/013-c3theme-frontend/contracts/theme-dependency.md.

Uso: python scripts/check_c3theme_leak.py [raiz]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP_DIRS = {"node_modules", "dist", "coverage", ".vite"}
TEXT_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".css", ".json", ".html", ".md", ".svg"}

# Arte do Able Pro que vem no seed do C3Theme.
FORBIDDEN_NAMES = re.compile(
    r"^(img-error-(404|500)\.svg|img-soon-.*|img-construction-.*|img-cunstruct-.*"
    r"|message\d+\.svg|avatar-\d+\.png)$",
    re.IGNORECASE,
)
# Textos do fornecedor que não devem aparecer no código do app.
FORBIDDEN_TEXT = re.compile(r"phoenixcoded|able\s*pro|themeforest", re.IGNORECASE)


def find_leaks(root: Path) -> list[str]:
    leaks: list[str] = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if FORBIDDEN_NAMES.match(path.name):
            leaks.append(f"{rel}: arquivo de arte do tema")
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="ignore")
            match = FORBIDDEN_TEXT.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                leaks.append(f"{rel}:{line}: texto do fornecedor ({match.group(0)!r})")
    return leaks


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1] / "web-c3"
    if not root.is_dir():
        print(f"{root} não existe; nada a verificar.")
        return 0
    leaks = find_leaks(root)
    if leaks:
        print("Conteúdo do tema privado encontrado no web-c3/ (repositório público):")
        for leak in leaks:
            print(f"  - {leak}")
        return 1
    print("web-c3/: nenhum arquivo ou texto do tema privado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
