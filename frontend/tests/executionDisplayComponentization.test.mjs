import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const debugSource = read('../src/components/DebugPanel.vue')
const reportsSource = read('../src/views/Reports.vue')
const requestSource = read('../src/components/ExecutionRequestDetail.vue')
const responseSource = read('../src/components/ExecutionResponseDetail.vue')
const assertionSource = read('../src/components/AssertionDiffTable.vue')

for (const source of [debugSource, reportsSource]) {
  assert.match(source, /<ExecutionRequestDetail/)
  assert.match(source, /<ExecutionResponseDetail/)
  assert.match(source, /<AssertionDiffTable/)
  assert.doesNotMatch(source, /class="request-meta"/)
}

assert.match(requestSource, /label="查询参数" name="params">/)
assert.match(requestSource, /label="路径参数" name="path">/)
assert.match(requestSource, /label="请求头" name="headers">/)
assert.match(responseSource, /label="响应体" name="body">/)
assert.match(responseSource, /label="响应头" name="headers">/)
assert.match(assertionSource, /v-for="\(diff, index\) in diffs"/)

console.log('执行请求、响应和断言展示组件化结构校验通过')
