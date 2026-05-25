"""HTML views for MCP OAuth authorization."""

from __future__ import annotations

import html

from app.application.use_cases.mcp_oauth_clients import server_id_from_static_client_id


def render_authorize_form(params: dict[str, str]) -> str:
    hidden = "\n".join(
        f'<input type="hidden" name="{html.escape(key)}" value="{html.escape(value)}" />'
        for key, value in params.items()
    )
    resource = html.escape(params.get("resource") or "endpoint MCP")
    requires_mcp_token = server_id_from_static_client_id(params.get("client_id", "")) is None
    token_field = (
        """<label>Token MCP
        <input name="mcp_token" type="password" autocomplete="off" required autofocus />
      </label>"""
        if requires_mcp_token
        else "<p>Client ID pre-cadastrado detectado. Confirme para autorizar o acesso.</p>"
    )
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Autorizar MCP CappyCloud</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #111318; color: #f6f7fb; margin: 0; }}
    main {{ max-width: 520px; margin: 8vh auto; padding: 24px; }}
    label, input, button {{ display: block; width: 100%; box-sizing: border-box; }}
    input {{
      margin-top: 8px; padding: 12px; border-radius: 8px;
      border: 1px solid #303542; background: #090b10; color: #fff;
    }}
    button {{
      margin-top: 16px; padding: 12px; border: 0; border-radius: 8px;
      background: #4f7cff; color: white; font-weight: 700;
    }}
    p {{ color: #adb4c5; line-height: 1.5; }}
    code {{ word-break: break-all; }}
  </style>
</head>
<body>
  <main>
    <h1>Autorizar MCP CappyCloud</h1>
    <p>Informe o token gerado na página MCP Server para autorizar o Claude a acessar:</p>
    <p><code>{resource}</code></p>
    <form method="post" action="/api/mcp/oauth/authorize">
      {hidden}
      {token_field}
      <button type="submit">Autorizar Claude</button>
    </form>
  </main>
</body>
</html>"""
