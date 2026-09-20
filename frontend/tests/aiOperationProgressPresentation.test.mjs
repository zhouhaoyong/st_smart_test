import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const operationSource = read('../src/components/AiOperationProgress.vue')
const batchSource = read('../src/components/BatchInterfaceCaseGenerationDialog.vue')

assert.match(operationSource, /ai-loading-orbit\.svg/)
assert.match(operationSource, /class="ai-loading-orbit-icon"/)
assert.match(operationSource, /import\.meta\.env\.BASE_URL/)
assert.doesNotMatch(operationSource, /\.\.\/\.\.\/docs\/ai-loading-orbit\.svg/)
assert.doesNotMatch(operationSource, /ai-loading-spinner/)
assert.doesNotMatch(operationSource, /import \{ Loading, Timer \}/)
assert.match(operationSource, /animation: ai-operation-time-breathe 1\.6s ease-in-out infinite/)
assert.match(operationSource, /transform-origin: right center/)
assert.match(operationSource, /50% \{ opacity: 1; transform: scale\(1\.06\);/)
assert.match(operationSource, /\.ai-operation-loading-card\s*\{[^}]*width: min\(100%, 640px\);[^}]*max-width: 640px;[^}]*padding: 40px 40px 34px;[^}]*gap: 16px;/s)
assert.match(operationSource, /\.ai-loading-copy\s*\{[^}]*gap: 8px;/s)
assert.match(operationSource, /\.ai-operation-loading-bar\s*\{[^}]*margin: 0;/s)
assert.match(operationSource, /\.ai-loading-progress-info\s*\{[^}]*gap: 6px;[^}]*padding: 10px 14px;/s)
assert.match(operationSource, /class="ai-loading-progress-info"/)
assert.match(operationSource, /class="ai-operation-loading-meta"/)
assert.match(batchSource, /import \{ estimateGeneration \} from '@\/utils\/aiImportGeneration'/)
assert.match(batchSource, /:meta-text="generationModelCallsText"/)
assert.match(batchSource, /return aiCalls \? `预计消耗 \$\{aiCalls\} 次 AI 配额次数` : '不消耗 AI 配额次数'/)

console.log('AI 过程动效与进度信息布局回归校验通过')
