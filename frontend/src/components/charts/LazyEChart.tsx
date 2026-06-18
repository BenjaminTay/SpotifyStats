import { lazy, Suspense, type CSSProperties } from 'react'
import { BarChart, HeatmapChart, LineChart, PieChart } from 'echarts/charts'
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsReactProps } from 'echarts-for-react/esm/types'

const ReactEChartsCore = lazy(() => import('echarts-for-react/esm/core'))

echarts.use([
  BarChart,
  HeatmapChart,
  LineChart,
  PieChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
])

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
      <ReactEChartsCore
        echarts={echarts}
        style={style}
        {...props}
      />
    </Suspense>
  )
}
