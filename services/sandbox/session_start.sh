#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# /session_start.sh — Cria um git worktree por sessão de conversa
#
# Uso:  /session_start.sh <slug> <session_id> <worktree_path> [base_branch] [branch_name] [clone_url]
#
# Fluxo:
#   1. Repo principal fica em /repos/<slug>
#   2. Cria worktree em <worktree_path> na branch cappy/<slug>/<session_id>
#   3. Branch é criada a partir de <base_branch> (ou da default detectada)
#   4. Idempotente: se o worktree já existe, reutiliza
#
# Tokens de autenticação herdados do ambiente do container:
#   DEVOPS_TOKEN  → Azure DevOps
#   GITHUB_TOKEN  → GitHub
# ──────────────────────────────────────────────────────────────
set -euo pipefail

ENV_SLUG="${1:?Usage: session_start.sh <slug> <session_id> <worktree_path> [base_branch] [branch_name] [clone_url]}"
SESSION_ID="${2:?}"
WORKTREE_PATH="${3:?}"
BASE_BRANCH="${4:-}"
BRANCH_NAME="${5:-cappy/${ENV_SLUG}/${SESSION_ID}}"
CLONE_URL="${6:-}"
MAIN_REPO="/repos/${ENV_SLUG}"

DEVOPS_TOKEN="${DEVOPS_TOKEN:-}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

echo "[session_start] slug=${ENV_SLUG}  session=${SESSION_ID}  worktree=${WORKTREE_PATH}  base=${BASE_BRANCH:-auto}  branch=${BRANCH_NAME}"

mkdir -p "$(dirname "$WORKTREE_PATH")"

# ── Idempotente: worktree já existe ───────────────────────────
if [ -d "$WORKTREE_PATH/.git" ] || [ -f "$WORKTREE_PATH/.git" ]; then
    echo "[session_start] Worktree já existe — reutilizando."
    exit 0
fi

# ── Helper: detecta a branch default real do repo ─────────────
_default_branch() {
    local repo_dir="$1"
    # Tenta via remote HEAD (mais confiável)
    local br
    br=$(git -C "$repo_dir" remote show origin 2>/dev/null \
        | grep "HEAD branch:" | sed 's/.*HEAD branch:[[:space:]]*//' | tr -d '[:space:]') || true
    if [ -z "$br" ] || [ "$br" = "(unknown)" ]; then
        # Fallback: branch atual do repo principal
        br=$(git -C "$repo_dir" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    fi
    # Último fallback
    echo "${br:-master}"
}

# ── Helper: URL autenticada ───────────────────────────────────
_auth_url() {
    local url="$1"
    if [ -n "${GITHUB_TOKEN}" ]; then
        url=$(echo "$url" | sed \
            "s|https://github.com|https://x-token:${GITHUB_TOKEN}@github.com|" | sed \
            "s|https://x-token:.*@github.com@github.com|https://x-token:${GITHUB_TOKEN}@github.com|")
    fi
    if [ -n "${DEVOPS_TOKEN}" ]; then
        url=$(echo "$url" | sed \
            "s|https://dev.azure.com|https://pat:${DEVOPS_TOKEN}@dev.azure.com|")
    fi
    echo "$url"
}

# ── Helper: push não-fatal ────────────────────────────────────
_push_session_branch() {
    local repo_dir="$1"
    local branch="$2"
    local remote_url
    remote_url=$(git -C "$repo_dir" remote get-url origin 2>/dev/null || true)
    [ -z "$remote_url" ] && return 0
    local auth_url
    auth_url=$(_auth_url "$remote_url")
    echo "[session_start] Push ${branch}…"
    git -C "$repo_dir" push "$auth_url" "${branch}:${branch}" --set-upstream 2>&1 \
        && echo "[session_start] Push OK: ${branch}" \
        || echo "[session_start] AVISO: push falhou — branch apenas local."
}

# ── Cria o worktree ───────────────────────────────────────────
_create_worktree() {
    local main_repo="$1"
    local worktree_path="$2"
    local branch_name="$3"
    local base_branch="$4"

    # Resolve a branch base: usa a fornecida ou detecta a default
    local resolved_base="${base_branch:-}"

    if [ -n "$resolved_base" ]; then
        # Verifica se a branch base existe localmente
        if ! git -C "$main_repo" rev-parse --verify "$resolved_base" >/dev/null 2>&1; then
            echo "[session_start] Buscando ${resolved_base} no remote…"
            git -C "$main_repo" fetch origin "${resolved_base}:${resolved_base}" 2>&1 || true
            # Se ainda não existe, detecta a default real
            if ! git -C "$main_repo" rev-parse --verify "$resolved_base" >/dev/null 2>&1; then
                echo "[session_start] AVISO: ${resolved_base} não encontrada."
                resolved_base=$(_default_branch "$main_repo")
                echo "[session_start] Branch default detectada: ${resolved_base}"
            fi
        fi
    else
        resolved_base=$(_default_branch "$main_repo")
        echo "[session_start] Branch base detectada automaticamente: ${resolved_base}"
    fi

    echo "[session_start] Criando worktree: branch=${branch_name} a partir de ${resolved_base}"

    # Tenta criar nova branch a partir da base
    if git -C "$main_repo" worktree add -b "$branch_name" "$worktree_path" "$resolved_base" 2>&1; then
        echo "[session_start] Worktree criado com nova branch ${branch_name}"
        return 0
    fi

    # A branch pode já existir (retry da mesma sessão) — checkout direto
    if git -C "$main_repo" rev-parse --verify "$branch_name" >/dev/null 2>&1; then
        echo "[session_start] Branch ${branch_name} já existe — checkout direto."
        if git -C "$main_repo" worktree add "$worktree_path" "$branch_name" 2>&1; then
            return 0
        fi
    fi

    echo "[session_start] ERRO: worktree add falhou para ${branch_name}."
    return 1
}

# ── Main: repo já clonado ─────────────────────────────────────
if [ -d "$MAIN_REPO/.git" ]; then
    # Garante HEAD válido
    if ! git -C "$MAIN_REPO" rev-parse HEAD >/dev/null 2>&1; then
        echo "[session_start] Repo sem commits — criando commit inicial..."
        git -C "$MAIN_REPO" config user.email "agent@cappycloud.local"
        git -C "$MAIN_REPO" config user.name "CappyCloud Agent"
        git -C "$MAIN_REPO" commit --allow-empty -m "init"
    fi

    _create_worktree "$MAIN_REPO" "$WORKTREE_PATH" "$BRANCH_NAME" "$BASE_BRANCH"
    _push_session_branch "$WORKTREE_PATH" "$BRANCH_NAME" || true

# ── Main: repo não clonado — clona primeiro ──────────────────
else
    RESOLVED_URL="${CLONE_URL:-}"

    if [ -z "$RESOLVED_URL" ] && [ -n "${WORKSPACE_REPOS:-}" ]; then
        IFS=',' read -ra _REPOS <<< "${WORKSPACE_REPOS}"
        for _r in "${_REPOS[@]}"; do
            _r=$(echo "$_r" | tr -d '[:space:]')
            _slug=$(basename "$_r" | sed 's/\.git$//')
            if [ "$_slug" = "$ENV_SLUG" ]; then
                RESOLVED_URL="$_r"
                break
            fi
        done
    fi

    if [ -n "$RESOLVED_URL" ]; then
        echo "[session_start] Clonando ${ENV_SLUG} de ${RESOLVED_URL}…"
        AUTH_URL=$(_auth_url "$RESOLVED_URL")
        CLONE_BRANCH="${BASE_BRANCH:-}"
        mkdir -p "$MAIN_REPO"
        if [ -n "$CLONE_BRANCH" ]; then
            git clone --branch "$CLONE_BRANCH" "$AUTH_URL" "$MAIN_REPO" 2>&1 \
                || git clone "$AUTH_URL" "$MAIN_REPO" 2>&1 \
                || { echo "[session_start] ERRO: clone falhou."; exit 1; }
        else
            git clone "$AUTH_URL" "$MAIN_REPO" 2>&1 \
                || { echo "[session_start] ERRO: clone falhou."; exit 1; }
        fi
        echo "[session_start] Clone concluído."
        _create_worktree "$MAIN_REPO" "$WORKTREE_PATH" "$BRANCH_NAME" "$BASE_BRANCH"
        _push_session_branch "$WORKTREE_PATH" "$BRANCH_NAME" || true
    else
        echo "[session_start] ERRO: sem repo em ${MAIN_REPO} e sem clone_url."
        exit 1
    fi
fi

# ── CLAUDE.md ─────────────────────────────────────────────────
# Prioridade: o ficheiro do próprio repo (seja CLAUDE.md ou AGENTS.md)
# vence sempre. Só copiamos o template genérico do CappyCloud quando o repo
# não tem nenhum desses ficheiros — assim não sobrescrevemos instruções do
# utilizador nem confundimos o agente com o manual do CappyCloud.
if [ -f "$WORKTREE_PATH/CLAUDE.md" ] || [ -f "$WORKTREE_PATH/AGENTS.md" ]; then
    echo "[session_start] CLAUDE.md/AGENTS.md do repo preservado."
elif [ -f /app/CLAUDE.md ]; then
    cp /app/CLAUDE.md "$WORKTREE_PATH/CLAUDE.md"
fi

echo "[session_start] OK — worktree=${WORKTREE_PATH}  branch=${BRANCH_NAME}"
