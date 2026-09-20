import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const page = readFileSync(new URL('../src/views/ProjectDashboard.vue', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api/project.js', import.meta.url), 'utf8')

assert.match(page, /清空项目数据/)
assert.match(page, /选择数据/)
assert.match(page, /确认清理/)
assert.match(page, /环境/)
assert.match(page, /接口/)
assert.match(page, /用例/)
assert.match(page, /参数集/)
assert.match(page, /执行集/)
assert.match(page, /测试报告/)
assert.match(page, /全部数据/)
assert.match(page, /确认清空/)
assert.match(page, /project\.owner_id === user\.id[\s\S]*!project\.is_public/)
assert.doesNotMatch(page, /user\.is_manager && project\.is_public/)
assert.match(api, /clearProjectBusinessData/)
assert.match(api, /getProjectBusinessCleanupSummary/)

console.log('api project business cleanup interaction test ok')
