import { lazy, Suspense, type CSSProperties } from 'react'
import type { EChartsReactProps } from 'echarts-for-react/esm/types'

const EChartRenderer = lazy(() => import('./EChartRenderer'))

type LazyEChartProps = Omit<EChartsReactProps, 'echarts'> & {
  fallbackHeight?: CSSProperties['height']
}

export function LazyEChart({
  fallbackHeight,
  style,
  ...props
}: LazyEChartProps) {
  const height = fallbackHeight ?? style?.height ?? 280

  return (
    <Suspense
      fallback={
        <div
          className="animate-pulse rounded-lg bg-muted/40"
          style={{ height }}
        />
      }
    >
      <EChartRenderer
        style={style}
        {...props}
      />
    </Suspense>
  )
}
