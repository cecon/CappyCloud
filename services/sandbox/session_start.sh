#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# /session_start.sh — Cria um git worktree por sessão de conversa
#
# Uso:  /session_start.sh <env_slug> <session_id> <worktree_path> [base_branch] [branch_name] [clone_url]
#
# Chamado pelo session_server.js (HTTP POST /sessions) sempre que
# uma nova conversa começa. Cria um worktree isolado e faz push
# da branch de sessão para o remote (idempotente).
#
# Tokens de autenticação herdados do ambiente do container:
#   DEVOPS_TOKEN  → Azure DevOps
#   GITHUB_TOKEN  → GitHub
# ──────────────────────────────────────────────────────────────
set -euo pipefail

ENV_SLUG="${1:?Usage: session_start.sh <env_slug> <session_id> <worktree_path> [base_branch] [branch_name] [clone_url]}"
SESSION_ID="${2:?Usage: session_start.sh <env_slug> <session_id> <worktree_path> [base_branch] [branch_name] [clone_url]}"
WORKTREE_PATH="${3:?Usage: session_start.sh <env_slug> <session_id> <worktree_path> [base_branch] [branch_name] [clone_url]}"
BASE_BRANCH="${4:-}"
BRANCH_NAME="${5:-${ENV_SLUG}_${SESSION_ID}}"
CLONE_URL="${6:-}"
MAIN_REPO="/repos/${ENV_SLUG}"

DEVOPS_TOKEN="${DEVOPS_TOKEN:-}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

echo "[session_start] env=${ENV_SLUG}  session=${SESSION_ID}  worktree=${WORKTREE_PATH}  base=${BASE_BRANCH:-HEAD}  branch=${BRANCH_NAME}"

mkdir -p "$(dirname "$WORKTREE_PATH")"

# ── Função: push da branch de sessão para o remote ───────────
# Chamada após worktree criado. Não-fatal: falha só gera aviso.
_push_session_branch() {
    local repo_dir="$1"
    local branch="$2"

    # Verifica se tem remote configurado
    local remote_url
    remote_url=$(git -C "$repo_dir" remote get-url origin 2>/dev/null || true)
    if [ -z "$remote_url" ]; then
        echo "[session_start] Sem remote configurado — branch apenas local."
        return 0
    fi

    # Constrói URL autenticada
    local auth_url="${remote_url}"
    if [ -n "${GITHUB_TOKEN}" ]; then
        auth_url=$(echo "${auth_url}" | sed \
            "s|https://github.com|https://x-token:${GITHUB_TOKEN}@github.com|" | sed \
            "s|https://x-token:.*@github.com@github.com|https://x-token:${GITHUB_TOKEN}@github.com|")
    fi
    if [ -n "${DEVOPS_TOKEN}" ]; then
        auth_url=$(echo "${auth_url}" | sed \
            "s|https://dev.azure.com|https://pat:${DEVOPS_TOKEN}@dev.azure.com|")
    fi

    echo "[session_start] Fazendo push da branch ${branch} para o remote…"
    if git -C "$repo_dir" push "${auth_url}" "${branch}:${branch}" \
        --set-upstream 2>&1; then
        echo "[session_start] Push concluído: ${branch}"
    else
        echo "[session_start] AVISO: push de ${branch} falhou — branch apenas local por agora."
    fi
}
# Se o worktree já existe, reutiliza
if [ -d "$WORKTREE_PATH/.git" ] || [ -f "$WORKTREE_PATH/.git" ]; then
    echo "[session_start] Worktree já existe — reutilizando."
    exit 0
fi

if [ -d "$MAIN_REPO/.git" ]; then
    # ── Recuperação: repo sem remote (clone inicial falhou) ──────────
    REMOTE_URL=$(git -C "$MAIN_REPO" remote get-url origin 2>/dev/null || true)
    if [ -z "$REMOTE_URL" ] && [ -n "${WORKSPACE_REPOS:-}" ]; then
        FOUND_URL=""
        IFS=',' read -ra _REPOS <<< "${WORKSPACE_REPOS}"
        for _r in "${_REPOS[@]}"; do
            _r=$(echo "${_r}" | tr -d '[:space:]')
            _slug=$(basename "${_r}" | sed 's/\.git$//')
            if [ "${_slug}" = "${ENV_SLUG}" ]; then
                FOUND_URL="${_r}"
                break
            fi
        done

        if [ -n "${FOUND_URL}" ]; then
            echo "[session_start] Clone inicial falhou — tentando recuperar..."

            AUTH_REPO="${FOUND_URL}"
            if [ -n "${DEVOPS_TOKEN}" ]; then
                AUTH_REPO=$(echo "${AUTH_REPO}" | \
                    sed "s|https://dev.azure.com|https://pat:${DEVOPS_TOKEN}@dev.azure.com|")
            fi
            if [ -n "${GITHUB_TOKEN}" ]; then
                AUTH_REPO=$(echo "${AUTH_REPO}" | \
                    sed "s|https://github.com|https://x-token:${GITHUB_TOKEN}@github.com|")
            fi

            BRANCH="${WORKSPACE_BRANCH:-main}"
            [ -f "$MAIN_REPO/CLAUDE.md" ] && cp "$MAIN_REPO/CLAUDE.md" /tmp/_claude_md_backup || true
            rm -rf "$MAIN_REPO/.git"
            if git clone --depth=1 --branch "$BRANCH" "$AUTH_REPO" "$MAIN_REPO" 2>&1 || \
               git clone --depth=1 "$AUTH_REPO" "$MAIN_REPO" 2>&1; then
                echo "[session_start] Recuperação do clone concluída."
            else
                echo "[session_start] AVISO: recuperação falhou — repo vazio."
                git -C "$MAIN_REPO" init -b main 2>/dev/null || git -C "$MAIN_REPO" init
            fi
            [ -f /tmp/_claude_md_backup ] && cp /tmp/_claude_md_backup "$MAIN_REPO/CLAUDE.md" && rm /tmp/_claude_md_backup || true
        fi
    fi

    # Garante HEAD válido
    if ! git -C "$MAIN_REPO" rev-parse HEAD >/dev/null 2>&1; then
        echo "[session_start] Repo sem commits — criando commit inicial..."
        git -C "$MAIN_REPO" config user.email "agent@cappycloud.local"
        git -C "$MAIN_REPO" config user.name "CappyCloud Agent"
        git -C "$MAIN_REPO" commit --allow-empty -m "init"
    fi

    BRANCH="${BRANCH_NAME}"

    if [ -n "${BASE_BRANCH}" ]; then
        if ! git -C "$MAIN_REPO" rev-parse --verify "${BASE_BRANCH}" >/dev/null 2>&1; then
            echo "[session_start] Buscando branch base remota: ${BASE_BRANCH}..."
            git -C "$MAIN_REPO" fetch origin "${BASE_BRANCH}:${BASE_BRANCH}" 2>&1 \
                || echo "[session_start] AVISO: fetch de ${BASE_BRANCH} falhou — usando HEAD."
        fi
        echo "[session_start] Criando worktree: branch=${BRANCH} a partir de ${BASE_BRANCH}"
        git -C "$MAIN_REPO" worktree add -b "$BRANCH" "$WORKTREE_PATH" "$BASE_BRANCH" 2>&1 \
            || git -C "$MAIN_REPO" worktree add "$WORKTREE_PATH" 2>&1
    else
        echo "[session_start] Criando worktree: branch=${BRANCH} a partir de HEAD"
        git -C "$MAIN_REPO" worktree add -b "$BRANCH" "$WORKTREE_PATH" 2>&1 \
            || git -C "$MAIN_REPO" worktree add "$WORKTREE_PATH" 2>&1
    fi

    # ── Push da branch de sessão para o remote ──────────────────
    _push_session_branch "$WORKTREE_PATH" "$BRANCH_NAME" || true

else
    # Tenta clonar se tiver clone_url ou WORKSPACE_REPOS disponível
    RESOLVED_URL="${CLONE_URL:-}"

    if [ -z "$RESOLVED_URL" ] && [ -n "${WORKSPACE_REPOS:-}" ]; then
        IFS=',' read -ra _REPOS <<< "${WORKSPACE_REPOS}"
        for _r in "${_REPOS[@]}"; do
            _r=$(echo "${_r}" | tr -d '[:space:]')
            _slug=$(basename "${_r}" | sed 's/\.git$//')
            if [ "${_slug}" = "${ENV_SLUG}" ]; then
                RESOLVED_URL="${_r}"
                break
            fi
        done
    fi

    if [ -n "$RESOLVED_URL" ]; then
        echo "[session_start] Repo não encontrado — clonando ${ENV_SLUG} de ${RESOLVED_URL}…"

        AUTH_URL="${RESOLVED_URL}"
        if [ -n "${DEVOPS_TOKEN:-}" ]; then
            AUTH_URL=$(echo "${AUTH_URL}" | sed "s|https://dev.azure.com|https://pat:${DEVOPS_TOKEN}@dev.azure.com|")
        fi
        if [ -n "${GITHUB_TOKEN:-}" ]; then
            AUTH_URL=$(echo "${AUTH_URL}" | sed "s|https://github.com|https://x-token:${GITHUB_TOKEN}@github.com|")
        fi

        BRANCH="${BASE_BRANCH:-main}"
        mkdir -p "$MAIN_REPO"
        if git clone --branch "$BRANCH" "$AUTH_URL" "$MAIN_REPO" 2>&1 \
            || git clone "$AUTH_URL" "$MAIN_REPO" 2>&1; then
            echo "[session_start] Clone concluído — criando worktree e push…"
            git -C "$MAIN_REPO" rev-parse HEAD >/dev/null 2>&1 || true
            git -C "$MAIN_REPO" worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" "${BASE_BRANCH:-HEAD}" 2>&1 \
                || git -C "$MAIN_REPO" worktree add "$WORKTREE_PATH" 2>&1 \
                || mkdir -p "$WORKTREE_PATH"
            # Push da branch de sessão
            _push_session_branch "$WORKTREE_PATH" "$BRANCH_NAME" || true
        else
            echo "[session_start] ERRO: clone falhou. Criando diretório vazio como fallback."
            mkdir -p "$WORKTREE_PATH"
        fi
    else
        echo "[session_start] Sem repo git em $MAIN_REPO e sem clone_url — criando diretório vazio."
        mkdir -p "$WORKTREE_PATH"
    fi
fi

# ── Injeta CLAUDE.md no worktree ─────────────────────────────
if [ -f /app/CLAUDE.md ]; then
    cp /app/CLAUDE.md "$WORKTREE_PATH/CLAUDE.md"
    echo "[session_start] CLAUDE.md injetado em $WORKTREE_PATH"
elif [ -f "/repos/${ENV_SLUG}/CLAUDE.md" ]; then
    cp "/repos/${ENV_SLUG}/CLAUDE.md" "$WORKTREE_PATH/CLAUDE.md"
    echo "[session_start] CLAUDE.md copiado do repo principal para $WORKTREE_PATH"
fi

echo "[session_start] OK"
