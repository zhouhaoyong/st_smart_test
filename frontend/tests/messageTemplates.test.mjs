import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const messageTemplates = read('../src/views/admin/MessageTemplates.vue')

assert.doesNotMatch(messageTemplates, /<el-table-column[^>]+prop="is_default"[^>]+label="默认"/)
assert.doesNotMatch(messageTemplates, /<el-table-column[^>]+label="默认"[^>]+prop="is_default"/)
assert.match(messageTemplates, /failed_cases_styled/)
assert.match(messageTemplates, /pass_rate_styled/)

console.log('message template visibility test ok')
