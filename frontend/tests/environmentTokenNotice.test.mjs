import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/Environments.vue', import.meta.url), 'utf8')

assert.match(
  source,
  /动态认证 Token：单用例和执行集执行时优先复用环境缓存；缓存未命中时按认证配置获取，接口返回 401 时自动刷新。手写认证头或手动 Token 不会自动获取。/
)
assert.doesNotMatch(source, /单用例运行会实时获取新 token/)
assert.doesNotMatch(source, /执行集每次执行开始时每套认证只获取一次/)

console.log('环境 Token 说明文案回归校验通过')
