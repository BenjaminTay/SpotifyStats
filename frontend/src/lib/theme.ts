export const CHART_COLORS_LIGHT = [
  'oklch(0.563 0.18 28.2)',
  'oklch(0.583 0.108 51.4)',
  'oklch(0.623 0.14 79.9)',
  'oklch(0.443 0.065 151.5)',
  'oklch(0.425 0.095 267.8)',
  'oklch(0.47 0.06 330)',
] as const

export const CHART_COLORS_DARK = [
  'oklch(0.632 0.12 35.1)',
  'oklch(0.598 0.105 39.8)',
  'oklch(0.697 0.125 73.5)',
  'oklch(0.615 0.08 138)',
  'oklch(0.635 0.08 257)',
  'oklch(0.58 0.06 330)',
] as const

export function getChartColors(isDark: boolean): readonly string[] {
  return isDark ? CHART_COLORS_DARK : CHART_COLORS_LIGHT
}
