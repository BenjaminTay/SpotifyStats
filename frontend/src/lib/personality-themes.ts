export interface PersonalityTheme {
  name: string
  color: string
  bgStart: string
  bgEnd: string
  accent: string
}

export const PERSONALITY_THEMES: Record<string, PersonalityTheme> = {
  '环球旅人': { name: '环球旅人', color: '#1e40af', bgStart: '#1e3a5f', bgEnd: '#0f172a', accent: '#3b82f6' },
  '深度鉴赏家': { name: '深度鉴赏家', color: '#b45309', bgStart: '#3d1f0a', bgEnd: '#1c0f05', accent: '#d97706' },
  '能量引擎': { name: '能量引擎', color: '#dc2626', bgStart: '#3f1515', bgEnd: '#1f0a0a', accent: '#ef4444' },
  '午夜诗人': { name: '午夜诗人', color: '#6d28d9', bgStart: '#2a1550', bgEnd: '#150a28', accent: '#8b5cf6' },
  '潮流捕手': { name: '潮流捕手', color: '#059669', bgStart: '#133a2e', bgEnd: '#0a1f17', accent: '#10b981' },
  '忠实灯塔': { name: '忠实灯塔', color: '#b8860b', bgStart: '#3d2e0f', bgEnd: '#1f1708', accent: '#eab308' },
}

export function getPersonalityTheme(label: string): PersonalityTheme {
  return PERSONALITY_THEMES[label] ?? PERSONALITY_THEMES['环球旅人']
}
