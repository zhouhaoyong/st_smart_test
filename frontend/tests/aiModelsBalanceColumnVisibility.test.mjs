import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/admin/AiModels.vue', import.meta.url), 'utf8')

const balanceColumn = source.match(/<el-table-column[^>]*label="余额查询"[^>]*>/)?.[0]

assert.ok(balanceColumn, '应存在余额查询列')
assert.match(
  balanceColumn,
  /v-if="isMineTab \|\| \(isPlatformTab && isSuperuser\)"/,
  '平台模型的余额查询列仅应对超管显示，普通用户的我的模型列保持显示',
)

console.log('AI model balance column visibility test ok')
