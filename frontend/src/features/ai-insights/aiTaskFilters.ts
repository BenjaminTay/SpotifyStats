import { getDefaultMergeLevel } from '@/lib/merge-level'

export interface AiTaskFilterPayload {
  min_ms: number
  music_only: boolean
  merge_enabled: boolean
  dynamic_threshold: boolean
  max_merge_gap_minutes: number
}

export interface ChatAgentFilterPayload extends AiTaskFilterPayload {
  merge_level: number
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === 'object' && !Array.isArray(value)
}

function parseStoredBoolean(value: string | null): boolean | null {
  if (value == null) return null
  const normalized = value.trim().toLowerCase()
  if (normalized === 'true' || normalized === '1') return true
  if (normalized === 'false' || normalized === '0') return false
  return null
}

function getStoredDynamicThreshold(): boolean | null {
  try {
    return parseStoredBoolean(localStorage.getItem('spotify_stats_dynamic_threshold'))
  } catch {
    return null
  }
}

export function getSettingsDynamicThreshold(settings: unknown): boolean {
  if (isRecord(settings) && typeof settings.dynamic_threshold === 'boolean') {
    return settings.dynamic_threshold
  }
  return getStoredDynamicThreshold() ?? true
}

export function getSettingsMaxMergeGapMinutes(settings: unknown): number {
  if (isRecord(settings) && typeof settings.max_merge_gap_minutes === 'number') {
    return settings.max_merge_gap_minutes
  }
  return 5
}

export function buildAiTaskFilterPayload(settings: unknown): AiTaskFilterPayload {
  return {
    min_ms: isRecord(settings) && typeof settings.min_ms === 'number' ? settings.min_ms : 30000,
    music_only: isRecord(settings) && typeof settings.music_only === 'boolean' ? settings.music_only : true,
    merge_enabled: isRecord(settings) && typeof settings.merge_enabled === 'boolean'
      ? settings.merge_enabled
      : true,
    dynamic_threshold: getSettingsDynamicThreshold(settings),
    max_merge_gap_minutes: getSettingsMaxMergeGapMinutes(settings),
  }
}

export function buildChatAgentFilterPayload(settings: unknown): ChatAgentFilterPayload {
  return {
    ...buildAiTaskFilterPayload(settings),
    merge_level: getDefaultMergeLevel(),
  }
}
