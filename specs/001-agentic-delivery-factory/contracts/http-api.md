# HTTP API Contract: Agentic Delivery Factory

Base path: `/api/agentic-cycles`

All endpoints require the authenticated user. Admins may observe across users where existing admin rules allow, but repository/domain authorization still applies to knowledge retrieval. Sensitive surface management requires either platform admin rights or an active `manage_sensitive_surfaces` agentic delivery permission for the affected repository/domain. External action authorization requires an active `authorize_external_action` agentic delivery permission; ordinary repository visibility is not sufficient.

## Create Cycle

`POST /api/agentic-cycles`

**Request**

```json
{
  "conversation_id": "uuid-or-null",
  "repository_ids": ["uuid"],
  "domain_key": "autosystem",
  "title": "Revisar fluxo fiscal NFCe",
  "business_goal": "Preparar mudança fiscal com revisão auditável",
  "scope_boundary": "Somente cálculo e emissão NFCe do ERP A",
  "expected_outputs": ["requirements", "code_change", "test_result"],
  "acceptance_expectations": ["evidência citada", "gates aprovados"],
  "evidence_sources": [
    {
      "source_type": "external_doc",
      "title": "PDF McKinsey",
      "source_url": "file-or-url",
      "scope_note": "Estratégia de entrega agentic"
    }
  ]
}
```

**Response `201`**

```json
{
  "id": "uuid",
  "status": "Draft",
  "required_gates": ["product", "architecture", "quality"],
  "created_at": "2026-06-16T10:00:00Z"
}
```

**Errors**
- `400`: missing required cycle fields
- `403`: user lacks repository/domain access

## Prepare Work Package

`POST /api/agentic-cycles/{cycle_id}/prepare`

Creates or replaces the latest structured work package and moves a valid cycle to `Ready`.

**Response `200`**

```json
{
  "cycle_id": "uuid",
  "status": "Ready",
  "work_package_id": "uuid",
  "missing_inputs": [],
  "required_gates": ["product", "architecture", "quality", "compliance"]
}
```

## Start Agent Execution

`POST /api/agentic-cycles/{cycle_id}/run`

Starts agent execution in the selected sandbox/worktree context and moves the cycle to `Running`.

**Request**

```json
{
  "model_id": "provider/model",
  "execution_window": "overnight"
}
```

**Response `202`**

```json
{
  "cycle_id": "uuid",
  "status": "Running",
  "agent_task_id": "uuid"
}
```

**Errors**
- `403`: user lacks cycle repository/domain access or model access
- `409`: cycle is not `Ready`, required work package is missing, or another run is active

## Get Review Package

`GET /api/agentic-cycles/{cycle_id}/review?outputs_limit=50&outputs_cursor=...&decisions_limit=20&decisions_cursor=...`

**Response `200`**

```json
{
  "cycle": {
    "id": "uuid",
    "status": "Review",
    "title": "Revisar fluxo fiscal NFCe"
  },
  "work_package": {
    "id": "uuid",
    "version": 1,
    "review_criteria": ["evidência citada"]
  },
  "outputs": [
    {
      "id": "uuid",
      "output_type": "code_change",
      "title": "Mudança preparada",
      "validation_status": "passed",
      "unsupported_claims_count": 0,
      "evidence_links": [
        {
          "evidence_source_id": "uuid",
          "claim_summary": "A alteração cobre a regra fiscal descrita",
          "support_status": "supported"
        }
      ]
    }
  ],
  "gates": [
    {
      "id": "uuid",
      "gate_type": "quality",
      "status": "pending",
      "required": true
    }
  ],
  "metrics": [
    {
      "metric_name": "duration_minutes",
      "metric_value": 42,
      "metric_unit": "minutes"
    }
  ],
  "outputs_next_cursor": null,
  "decisions_next_cursor": null
}
```

## Record Review Decision

`POST /api/agentic-cycles/{cycle_id}/review-decisions`

**Request**

```json
{
  "agent_output_id": "uuid-or-null",
  "review_gate_id": "uuid-or-null",
  "decision": "approve",
  "rationale": "Cobertura e evidências suficientes"
}
```

**Response `201`**

```json
{
  "id": "uuid",
  "cycle_id": "uuid",
  "decision": "approve",
  "cycle_status": "Review"
}
```

## Transition Cycle

`POST /api/agentic-cycles/{cycle_id}/transition`

**Request**

```json
{
  "to_status": "Approved",
  "reason": "Todos os gates aprovados"
}
```

**Response `200`**

```json
{
  "cycle_id": "uuid",
  "from_status": "Review",
  "to_status": "Approved"
}
```

**Errors**
- `409`: invalid transition or incomplete required gates

## Search Reusable Knowledge

`POST /api/agentic-cycles/knowledge/search`

Search is pre-filtered by authorized repository/domain before candidate content is returned.

**Request**

```json
{
  "repository_ids": ["uuid"],
  "domain_key": "autosystem",
  "query": "parametrização NFCe",
  "limit": 10,
  "cursor": null
}
```

**Response `200`**

```json
{
  "items": [
    {
      "id": "uuid",
      "repository_id": "uuid",
      "domain_key": "autosystem",
      "knowledge_type": "decision",
      "title": "Regra fiscal validada",
      "needs_review": false
    }
  ],
  "next_cursor": null
}
```

## Manage Agentic Delivery Permission

`PUT /api/admin/agentic-delivery/permissions/{permission_id}`

Grants, updates, disables, or reactivates a privileged agentic delivery permission. This endpoint is platform-admin only.

**Request**

```json
{
  "user_id": "uuid",
  "repository_id": "uuid-or-null",
  "domain_key": "autosystem",
  "permission": "authorize_external_action",
  "active": true
}
```

**Response `200`**

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "repository_id": "uuid-or-null",
  "domain_key": "autosystem",
  "permission": "authorize_external_action",
  "active": true
}
```

**Errors**
- `403`: user is not a platform admin
- `422`: neither repository nor domain scope was provided, or permission value is invalid

## List Sensitive Surfaces

`GET /api/agentic-cycles/sensitive-surfaces?repository_id={uuid}&domain_key=autosystem&limit=50&cursor=...`

**Response `200`**

```json
{
  "items": [
    {
      "id": "uuid",
      "repository_id": "uuid",
      "domain_key": "autosystem",
      "name": "Fiscal NFCe",
      "description": "Regras fiscais e documento eletrônico",
      "active": true
    }
  ],
  "next_cursor": null
}
```

## Create or Update Sensitive Surface

`PUT /api/agentic-cycles/sensitive-surfaces/{surface_id}`

**Request**

```json
{
  "repository_id": "uuid",
  "domain_key": "autosystem",
  "name": "Fiscal NFCe",
  "description": "Regras fiscais e documento eletrônico",
  "match_rules": {
    "path_prefixes": ["fiscal/", "nfce/"],
    "keywords": ["ICMS", "IBS", "CBS", "NFCe"]
  },
  "active": true
}
```

**Response `200`**

```json
{
  "id": "uuid",
  "active": true
}
```

**Errors**
- `403`: user lacks platform admin rights or `manage_sensitive_surfaces` permission for the repository/domain
- `422`: match rules are invalid

## Authorize External Action

`POST /api/agentic-cycles/{cycle_id}/external-actions/authorize`

Permission and gate completion are rechecked server-side at execution boundary.

**Request**

```json
{
  "action_type": "pull_request",
  "repository_id": "uuid",
  "domain_key": "autosystem",
  "requested_payload": {
    "target_branch": "main"
  },
  "rationale": "Gates completos e mudança pronta para PR"
}
```

**Response `201`**

```json
{
  "id": "uuid",
  "cycle_id": "uuid",
  "execution_status": "authorized"
}
```

**Errors**
- `403`: user lacks `authorize_external_action` permission for the repository/domain
- `409`: required gates incomplete or cycle not approved

## Get Cycle Metrics

`GET /api/agentic-cycles/{cycle_id}/metrics?limit=50&cursor=...`

**Response `200`**

```json
{
  "cycle_id": "uuid",
  "metrics": [
    {
      "metric_name": "rework_count",
      "metric_value": 1,
      "metric_unit": "count",
      "source": "system"
    }
  ],
  "next_cursor": null
}
```
