# Manual Smoke Checklist

## Chat Command UX

- [ ] Empty composer `/` opens suggestions within 2 seconds.
- [ ] `/mod` filters to matching command names or descriptions within 150 ms.
- [ ] Slash in ordinary URL/path/prose does not open suggestions.
- [ ] Multiline pasted content beginning with `/` is preserved and does not execute automatically.
- [ ] Selecting an unavailable terminal-only command shows a Portuguese reason and does not send plain text accidentally.
- [ ] Selecting a command with required arguments shows argument guidance before execution.
- [ ] State-changing commands show inline confirmation before execution.
- [ ] Cancelling confirmation leaves the draft understandable and does not call the runtime.

## Existing Chat States

- [ ] Pending action-required prompt remains visible while suggestions open and close.
- [ ] Attachment tray remains visible and attached files are preserved.
- [ ] Selected model and permission mode remain visible.
- [ ] Runtime warning, send action and stop action remain reachable.
- [ ] Normal streamed answer still renders text.
- [ ] Tool start/result/error still render in the timeline.
- [ ] Cancellation state remains clear.
- [ ] Retry or timeout state remains clear.
- [ ] Model fallback notice remains visible when present.
- [ ] Usage and cost still render from provider-returned usage.

## Gate Evidence

- Python compile check for new backend/agent modules: pass on 2026-07-21 using the bundled Codex Python runtime.
- Backend pytest/ruff/mypy gates: blocked locally because `.venv\Scripts\python.exe` points to missing `C:\Users\cecon\AppData\Roaming\uv\python\cpython-3.14.3-windows-x86_64-none\python.exe`, `pytest` is not on PATH, and the bundled Python runtime does not include pytest.
- Frontend `pnpm run lint`: pass on 2026-07-21.
- Frontend `pnpm run build`: pass on 2026-07-21.
- Sandbox build/smoke: pass for image build, runtime status, gRPC startup log and post-entrypoint helper inspection on 2026-07-21; full chat/tool/action/cancel smoke remains pending because it requires a live provider key and authenticated app stack.
