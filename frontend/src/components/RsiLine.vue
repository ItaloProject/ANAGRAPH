<template>
  <div ref="el" style="width:100%;" :style="{ height: height + 'px' }" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { createChart, LineStyle, ColorType } from 'lightweight-charts'

const props = defineProps<{ height?: number }>()
const el = ref<HTMLElement | null>(null)

onMounted(() => {
  if (!el.value) return
  const chart = createChart(el.value, {
    width: el.value.clientWidth,
    height: props.height ?? 100,
    layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#8A9BBE' },
    grid: { vertLines: { color: 'rgba(0,212,255,0.05)' }, horzLines: { color: 'rgba(0,212,255,0.05)' } },
    rightPriceScale: { borderColor: 'rgba(0,212,255,0.1)', textColor: '#8A9BBE', scaleMargins: { top: 0.1, bottom: 0.1 } },
    timeScale: { borderColor: 'rgba(0,212,255,0.1)', textColor: '#8A9BBE', timeVisible: true },
  })

  const line = chart.addLineSeries({ color: '#FFB800', lineWidth: 2 })

  // Oversold / overbought lines
  const over = chart.addLineSeries({ color: 'rgba(0,255,136,0.3)', lineWidth: 1, lineStyle: LineStyle.Dashed })
  const under = chart.addLineSeries({ color: 'rgba(255,68,102,0.3)', lineWidth: 1, lineStyle: LineStyle.Dashed })

  const now = Math.floor(Date.now() / 1000)
  const rsiData = []
  let v = 50
  for (let i = 100; i >= 0; i--) {
    v = Math.max(5, Math.min(95, v + (Math.random() - 0.48) * 5))
    rsiData.push({ time: (now - i * 60) as any, value: v })
  }
  line.setData(rsiData)
  over.setData([{ time: rsiData[0].time, value: 70 }, { time: rsiData[rsiData.length - 1].time, value: 70 }])
  under.setData([{ time: rsiData[0].time, value: 30 }, { time: rsiData[rsiData.length - 1].time, value: 30 }])
  chart.timeScale().fitContent()

  const ro = new ResizeObserver(() => {
    if (el.value) chart.resize(el.value.clientWidth, props.height ?? 100)
  })
  ro.observe(el.value)
  onUnmounted(() => { chart.remove(); ro.disconnect() })
})
</script>
