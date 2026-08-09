import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent, LegendComponent, MarkLineComponent, TooltipComponent,
} from 'echarts/components'
import { use, init } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

use([
  BarChart, LineChart, GridComponent, LegendComponent, MarkLineComponent,
  TooltipComponent, CanvasRenderer,
])

export { init }
export type { EChartsType } from 'echarts/core'
