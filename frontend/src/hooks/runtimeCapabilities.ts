export type RuntimeCapability =
  | 'settings'
  | 'editing'
  | 'imports'
  | 'ai'
  | 'spotify_oauth'
  | 'lyrics'
  | 'metadata_governance'
  | 'yearly_generation'
  | 'community_write'
  | 'cover_enrichment'

export interface RuntimeCapabilities {
  surface: 'private-admin' | 'public-readonly'
  profile: 'full' | 'showcase'
  policy_version: string
  release_sha: string
  settings: boolean
  editing: boolean
  imports: boolean
  ai: boolean
  spotify_oauth: boolean
  lyrics: boolean
  metadata_governance: boolean
  yearly_generation: boolean
  community_write: boolean
  cover_enrichment: boolean
}

export const FULL_CAPABILITIES: RuntimeCapabilities = {
  surface: 'private-admin',
  profile: 'full',
  policy_version: 'development',
  release_sha: 'development',
  settings: true,
  editing: true,
  imports: true,
  ai: true,
  spotify_oauth: true,
  lyrics: true,
  metadata_governance: true,
  yearly_generation: true,
  community_write: true,
  cover_enrichment: true,
}

export const PUBLIC_CAPABILITIES: RuntimeCapabilities = {
  surface: 'public-readonly',
  profile: 'showcase',
  policy_version: 'unknown',
  release_sha: 'unknown',
  settings: false,
  editing: false,
  imports: false,
  ai: false,
  spotify_oauth: false,
  lyrics: false,
  metadata_governance: false,
  yearly_generation: false,
  community_write: false,
  cover_enrichment: false,
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

/** Missing or malformed flags always fail closed. */
export function normalizeRuntimeCapabilities(value: unknown): RuntimeCapabilities {
  if (!isRecord(value)) return PUBLIC_CAPABILITIES
  const flags = isRecord(value.capabilities) ? value.capabilities : value
  const surface = value.surface === 'private-admin' ? 'private-admin' : 'public-readonly'
  const enabled = (key: RuntimeCapability) => flags[key] === true

  return {
    surface,
    profile: value.profile === 'full' || value.profile === 'showcase'
      ? value.profile
      : surface === 'private-admin' ? 'full' : 'showcase',
    policy_version: typeof value.policy_version === 'string' ? value.policy_version : 'unknown',
    release_sha: typeof value.release_sha === 'string' ? value.release_sha : 'unknown',
    settings: enabled('settings'),
    editing: enabled('editing'),
    imports: enabled('imports'),
    ai: enabled('ai'),
    spotify_oauth: enabled('spotify_oauth'),
    lyrics: enabled('lyrics'),
    metadata_governance: enabled('metadata_governance'),
    yearly_generation: enabled('yearly_generation'),
    community_write: enabled('community_write'),
    cover_enrichment: enabled('cover_enrichment'),
  }
}

export function hasRuntimeCapabilities(
  capabilities: RuntimeCapabilities,
  required: RuntimeCapability | readonly RuntimeCapability[],
): boolean {
  const keys: readonly RuntimeCapability[] = typeof required === 'string' ? [required] : required
  return keys.every((key) => capabilities[key])
}
