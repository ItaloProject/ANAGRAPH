/**
 * Gera os ícones PNG do ANAGRAPH em todos os tamanhos necessários para o PWA.
 * Usa apenas APIs nativas do Node.js 18+ (sem dependências externas).
 *
 * Execute: node generate-icons.mjs
 *
 * Requer: @napi-rs/canvas  → npm install @napi-rs/canvas --save-dev
 * (ou use o script Python abaixo se preferir não instalar)
 */

import { createCanvas } from '@napi-rs/canvas'
import { writeFileSync, mkdirSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dir = dirname(fileURLToPath(import.meta.url))
const OUT   = join(__dir, 'public', 'icons')
mkdirSync(OUT, { recursive: true })

const SIZES = [48, 72, 96, 128, 192, 256, 384, 512]

function drawIcon(size, maskable = false) {
  const canvas = createCanvas(size, size)
  const ctx    = canvas.getContext('2d')
  const pad    = maskable ? size * 0.15 : 0   // safe area para maskable
  const inner  = size - pad * 2

  // Fundo
  ctx.fillStyle = '#080d1a'
  ctx.fillRect(0, 0, size, size)

  if (maskable) {
    // Maskable: fundo arredondado levemente maior
    ctx.fillStyle = '#0d1526'
    roundRect(ctx, pad * 0.4, pad * 0.4, size - pad * 0.8, size - pad * 0.8, size * 0.15)
    ctx.fill()
  }

  const cx = size / 2
  const cy = size / 2

  // Texto "ANA GRAPH" no topo, centralizado
  const textY = cy - inner * 0.44
  const fs    = inner * 0.15
  ctx.textAlign    = 'center'
  ctx.textBaseline = 'middle'

  // Mede as duas partes para centralizá-las juntas
  ctx.font = `700 ${fs}px sans-serif`
  const wAna   = ctx.measureText('ANA').width
  const wGraph = ctx.measureText('GRAPH').width
  const gap    = fs * 0.18
  const total  = wAna + gap + wGraph
  const startX = cx - total / 2

  // "ANA" em ciano
  ctx.fillStyle = '#00D4FF'
  ctx.textAlign = 'left'
  ctx.fillText('ANA', startX, textY)

  // "GRAPH" em branco
  ctx.fillStyle = '#FFFFFF'
  ctx.fillText('GRAPH', startX + wAna + gap, textY)

  // Diamante exterior (borda ciano)
  const d = inner * 0.33
  ctx.beginPath()
  ctx.moveTo(cx,      cy - d + inner * 0.05)
  ctx.lineTo(cx + d,  cy      + inner * 0.05)
  ctx.lineTo(cx,      cy + d  + inner * 0.05)
  ctx.lineTo(cx - d,  cy      + inner * 0.05)
  ctx.closePath()
  ctx.strokeStyle = '#00D4FF'
  ctx.lineWidth   = size * 0.045
  ctx.stroke()

  // Diamante interior preenchido
  const di = inner * 0.16
  ctx.beginPath()
  ctx.moveTo(cx,       cy - di + inner * 0.05)
  ctx.lineTo(cx + di,  cy      + inner * 0.05)
  ctx.lineTo(cx,       cy + di + inner * 0.05)
  ctx.lineTo(cx - di,  cy      + inner * 0.05)
  ctx.closePath()
  ctx.fillStyle = '#00D4FF'
  ctx.fill()

  return canvas.toBuffer('image/png')
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y,     x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x,     y + h, r)
  ctx.arcTo(x,     y + h, x,     y,     r)
  ctx.arcTo(x,     y,     x + w, y,     r)
  ctx.closePath()
}

for (const size of SIZES) {
  const buf = drawIcon(size, false)
  const name = `icon-${size}x${size}.png`
  writeFileSync(join(OUT, name), buf)
  console.log(`✓ ${name}`)
}

// Maskable (192 e 512 com safe area)
for (const size of [192, 512]) {
  const buf  = drawIcon(size, true)
  const name = `icon-maskable-${size}x${size}.png`
  writeFileSync(join(OUT, name), buf)
  console.log(`✓ ${name} (maskable)`)
}

console.log(`\nÍcones gerados em: public/icons/`)
console.log('Total:', SIZES.length + 2)
