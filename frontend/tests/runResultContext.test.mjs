import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as executionResultUtils from '../src/utils/executionResult.js'

const { normalizeExecutionStep, formatResponseBody } = executionResultUtils

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

const interfaceCases = read('../src/views/InterfaceCases.vue')
const debugPanel = read('../src/components/DebugPanel.vue')
const reports = read('../src/views/Reports.vue')

const normalized = normalizeExecutionStep({
  name: '账户账单流水列表',
  status: 'success',
  statusCode: 200,
  assertion_results: { diffs: [{ result: 'pass' }] },
}, '账户账单流水列表_基础用例')
assert.equal(normalized.interfaceName, '账户账单流水列表')
assert.equal(normalized.caseName, '账户账单流水列表_基础用例')
assert.deepEqual(normalized.assertionDiffs, [{ result: 'pass' }])

assert.equal(
  formatResponseBody('{"code":200,"data":{"id":1}}'),
  '{\n  "code": 200,\n  "data": {\n    "id": 1\n  }\n}',
  '字符串形式的 JSON 响应应被解析并格式化',
)
assert.equal(
  formatResponseBody('第一行\r\n第二行'),
  '第一行\n第二行',
  '普通文本响应只统一换行，不应删除换行内容',
)

assert.equal(typeof executionResultUtils.summarizeAssertionDiffs, 'function', '应提供统一的断言统计方法')
assert.deepEqual(
  executionResultUtils.summarizeAssertionDiffs([
    { result: 'pass' },
    { result: 'failed' },
    { result: 'pass' },
  ]),
  { total: 3, passed: 2, failed: 1 },
  '断言统计应满足通过数加未通过数等于总数',
)

const backendNamed = normalizeExecutionStep({ name: '接口名称', test_case_name: '后端返回的用例名称' })
assert.equal(backendNamed.caseName, '后端返回的用例名称')

for (const [name, source] of [
  ['接口下用例运行', interfaceCases],
]) {
  assert.match(source, /normalizeExecutionStep/, `${name}应统一补充接口名称和用例名称`)
}

assert.match(debugPanel, /label="接口名称"/, '运行结果表格应明确展示接口名称')
assert.match(debugPanel, /v-if="hasCaseNames"/, '有用例上下文时才展示用例名称列')
assert.match(debugPanel, /总断言/, '运行结果应展示总断言')
assert.match(debugPanel, /断言通过/, '运行结果应展示通过断言')
assert.match(debugPanel, /未通过/, '运行结果应展示未通过断言')
assert.doesNotMatch(debugPanel, /总步骤/, '单用例结果不应展示总步骤')
assert.doesNotMatch(debugPanel, /失败\/错误/, '断言统计不应展示失败或错误混合口径')
for (const filter of ['all', 'passed', 'failed']) {
  assert.match(debugPanel, new RegExp(`@click="showAssertions\\('${filter}'\\)"`), `${filter}断言统计应可点击`)
}
const debugTable = debugPanel.slice(debugPanel.indexOf('<el-table v-if="steps'), debugPanel.indexOf('<!-- 选中步骤'))
assert.doesNotMatch(debugTable, /row\.assertionDiffs/, '运行结果表格不应直接铺开断言内容')
assert.match(debugTable, /label="断言结果"/, '运行结果表格应提供断言结果入口')
assert.match(debugTable, /@click\.stop="showStepAssertions\(row\)"/, '单行断言结果应可点击')
assert.match(debugPanel, /@click="showAssertions\('all'\)"/, '总断言统计应可点击')
assert.match(debugPanel, /formatResponseBody/, '调试和运行结果应使用统一响应体格式化')
assert.match(debugPanel, /label="断言结果" name="assertions"/, '运行结果详情应提供断言结果区域')
assert.match(debugPanel, /class="execution-result-header"/, '运行结果详情应使用统一的身份信息头部')
assert.match(debugPanel, /<div class="request-meta">[\s\S]*?<span>请求地址：\{\{ selectedStep\.request\?\.url \|\| '-' \}\}<\/span>/, '步骤详情的请求信息应展示请求地址')
assert.match(debugPanel, /<el-tab-pane label="代理" name="proxy">/, '步骤详情应通过页签展示代理')
assert.match(debugPanel, /<el-tab-pane label="服务" name="service">/, '步骤详情应通过页签展示服务')
assert.doesNotMatch(debugPanel, /class="execution-result-url"/, '步骤详情头部不应重复展示请求地址')
assert.doesNotMatch(debugPanel, /class="execution-summary"/, '步骤详情不应重复展示响应摘要')
assert.match(reports, /class="execution-result-header"/, '测试报告详情应使用统一的身份信息头部')
assert.match(reports, /<div class="request-meta">[\s\S]*?<span>请求地址：\{\{ step\.request_data\?\.url \|\| step\.interface_url \|\| '-' \}\}<\/span>/, '测试报告详情的请求信息应展示请求地址')
assert.match(reports, /<el-tab-pane label="代理" name="proxy">/, '测试报告详情应通过页签展示代理')
assert.match(reports, /<el-tab-pane label="服务" name="service">/, '测试报告详情应通过页签展示服务')
assert.doesNotMatch(reports, /class="execution-result-url"/, '测试报告详情头部不应重复展示请求地址')
assert.doesNotMatch(reports, /class="execution-summary"/, '测试报告详情不应重复展示响应摘要')
assert.match(reports, /总断言/, '测试报告详情应展示总断言')
assert.match(reports, /未通过/, '测试报告详情应展示未通过断言')
assert.doesNotMatch(reports, /<span class="summary-label">断言失败<\/span>/, '测试报告摘要应统一使用未通过文案')
assert.match(reports, /@click="showGroupAssertions\(group, gi, 'all'\)"/, '测试报告总断言统计应可点击')
assert.match(reports, /formatResponseBody/, '测试报告应使用统一响应体格式化')
assert.match(reports, /@update:model-value="setReportDetailTab\(gi, si, 'main', \$event\)"/, '测试报告应支持点击统计后切换到断言详情')

assert.match(interfaceCases, /test_case_count/, '接口列表应直接使用后端返回的用例数量')
assert.match(
  interfaceCases,
  /Object\.prototype\.hasOwnProperty\.call\(overrides, field\)/,
  '运行用例时应保留覆盖字段是否存在的语义',
)
assert.doesNotMatch(
  interfaceCases,
  /for \(const iface of interfaces\.value\) \{[\s\S]*?getTestCases\(iface\.id\)/,
  '接口列表加载不应逐个请求接口用例列表',
)

console.log('run result context test ok')
