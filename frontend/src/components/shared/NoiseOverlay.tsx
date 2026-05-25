const NOISE_SVG =
  "data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E"

export function NoiseOverlay() {
  return (
    <div
      className="fixed inset-0 z-0 opacity-[0.035] pointer-events-none"
      style={{
        backgroundImage: `url("${NOISE_SVG}")`,
        backgroundSize: '256px 256px',
      }}
    />
  )
}
