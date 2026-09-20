import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = path.resolve(import.meta.dirname, '..')
const read = relativePath => fs.readFileSync(path.join(root, relativePath), 'utf8')

test('数据看板展示接口处理率和用例确认率的组合指标', () => {
  const page = read('src/views/ProjectDashboard.vue')

  assert.match(page, /接口处理率/)
  assert.match(page, /stats\.interface_process_rate/)
  assert.match(page, /已处理 \{\{ stats\.interface_done_count \}\}/)
  assert.match(page, /待处理 \{\{ stats\.interface_pending_count \}\}/)
  assert.match(page, /用例确认率/)
  assert.match(page, /stats\.test_case_confirm_rate/)
  assert.match(page, /已确认 \{\{ stats\.test_case_confirmed_count \}\}/)
  assert.match(page, /待确认 \{\{ stats\.test_case_pending_count \}\}/)
})

test('数据看板保留原有卡片跳转并支持接口状态条件跳转', () => {
  const page = read('src/views/ProjectDashboard.vue')

  assert.match(page, /@click="goEnv"/)
  assert.match(page, /@click="goInterface"/)
  assert.match(page, /@click="goTestCase"/)
  assert.match(page, /@click="goExecution"/)
  assert.match(page, /@click="caseDialogVisible = true"/)
  assert.match(page, /@click="ifaceDialogVisible = true"/)
  assert.match(page, /goInterfaceByWorkflowStatus\('done'\)/)
  assert.match(page, /goInterfaceByWorkflowStatus\('pending'\)/)
  assert.match(page, /query:\s*\{\s*workflow_status:\s*workflowStatus\s*\}/)
})

test('数据看板八张统计卡片使用四列两行布局', () => {
  const page = read('src/views/ProjectDashboard.vue')
  const cardClasses = [
    'stat-card--env',
    'stat-card--iface',
    'stat-card--case',
    'stat-card--exec',
    'stat-card--iface-rate',
    'stat-card--case-rate',
    'stat-card--contrib',
    'stat-card--iface-contrib',
  ]

  assert.match(page, /grid-template-columns:\s*repeat\(4,\s*1fr\)/)
  assert.doesNotMatch(page, /stat-grid--contributors/)
  for (let index = 0; index < cardClasses.length - 1; index += 1) {
    assert.ok(
      page.indexOf(cardClasses[index]) < page.indexOf(cardClasses[index + 1]),
      `${cardClasses[index]} 应排在 ${cardClasses[index + 1]} 前面`,
    )
  }
})

test('接口列表会读取看板传入的状态条件后再发起首次查询', () => {
  const page = read('src/views/Interfaces.vue')

  assert.match(page, /route\.query\.workflow_status/)
  assert.match(page, /searchWorkflowStatus\.value = requestedStatus/)
  assert.match(page, /await loadInterfaces\(rememberedCollectionId\)/)
})
