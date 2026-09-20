import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const page = readFileSync(new URL('../src/views/Login.vue', import.meta.url), 'utf8')

assert.match(page, /测试与研发工具一体化平台/)
assert.match(page, /<span>测试工作台<\/span>/)
assert.match(page, /<span>API测试<\/span>/)
assert.match(page, /<span>工具箱<\/span>/)
assert.match(page, /<span>导航管理<\/span>/)
assert.match(page, /placeholder="手机号"/)
assert.match(page, /placeholder="密码"/)

console.log('login brand navigation test ok')
