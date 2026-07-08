#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# /session_start.sh — Cria um git worktree por sessão de conversa
#
# Uso:  /session_start.sh <slug> <session_id> <worktree_path> [base_branch] [branch_name] [clone_url]
#
# Fluxo:
#   1. Repo principal fica em /repos/<slug>
#   2. Cria worktree em <worktree_path> na branch cappy/<slug>/<session_id>
#   3. Branch é criada a partir de <base_branch>, commit SHA de baseline
#      limpo, ou da default detectada
#   4. Por padrão, mantém a branch apenas local. Push automático só se
#      CAPPYCLOUD_AUTO_PUSH_SESSION_BRANCH=true.
#   5. Idempotente: se o worktree já existe, reutiliza
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
AUTO_PUSH_SESSION_BRANCH="${CAPPYCLOUD_AUTO_PUSH_SESSION_BRANCH:-false}"

echo "[session_start] slug=${ENV_SLUG}  session=${SESSION_ID}  worktree=${WORKTREE_PATH}  base=${BASE_BRANCH:-auto}  branch=${BRANCH_NAME}"

mkdir -p "$(dirname "$WORKTREE_PATH")"

# ── Helper: overlay .sendbox/ → .claude/ na worktree ─────────
# .sendbox fica versionado no clone principal do repo e é copiado como
# configuração local da sessão. Copiamos apenas arquivos regulares para evitar
# symlinks apontando para fora do repo/sessão.
_copy_regular_tree() {
    local src="$1"
    local dest="$2"
    [ -d "$src" ] || return 0
    mkdir -p "$dest"
    (
        cd "$src"
        find . -type f -print0
    ) | while IFS= read -r -d '' rel; do
        rel="${rel#./}"
        mkdir -p "$(dirname "$dest/$rel")"
        cp -p "$src/$rel" "$dest/$rel"
    done
}

_exclude_injected_claude_dirs() {
    local worktree_path="$1"
    local exclude_file
    exclude_file=$(git -C "$worktree_path" rev-parse --git-path info/exclude 2>/dev/null || true)
    [ -n "$exclude_file" ] || return 0
    mkdir -p "$(dirname "$exclude_file")"
    touch "$exclude_file"
    for pattern in ".claude/skills/" ".claude/commands/" ".claude/agents/"; do
        grep -qxF "$pattern" "$exclude_file" || echo "$pattern" >> "$exclude_file"
    done
}

_inject_sendbox_overlay() {
    local main_repo="$1"
    local worktree_path="$2"
    local overlay_dir="${main_repo}/.sendbox"
    [ -d "$overlay_dir" ] || return 0

    local injected=()
    if [ -d "$overlay_dir/skills" ]; then
        _copy_regular_tree "$overlay_dir/skills" "$worktree_path/.claude/skills"
        injected+=("skills")
    fi
    if [ -d "$overlay_dir/commands" ]; then
        _copy_regular_tree "$overlay_dir/commands" "$worktree_path/.claude/commands"
        injected+=("commands")
    fi
    if [ -d "$overlay_dir/agents" ]; then
        _copy_regular_tree "$overlay_dir/agents" "$worktree_path/.claude/agents"
        injected+=("agents")
    fi

    if [ "${#injected[@]}" -gt 0 ]; then
        _exclude_injected_claude_dirs "$worktree_path"
        echo "[session_start] .sendbox overlay injetado em .claude/: ${injected[*]}"
    fi
}

# ── Idempotente: worktree saudável já existe ──────────────────
if [ -d "$WORKTREE_PATH/.git" ] || [ -f "$WORKTREE_PATH/.git" ]; then
    echo "[session_start] Worktree já existe — reutilizando."
    _inject_sendbox_overlay "$MAIN_REPO" "$WORKTREE_PATH" || true
    exit 0
fi

# ── Pasta órfã (existe mas sem .git) ──────────────────────────
# Aparece quando a sessão foi destruída parcialmente (ex.: watchdog
# apagou conteúdo mas deixou a pasta, ou alguém criou /repos/sessions/<id>/<alias>
# fora do fluxo normal). git worktree add recusa pasta de destino existente,
# o que provoca o agente a entrar num diretório vazio e responder
# "não há código X" — o famoso falso-negativo.
if [ -d "$WORKTREE_PATH" ]; then
    echo "[session_start] Pasta órfã em ${WORKTREE_PATH} — removendo antes de recriar worktree."
    rm -rf "$WORKTREE_PATH"
fi

# ── Worktree órfão no registry do bare repo ───────────────────
# Se o git ainda conhece a worktree (mas a pasta foi apagada),
# bloqueia novo `worktree add`. prune limpa entradas mortas.
if [ -d "$MAIN_REPO/.git" ] || [ -d "$MAIN_REPO" ]; then
    git -C "$MAIN_REPO" worktree prune 2>/dev/null || true
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

# ── Helper: busca a branch base com a URL autenticada da sessão ─
_fetch_base_branch() {
    local repo_dir="$1"
    local branch="$2"
    local remote="origin"

    if [ -n "${CLONE_URL}" ]; then
        remote=$(_auth_url "$CLONE_URL")
    fi

    git -C "$repo_dir" fetch "$remote" \
        "+refs/heads/${branch}:refs/remotes/origin/${branch}" 2>&1
}

# ── Helper: push não-fatal ────────────────────────────────────
_push_session_branch() {
    case "$(echo "$AUTO_PUSH_SESSION_BRANCH" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|on) ;;
        *)
            echo "[session_start] Push automático desativado — branch ${2} permanece local."
            return 0
            ;;
    esac

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

    # Resolve a base: usa a branch fornecida, um commit SHA derivado de
    # baseline limpo, ou detecta a default.
    local resolved_base="${base_branch:-}"

    if [ -n "$resolved_base" ]; then
        # Atualiza a branch base usando a URL autenticada do cadastro quando
        # disponível. Em repos dinâmicos, o clone do volume pode ter um origin
        # antigo/sem token; a clone_url da sessão é a fonte confiável.
        echo "[session_start] Buscando ${resolved_base} no remote…"
        _fetch_base_branch "$main_repo" "$resolved_base" || true

        local remote_base="refs/remotes/origin/${resolved_base}"
        if git -C "$main_repo" rev-parse --verify "$remote_base" >/dev/null 2>&1; then
            resolved_base="$remote_base"
        elif ! git -C "$main_repo" rev-parse --verify "$resolved_base" >/dev/null 2>&1; then
            echo "[session_start] AVISO: ${resolved_base} não encontrada."
            resolved_base=$(_default_branch "$main_repo")
            echo "[session_start] Branch default detectada: ${resolved_base}"
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

# ── .sendbox/ overlay (commands/agents/skills do próprio repo) ──
_inject_sendbox_overlay "$MAIN_REPO" "$WORKTREE_PATH" || true

echo "[session_start] OK — worktree=${WORKTREE_PATH}  branch=${BRANCH_NAME}"
