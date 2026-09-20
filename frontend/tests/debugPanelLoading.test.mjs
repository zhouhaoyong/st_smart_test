import assert from 'node:assert/strict'
import fs from 'node:fs'
import { formatExecutionValue } from '../src/utils/executionResult.js'

const source = fs.readFileSync(new URL('../src/components/DebugPanel.vue', import.meta.url), 'utf8')
const requestDetail = fs.readFileSync(new URL('../src/components/ExecutionRequestDetail.vue', import.meta.url), 'utf8')
const responseDetail = fs.readFileSync(new URL('../src/components/ExecutionResponseDetail.vue', import.meta.url), 'utf8')
const reportsSource = fs.readFileSync(new URL('../src/views/Reports.vue', import.meta.url), 'utf8')
const serviceInfoUrl = new URL('../src/components/ServiceInfoTable.vue', import.meta.url)
assert.ok(fs.existsSync(serviceInfoUrl), '服务信息展示组件应存在')
const serviceInfoSource = fs.readFileSync(serviceInfoUrl, 'utf8')

const assertRequestInfoOrder = (source, name) => {
  const labels = ['查询参数', '路径参数', '请求体', '请求头', '代理', '服务']
  const positions = labels.map(label => source.indexOf(`label="${label}"`))
  assert.ok(positions.every(position => position >= 0), `${name} 请求信息缺少参数标签`)
  assert.deepEqual([...positions].sort((a, b) => a - b), positions, `${name} 请求信息顺序不一致`)
}

assert.match(source, /loading && \(!steps \|\| !steps\.length\)/)
assert.match(source, /正在运行用例/)
assert.match(source, /class="is-loading"/)

const responsePaneStart = reportsSource.indexOf('<el-tab-pane label="响应结果" name="response">')
const assertionPaneStart = reportsSource.indexOf('<el-tab-pane :label="`断言结果', responsePaneStart)
const reportsResponsePane = reportsSource.slice(responsePaneStart, assertionPaneStart)

assert.match(source, /<ExecutionRequestDetail/)
assert.match(source, /<ExecutionResponseDetail/)
assert.equal((requestDetail.match(/class="detail-tabs"/g) || []).length, 1)
assert.match(requestDetail, /<el-tab-pane label="请求头" name="headers">/)
assert.match(requestDetail, /<el-tab-pane label="查询参数" name="params">/)
assert.match(requestDetail, /<el-tab-pane label="路径参数" name="path">/)
assert.match(requestDetail, /<el-tab-pane label="请求体" name="body">/)
assert.match(requestDetail, /<el-tab-pane v-if="showProxy" label="代理" name="proxy">/)
assert.match(requestDetail, /<el-tab-pane v-if="showService" label="服务" name="service">/)
assert.match(source, /selectedStep\.value\?\.request\?\.path_params/)
assert.match(responseDetail, /<el-tab-pane label="响应体" name="body">/)
assert.match(responseDetail, /<el-tab-pane label="响应头" name="headers">/)

assert.match(reportsSource, /<ExecutionRequestDetail/)
assert.match(reportsSource, /<ExecutionResponseDetail/)
assert.match(reportsSource, /<el-tab-pane label="响应结果" name="response">/)
assert.match(reportsSource, /step\.request_data\?\.path_params/)
assertRequestInfoOrder(requestDetail, '调试面板')
assertRequestInfoOrder(requestDetail, '测试报告')
assert.match(requestDetail, /<el-tab-pane v-if="showProxy" label="代理" name="proxy">/)
assert.match(requestDetail, /<el-tab-pane v-if="showService" label="服务" name="service">/)
assert.match(responseDetail, /<el-tab-pane label="响应头" name="headers">/)
assert.doesNotMatch(reportsResponsePane, /data-section-title">请求头/)

assert.equal(formatExecutionValue('http://proxy.example:8080'), 'http://proxy.example:8080')
assert.equal(formatExecutionValue({ scheme: 'https', url: 'http://proxy.example:8080' }), '{\n  "scheme": "https",\n  "url": "http://proxy.example:8080"\n}')
assert.equal(formatExecutionValue(null, '未使用'), '未使用')

// 服务信息统一使用只读三列表格，接口调试、用例运行结果、测试报告保持一致
assert.match(serviceInfoSource, /服务标识/)
assert.match(serviceInfoSource, /服务名称/)
assert.match(serviceInfoSource, /路径前缀/)
assert.match(serviceInfoSource, /未使用/)
assert.match(serviceInfoSource, /serviceRows/)
assert.equal((requestDetail.match(/<ServiceInfoTable/g) || []).length, 1)
for (const consumerSource of [source, reportsSource]) {
  assert.match(consumerSource, /<ExecutionRequestDetail/)
  assert.doesNotMatch(consumerSource, /<pre class="code-block">\{\{[^}]*service[^}]*\}\}<\/pre>/)
}

console.log('运行结果弹窗 Loading 回归校验通过')
