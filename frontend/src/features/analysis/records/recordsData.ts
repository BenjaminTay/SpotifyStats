/** Data helpers for Playback Records. */

import type { PlaybackRecordRow, EntityRecordType } from '@/types/analysis'

/**
 * Extract a flat list of records from the nested response for a specific entity type
 * within a three-entity record family.
 */
export function getEntityRows(
  family: { track: PlaybackRecordRow[]; album: PlaybackRecordRow[]; artist: PlaybackRecordRow[] } | undefined,
  entity: EntityRecordType
): PlaybackRecordRow[] {
  if (!family) return []
  return family[entity] ?? []
}

/** Check if any entity in a family has data. */
export function familyHasData(
  family: { track: PlaybackRecordRow[]; album: PlaybackRecordRow[]; artist: PlaybackRecordRow[] } | undefined
): boolean {
  if (!family) return false
  return family.track.length > 0 || family.album.length > 0 || family.artist.length > 0
}

/** Get available entity types from a record family. */
export function getAvailableEntities(
  family: { track: PlaybackRecordRow[]; album: PlaybackRecordRow[]; artist: PlaybackRecordRow[] } | undefined
): EntityRecordType[] {
  if (!family) return []
  const available: EntityRecordType[] = []
  if (family.track.length > 0) available.push('track')
  if (family.album.length > 0) available.push('album')
  if (family.artist.length > 0) available.push('artist')
  return available
}
