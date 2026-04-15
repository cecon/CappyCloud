#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# /session_start.sh — Cria um git worktree por sessão de conversa
#
# Uso:  /session_start.sh <env_slug> <session_id> <worktree_path> [base_branch]
#
# Chamado via `docker exec` pelo EnvironmentManager sempre que uma
# nova conversa começa.  O worktree é criado a partir de /repos/<env_slug>,
# na branch BASE_BRANCH (padrão: HEAD do clone principal).
#
# A branch da sessão é nomeada <env_slug>_<session_id>, derivada de BASE_BRANCH.
# ──────────────────────────────────────────────────────────────
set -euo pipefail

ENV_SLUG="${1:?Usage: session_start.sh <env_slug> <session_id> <worktree_path> [base_branch]}"
SESSION_ID="${2:?Usage: session_start.sh <env_slug> <session_id> <worktree_path> [base_branch]}"
WORKTREE_PATH="${3:?Usage: session_start.sh <env_slug> <session_id> <worktree_path> [base_branch]}"
BASE_BRANCH="${4:-}"
MAIN_REPO="/repos/${ENV_SLUG}"

echo "[session_start] env=${ENV_SLUG}  session=${SESSION_ID}  worktree=${WORKTREE_PATH}  base=${BASE_BRANCH:-HEAD}"

mkdir -p "$(dirname "$WORKTREE_PATH")"

# Se o worktree já existe, apenas valida
if [ -d "$WORKTREE_PATH/.git" ] || [ -f "$WORKTREE_PATH/.git" ]; then
    echo "[session_start] Worktree já existe — reutilizando."
    exit 0
fi

if [ -d "$MAIN_REPO/.git" ]; then
    # ── Recuperação: se o repo não tem remote, o clone inicial falhou ──────────
    # Verifica se tem remote configurado; se não, tenta clonar agora
    REMOTE_URL=$(git -C "$MAIN_REPO" remote get-url origin 2>/dev/null || true)
    if [ -z "$REMOTE_URL" ] && [ -n "${WORKSPACE_REPO:-}" ]; then
        echo "[session_start] Clone inicial falhou — tentando recuperar agora..."

        if [ -n "${GIT_AUTH_TOKEN:-}" ]; then
            AUTH_REPO=$(echo "${WORKSPACE_REPO}" | sed 's|https://[^@]*@|https://|' | \
                sed "s|https://dev.azure.com|https://pat:${GIT_AUTH_TOKEN}@dev.azure.com|")
        else
            AUTH_REPO="${WORKSPACE_REPO}"
        fi
        BRANCH="${WORKSPACE_BRANCH:-main}"

        # Salva o CLAUDE.md antes de limpar
        [ -f "$MAIN_REPO/CLAUDE.md" ] && cp "$MAIN_REPO/CLAUDE.md" /tmp/_claude_md_backup || true

        # Limpa o repo vazio e substitui pelo clone real
        rm -rf "$MAIN_REPO/.git"
        if git clone --depth=1 --branch "$BRANCH" "$AUTH_REPO" "$MAIN_REPO" 2>&1 || \
           git clone --depth=1 "$AUTH_REPO" "$MAIN_REPO" 2>&1; then
            echo "[session_start] Recuperação do clone concluída."
        else
            echo "[session_start] AVISO: recuperação do clone falhou — repo vazio."
            git -C "$MAIN_REPO" init -b main
        fi

        # Restaura o CLAUDE.md
        [ -f /tmp/_claude_md_backup ] && cp /tmp/_claude_md_backup "$MAIN_REPO/CLAUDE.md" && rm /tmp/_claude_md_backup || true
    fi

    # Garante que HEAD aponta para um commit válido antes de criar o worktree.
    if ! git -C "$MAIN_REPO" rev-parse HEAD >/dev/null 2>&1; then
        echo "[session_start] Repo sem commits — criando commit inicial..."
        git -C "$MAIN_REPO" config user.email "agent@cappycloud.local"
        git -C "$MAIN_REPO" config user.name "CappyCloud Agent"
        git -C "$MAIN_REPO" commit --allow-empty -m "init"
    fi

    # Nome da branch: <env_slug>_<session_id> (legível e rastreável)
    BRANCH="${ENV_SLUG}_${SESSION_ID}"

    if [ -n "${BASE_BRANCH}" ]; then
        # Garante que a branch base existe localmente (pode ser remota)
        if ! git -C "$MAIN_REPO" rev-parse --verify "${BASE_BRANCH}" >/dev/null 2>&1; then
            echo "[session_start] Buscando branch base remota: ${BASE_BRANCH}..."
            git -C "$MAIN_REPO" fetch origin "${BASE_BRANCH}:${BASE_BRANCH}" 2>&1 \
                || echo "[session_start] AVISO: fetch de ${BASE_BRANCH} falhou — usando HEAD."
        fi

        echo "[session_start] Criando worktree git: branch=${BRANCH} a partir de ${BASE_BRANCH}"
        git -C "$MAIN_REPO" worktree add -b "$BRANCH" "$WORKTREE_PATH" "$BASE_BRANCH" 2>&1 \
            || git -C "$MAIN_REPO" worktree add "$WORKTREE_PATH" 2>&1
    else
        echo "[session_start] Criando worktree git: branch=${BRANCH} a partir de HEAD"
        git -C "$MAIN_REPO" worktree add -b "$BRANCH" "$WORKTREE_PATH" 2>&1 \
            || git -C "$MAIN_REPO" worktree add "$WORKTREE_PATH" 2>&1
    fi
else
    echo "[session_start] Sem repo git em $MAIN_REPO — criando directório vazio."
    mkdir -p "$WORKTREE_PATH"
fi

echo "[session_start] OK"
