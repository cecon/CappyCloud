#!/usr/bin/env bash
# Gera os patches para o openclaude a partir do repositório atual.
# Execute dentro de um container com git disponível.
set -euo pipefail

cd /tmp/oc
git config user.email 'build@cappy'
git config user.name 'build'

# ── Patch 1: grep-tool-n-alias ─────────────────────────────────────────
# Adiciona o campo 'n' como alias de '-n' no schema do GrepTool e
# normaliza show_line_numbers para aceitar ambos.

NODE_PATCH=$(cat <<'NODEEOF'
const fs = require('fs');
const file = 'src/tools/GrepTool/GrepTool.ts';
let c = fs.readFileSync(file, 'utf8');

// Hunk 1: add 'n' alias field in schema (after the '-n' block)
const H1_OLD = "    '-n': semanticBoolean(z.boolean().optional()).describe(\n      'Show line numbers in output (rg -n). Requires output_mode: \"content\", ignored otherwise. Defaults to true.',\n    ),\n    '-i': semanticBoolean(z.boolean().optional()).describe(";
const H1_NEW = "    '-n': semanticBoolean(z.boolean().optional()).describe(\n      'Show line numbers in output (rg -n). Requires output_mode: \"content\", ignored otherwise. Defaults to true.',\n    ),\n    n: semanticBoolean(z.boolean().optional()).describe(\n      'Alias for -n (line numbers). Some models send `n` instead of `-n`.',\n    ),\n    '-i': semanticBoolean(z.boolean().optional()).describe(";

if (!c.includes("'n: semanticBoolean") && !c.includes("n: semanticBoolean")) {
  if (!c.includes(H1_OLD)) { console.error('H1 needle not found'); process.exit(1); }
  c = c.replace(H1_OLD, H1_NEW);
}

// Hunk 2: rename '-n' destructuring to show_line_numbers_dash, add n: show_line_numbers_n
const H2_OLD = "      '-n': show_line_numbers = true,\n      '-i': case_insensitive = false,";
const H2_NEW = "      '-n': show_line_numbers_dash,\n      n: show_line_numbers_n,\n      '-i': case_insensitive = false,";

if (!c.includes('show_line_numbers_dash')) {
  if (!c.includes(H2_OLD)) { console.error('H2 needle not found'); process.exit(1); }
  c = c.replace(H2_OLD, H2_NEW);
}

// Hunk 3: add show_line_numbers resolution after the destructuring block
const H3_NEEDLE = "  ) {\n    const absolutePath = path ? expandPath(path) : getCwd()";
const H3_REPL = "  ) {\n    const show_line_numbers =\n      show_line_numbers_n !== undefined\n        ? show_line_numbers_n\n        : (show_line_numbers_dash ?? true)\n    const absolutePath = path ? expandPath(path) : getCwd()";

if (!c.includes('show_line_numbers_n !== undefined')) {
  if (!c.includes(H3_NEEDLE)) { console.error('H3 needle not found'); process.exit(1); }
  c = c.replace(H3_NEEDLE, H3_REPL);
}

fs.writeFileSync(file, c);
console.log('grep-tool patch applied');
NODEEOF
)

node -e "$NODE_PATCH"
git diff src/tools/GrepTool/GrepTool.ts

# ── Patch 2: auto-approve-tools ──────────────────────────────────────
# Insere verificação OPENCLAUDE_AUTO_APPROVE antes de pedir permissão ao user.
NODE_PATCH2=$(cat <<'NODEEOF2'
const fs = require('fs');
const file = 'src/grpc/server.ts';
let c = fs.readFileSync(file, 'utf8');

const needle = '              // Ask user for permission';
const insert = [
  '              // Auto-approve mode: skip prompting the client and allow immediately.',
  '              // Enabled by env var OPENCLAUDE_AUTO_APPROVE=1 (set by CappyCloud sandbox).',
  "              if (process.env.OPENCLAUDE_AUTO_APPROVE === '1') {",
  "                return { behavior: 'allow' }",
  '              }',
  '',
  '',
].join('\n');

if (!c.includes('OPENCLAUDE_AUTO_APPROVE')) {
  if (!c.includes(needle)) { console.error('server.ts needle not found'); process.exit(1); }
  c = c.replace(needle, insert + needle);
}

fs.writeFileSync(file, c);
console.log('auto-approve patch applied');
NODEEOF2
)

node -e "$NODE_PATCH2"
git diff src/grpc/server.ts
