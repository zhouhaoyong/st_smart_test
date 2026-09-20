import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const componentPath = fileURLToPath(new URL('../src/components/AiOperationProgress.vue', import.meta.url))
assert.equal(existsSync(componentPath), true, '统一 AI 过程组件应存在')

const componentSource = readFileSync(componentPath, 'utf8')
const iconSource = readFileSync(new URL('../public/ai-loading-orbit.svg', import.meta.url), 'utf8')
assert.match(componentSource, /ai-loading-badge--breathing/)
assert.match(componentSource, /ai-operation-loading-time--breathing/)
assert.match(componentSource, /@media \(prefers-reduced-motion: reduce\)/)
assert.match(iconSource, /<title id="title">精致脉冲加载图标<\/title>/)
assert.match(iconSource, /stroke-dasharray="52 17"/)
assert.doesNotMatch(iconSource, /三个蓝紫光点沿轨道环绕中心 AI 符号/)

for (const fileName of [
  'BatchInterfaceCaseGenerationDialog.vue',
]) {
  const source = readFileSync(new URL(`../src/components/${fileName}`, import.meta.url), 'utf8')
  assert.match(source, /<AiOperationProgress[\s\S]*@cancel=/, `${fileName} 应复用统一 AI 过程组件`)
}

console.log('接口列表 AI 生成用例过程组件化与动效回归校验通过')
