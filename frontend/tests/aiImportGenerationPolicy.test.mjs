import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  AI_BATCH_MAX_INTERFACES,
  coveragePlan,
  estimateGeneration,
  extraCaseLimit,
  planGenerationBatches,
  resolveOperationType,
} from '../src/utils/aiImportGeneration.js'

// ---- 接口类型判定：优先采信已有类型字段，缺失时按方法与名称粗判 ----
assert.equal(resolveOperationType({ operation_type: 'auth', method: 'GET' }), 'auth')
assert.equal(resolveOperationType({ method: 'DELETE', url: '/users/1' }), 'delete')
assert.equal(resolveOperationType({ method: 'GET', url: '/users' }), 'read')
assert.equal(resolveOperationType({ method: 'POST', url: '/users' }), 'write')
assert.equal(resolveOperationType({ method: 'POST', url: '/auth/login' }), 'auth')
assert.equal(resolveOperationType({ method: 'TRACE', url: '/x' }), 'other')

// ---- 主流程档完全由系统生成，任何接口数都不消耗次数 ----
const mainEstimate = estimateGeneration(Array.from({ length: 30 }, () => ({ method: 'GET', url: '/users' })), 'main')
assert.equal(mainEstimate.aiCalls, 0)
assert.equal(mainEstimate.cases, 30)

// ---- 覆盖深度随模式与接口类型变化 ----
assert.ok(extraCaseLimit('full', 'write') > extraCaseLimit('normal', 'write'))
assert.ok(extraCaseLimit('normal', 'write') > extraCaseLimit('normal', 'delete'))
assert.equal(extraCaseLimit('main', 'write'), 0)

const plan = coveragePlan({ temp_id: 't1', method: 'POST', url: '/users' }, 'normal')
assert.equal(plan.operationType, 'write')
assert.equal(plan.maxCases, extraCaseLimit('normal', 'write'))

// ---- 分批按接口数量切，每批目标 6～10 个，最后一批允许不足 6 个 ----
const heavy = Array.from({ length: 10 }, (_, i) => ({ tempId: `t${i}`, maxCases: 7 }))
const heavyBatches = planGenerationBatches(heavy)
assert.deepEqual(heavyBatches.map(b => b.length), [10])
assert.equal(heavyBatches.reduce((s, b) => s + b.length, 0), heavy.length)

const eleven = Array.from({ length: 11 }, (_, i) => ({ tempId: `t${i}`, maxCases: 7 }))
assert.deepEqual(planGenerationBatches(eleven).map(b => b.length), [6, 5])

const light = Array.from({ length: 30 }, (_, i) => ({ tempId: `t${i}`, maxCases: 1 }))
assert.ok(planGenerationBatches(light).every(b => b.length <= AI_BATCH_MAX_INTERFACES))
assert.deepEqual(planGenerationBatches(light).map(b => b.length), [10, 10, 10])

// ---- 前后端估算口径必须一致，否则界面预计次数会失真 ----
const backendPolicy = readFileSync(new URL('../../backend/services/ai_import/generation.py', import.meta.url), 'utf8')
assert.match(backendPolicy, new RegExp(`AI_BATCH_MAX_INTERFACES = ${AI_BATCH_MAX_INTERFACES}\\b`))
for (const mode of ['main', 'normal', 'full']) {
  for (const op of ['read', 'write', 'delete', 'auth', 'other']) {
    assert.match(
      backendPolicy,
      new RegExp(`"${mode}": \\{[^}]*"${op}": ${extraCaseLimit(mode, op)}[,}]`),
      `${mode}/${op} 的增量上限前后端不一致`,
    )
  }
}

const generationDialog = readFileSync(new URL('../src/components/BatchInterfaceCaseGenerationDialog.vue', import.meta.url), 'utf8')
assert.match(generationDialog, /@click="retryFailedGeneration"/)
assert.match(generationDialog, /function retryFailedGeneration\(\)/)
assert.doesNotMatch(generationDialog, /class="generation-ai-summary"/)

console.log('AI 导入生成策略回归校验通过')
