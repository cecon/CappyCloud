import { useEffect } from 'react'
import {
  AuthError,
  fetchAiModels,
  fetchConversations,
  fetchSandboxes,
  fetchUserPreferences,
  fetchWorkspaces,
  redirectToLogin,
} from '../../api'
import { normalizeExecutionProfile, normalizePermissionMode } from './permissionOptions'
import { defaultTextModelId, validModelId } from './preferences'
import type { ChatPageState } from './useChatPageState'

/**
 * Carga inicial: conversas, repositórios, modelos, preferências e sandboxes.
 * Setters e refs têm identidade estável; estão nas deps só para o lint.
 */
export function useChatBootstrap(st: ChatPageState, token: string) {
  const {
    chatPrefsRef, setExecutionProfileState, setUserDefaultPermissionMode, setPermissionModeState,
    setWorkspaces, setSelectedSlug, setSelectedBranch, setModels, setSelectedModelId,
    setConversations, setActiveId, setSandboxes, setLoading,
  } = st

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [convsResult, wsList, modelsList, userPrefsResult, sandboxesResult] = await Promise.allSettled([
          fetchConversations(token),
          fetchWorkspaces(token),
          fetchAiModels(token),
          fetchUserPreferences(token),
          fetchSandboxes(token),
        ])
        if (cancelled) return

        const prefs = chatPrefsRef.current
        let preferredSlug = prefs.lastRepoSlug || ''
        setExecutionProfileState(normalizeExecutionProfile(prefs.executionProfile))

        if (userPrefsResult.status === 'fulfilled') {
          const mode = normalizePermissionMode(userPrefsResult.value.default_permission_mode)
          setUserDefaultPermissionMode(mode)
          setPermissionModeState(mode)
        } else if (userPrefsResult.reason instanceof AuthError) {
          redirectToLogin()
          return
        }

        if (wsList.status === 'fulfilled') {
          setWorkspaces(wsList.value)
          if (preferredSlug && !wsList.value.some((workspace) => workspace.slug === preferredSlug)) {
            preferredSlug = ''
          }
          if (preferredSlug) {
            setSelectedSlug(preferredSlug)
            setSelectedBranch(prefs.byRepo?.[preferredSlug]?.branch || '')
          }
        } else if (wsList.reason instanceof AuthError) {
          redirectToLogin()
          return
        }

        if (modelsList.status === 'fulfilled') {
          const ms = modelsList.value
          setModels(ms)
          const preferredModel =
            validModelId(ms, preferredSlug ? prefs.byRepo?.[preferredSlug]?.modelId : undefined) ||
            validModelId(ms, prefs.lastModelId) ||
            defaultTextModelId(ms)
          if (preferredModel) setSelectedModelId(preferredModel)
        }

        if (convsResult.status === 'fulfilled') {
          setConversations(convsResult.value)
          if (convsResult.value.length > 0) setActiveId((prev) => prev ?? convsResult.value[0].id)
        } else if (convsResult.reason instanceof AuthError) {
          redirectToLogin()
          return
        }

        if (sandboxesResult.status === 'fulfilled') {
          setSandboxes(sandboxesResult.value)
        } else if (sandboxesResult.reason instanceof AuthError) {
          redirectToLogin()
          return
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [
    token, chatPrefsRef, setExecutionProfileState, setUserDefaultPermissionMode, setPermissionModeState,
    setWorkspaces, setSelectedSlug, setSelectedBranch, setModels, setSelectedModelId,
    setConversations, setActiveId, setSandboxes, setLoading,
  ])
}
