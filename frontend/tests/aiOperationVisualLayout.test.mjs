import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const operationSource = read('../src/components/AiOperationProgress.vue')
const iconSource = read('../public/ai-loading-orbit.svg')

const headSource = operationSource.match(/<div class="ai-loading-card-head">[\s\S]*?<\/div>/)?.[0] || ''
assert.match(headSource, /showBadge/)
assert.match(headSource, /ai-operation-loading-time/)
assert.match(operationSource, /\.ai-loading-card-head\s*\{[^}]*justify-content:\s*space-between/)
assert.doesNotMatch(operationSource, /\.ai-operation-loading-time\s*\{[^}]*position:\s*absolute/)
assert.match(operationSource, /ai-loading-badge--breathing/)
assert.match(operationSource, /ai-operation-loading-time--breathing/)
assert.match(iconSource, /<title id="title">精致脉冲加载图标<\/title>/)
assert.match(iconSource, /class="pulse-orbit"/)
assert.match(iconSource, /class="pulse-node"/)
assert.match(iconSource, /class="pulse-core"/)
assert.match(iconSource, /class="pulse-bolt"/)
assert.match(
  iconSource,
  /<g class="pulse-orbit">\s*<animateTransform attributeName="transform" type="rotate"[\s\S]*?<path/,
  '实心原点应与轨道作为整体旋转',
)
assert.match(
  iconSource,
  /<circle class="pulse-node" cx="129" cy="58" r="5"/,
  '实心原点应位于两段轨道实线之间的空缺中心',
)
assert.doesNotMatch(
  iconSource,
  /<path[\s\S]*?<animateTransform attributeName="transform" type="rotate"/,
  '旋转动画不应只绑定在轨道路径上',
)
assert.doesNotMatch(iconSource, /filter id="glow"/)

console.log('AI 过程状态同高回归校验通过')
