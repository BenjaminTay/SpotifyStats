import { lazy, Suspense, type CSSProperties } from 'react'
import type { EChartsReactProps } from 'echarts-for-react/esm/types'

const EChartRenderer = lazy(() => import('./EChartRenderer'))
const LineEChartRenderer = lazy(() => import('./LineEChartRenderer'))

type LazyEChartProps = Omit<EChartsReactProps, 'echarts'> & {
  fallbackHeight?: CSSProperties['height']
  renderer?: 'full' | 'line'
}

export function LazyEChart({
  fallbackHeight,
  renderer = 'full',
  style,
  ...props
}: LazyEChartProps) {
  const height = fallbackHeight ?? style?.height ?? 280
  const Renderer = renderer === 'line' ? LineEChartRenderer : EChartRenderer

  return (
    <Suspense
      fallback={
        <div
          className="animate-pulse rounded-lg bg-muted/40"
          style={{ height }}
        />
      }
    >
      <Renderer
        style={style}
        {...props}
      />
    </Suspense>
  )
}
