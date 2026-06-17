import { useEffect, useMemo, useState } from 'react'
import {
  authorizeAgenticExternalAction,
  createAgenticCycle,
  fetchAgenticMetrics,
  fetchAgenticReviewPackage,
  fetchRepositories,
  getToken,
  prepareAgenticCycle,
  recordAgenticReviewDecision,
  runAgenticCycle,
  saveSensitiveSurface,
  searchAgenticKnowledge,
  type AgenticCycleCreatePayload,
  type AgenticCycleCreated,
  type AgenticKnowledgeItem,
  type AgenticPrepareResponse,
  type AgenticReviewPackage,
  type CycleMetric,
  type Repository,
  type SensitiveSurfacePayload,
} from '../api'
import { AgentOutputReviewList } from '../components/agentic-delivery/AgentOutputReviewList'
import { CycleLifecycleBadge } from '../components/agentic-delivery/CycleLifecycleBadge'
import { CycleCreateForm } from '../components/agentic-delivery/CycleCreateForm'
import { CycleMetricsSummary } from '../components/agentic-delivery/CycleMetricsSummary'
import { ExternalActionAuthorizationPanel } from '../components/agentic-delivery/ExternalActionAuthorizationPanel'
import { ReusableKnowledgeSearch } from '../components/agentic-delivery/ReusableKnowledgeSearch'
import { ReviewGatePanel } from '../components/agentic-delivery/ReviewGatePanel'
import { SensitiveSurfaceManager } from '../components/agentic-delivery/SensitiveSurfaceManager'
import { WorkPackageSummary } from '../components/agentic-delivery/WorkPackageSummary'
import styles from './agentic-delivery-page.module.css'

const EMPTY_CYCLE: AgenticCycleCreatePayload = {
  repository_ids: [],
  domain_key: '',
  title: 'Mudança fiscal auditável',
  business_goal: '',
  scope_boundary: '',
  expected_outputs: ['requirements', 'code_change', 'test_result'],
  acceptance_expectations: ['evidência citada', 'gates aprovados'],
  evidence_sources: [],
}

const EMPTY_SURFACE: SensitiveSurfacePayload = {
  repository_id: null,
  domain_key: '',
  name: 'Fiscal NFCe',
  description: 'Regras fiscais e documento eletrônico',
  match_rules: { path_prefixes: ['fiscal/', 'nfce/'], keywords: ['ICMS', 'IBS', 'CBS', 'NFCe'] },
  active: true,
}

export function AgenticDeliveryPage() {
  const token = getToken()!
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [cycleForm, setCycleForm] = useState<AgenticCycleCreatePayload>(EMPTY_CYCLE)
  const [cycle, setCycle] = useState<AgenticCycleCreated | null>(null)
  const [prepared, setPrepared] = useState<AgenticPrepareResponse | null>(null)
  const [review, setReview] = useState<AgenticReviewPackage | null>(null)
  const [knowledgeQuery, setKnowledgeQuery] = useState('fiscal')
  const [knowledge, setKnowledge] = useState<AgenticKnowledgeItem[]>([])
  const [surface, setSurface] = useState<SensitiveSurfacePayload>(EMPTY_SURFACE)
  const [rationale, setRationale] = useState('Gates completos e mudança pronta para PR')
  const [metrics, setMetrics] = useState<CycleMetric[]>([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const selectedRepositoryId = cycleForm.repository_ids[0] ?? null

  useEffect(() => {
    void loadRepositories()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    setSurface((prev) => ({
      ...prev,
      repository_id: selectedRepositoryId,
      domain_key: cycleForm.domain_key,
    }))
  }, [selectedRepositoryId, cycleForm.domain_key])

  const lifecycleStatus = useMemo(
    () => review?.cycle.status ?? prepared?.status ?? cycle?.status ?? null,
    [cycle?.status, prepared?.status, review?.cycle.status],
  )
  const sensitiveSurfaceActive = Boolean(surface.active && surface.name.trim())

  async function loadRepositories() {
    try {
      const list = await fetchRepositories(token)
      setRepositories(list)
      if (list[0] && cycleForm.repository_ids.length === 0) {
        setCycleForm((prev) => ({ ...prev, repository_ids: [list[0].id] }))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível carregar repositórios.')
    }
  }

  async function createAndPrepare() {
    setLoading(true)
    setError(null)
    setMessage(null)
    try {
      const created = await createAgenticCycle(token, cycleForm)
      const preparedCycle = await prepareAgenticCycle(token, created.id)
      setCycle(created)
      setPrepared(preparedCycle)
      setMessage('Ciclo criado e pacote preparado.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao criar ciclo.')
    } finally {
      setLoading(false)
    }
  }

  async function runCycle() {
    if (!cycle) return
    setLoading(true)
    try {
      await runAgenticCycle(token, cycle.id)
      setMessage('Execução iniciada em contexto review-only.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao executar ciclo.')
    } finally {
      setLoading(false)
    }
  }

  async function loadReview() {
    if (!cycle) return
    setReview(await fetchAgenticReviewPackage(token, cycle.id))
  }

  async function approveGate(gateId: string) {
    if (!cycle) return
    await recordAgenticReviewDecision(token, cycle.id, {
      review_gate_id: gateId,
      decision: 'approve',
      rationale: 'Gate aprovado na revisão.',
    })
    await loadReview()
  }

  async function searchKnowledge() {
    if (!selectedRepositoryId) return
    const result = await searchAgenticKnowledge(token, {
      repository_ids: [selectedRepositoryId],
      domain_key: cycleForm.domain_key,
      query: knowledgeQuery,
      limit: 10,
    })
    setKnowledge(result.items)
  }

  async function saveSurface() {
    await saveSensitiveSurface(token, crypto.randomUUID(), surface)
    setMessage('Superfície sensível salva.')
  }

  async function authorizeExternalAction() {
    if (!cycle) return
    await authorizeAgenticExternalAction(token, cycle.id, {
      action_type: 'pull_request',
      repository_id: selectedRepositoryId,
      domain_key: cycleForm.domain_key,
      requested_payload: { target_branch: 'main' },
      rationale,
    })
    setMessage('Ação externa autorizada.')
  }

  async function loadMetrics() {
    if (!cycle) return
    const result = await fetchAgenticMetrics(token, cycle.id)
    setMetrics(result.metrics)
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>Agentic Delivery</span>
          <h1>Factory</h1>
          <p>Fluxo de execução com revisão, evidência, isolamento por domínio e gates auditáveis.</p>
        </div>
        <div className={styles.headerActions}>
          {sensitiveSurfaceActive ? (
            <span className={styles.surfaceIndicator}>
              <span className={styles.icon}>policy</span>
              Compliance automático
            </span>
          ) : null}
          <CycleLifecycleBadge status={lifecycleStatus} />
        </div>
      </header>

      {error ? <p className={styles.error}>{error}</p> : null}
      {message ? <p className={styles.message}>{message}</p> : null}

      <section className={styles.grid}>
        <CycleCreateForm
          repositories={repositories}
          value={cycleForm}
          disabled={loading}
          onChange={setCycleForm}
          onSubmit={() => void createAndPrepare()}
        />
        <WorkPackageSummary
          cycle={cycle}
          prepared={prepared}
          disabled={loading}
          onRun={() => void runCycle()}
        />
        <ReviewGatePanel gates={review?.gates ?? []} onApprove={(gateId) => void approveGate(gateId)} />
        <AgentOutputReviewList outputs={review?.outputs ?? []} />
        <ReusableKnowledgeSearch
          query={knowledgeQuery}
          items={knowledge}
          onQueryChange={setKnowledgeQuery}
          onSearch={() => void searchKnowledge()}
        />
        <SensitiveSurfaceManager value={surface} onChange={setSurface} onSave={() => void saveSurface()} />
        <ExternalActionAuthorizationPanel
          rationale={rationale}
          onRationaleChange={setRationale}
          onAuthorize={() => void authorizeExternalAction()}
        />
        <CycleMetricsSummary metrics={metrics} />
      </section>

      <footer className={styles.footer}>
        <button className={styles.button} type="button" disabled={!cycle} onClick={() => void loadReview()}>
          <span className={styles.icon}>fact_check</span>
          Carregar revisão
        </button>
        <button className={styles.button} type="button" disabled={!cycle} onClick={() => void loadMetrics()}>
          <span className={styles.icon}>monitoring</span>
          Carregar métricas
        </button>
      </footer>
    </main>
  )
}
