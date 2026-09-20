import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { buildPreviewRunPayload, toCaseEditorForm, toPreviewCase } from '../src/utils/aiImportCase.js'

const iface = {
  name: '用户详情',
  method: 'GET',
  url: '/users/{id}',
  service_key: 'user-service',
  headers: [{ key: 'X-Interface', value: '1' }],
  query_params: [{ key: 'verbose', value: 'true' }],
  path_params: [{ key: 'id', value: '$.user_id' }],
  body_type: 'json',
  body_content: '{"source":"interface"}',
  body_schema_types: { id: 'int' },
  pre_script: 'before()',
  post_script: 'after()',
}
const original = {
  name: '用户详情_主流程',
  description: '原始描述',
  priority: 'high',
  case_type: 'main',
  param_overrides: {
    method: 'POST',
    url: '/users',
    headers: [{ key: 'X-Case', value: '2' }],
    query_params: [{ key: 'page', value: '1' }],
    path_params: [],
    body_type: 'json',
    body_content: '{"source":"case"}',
    body_schema_types: { page: 'int' },
    pre_script: 'caseBefore()',
    post_script: 'caseAfter()',
    service_key: 'case-service',
  },
  assertions: [{ type: 'status_code', expression: '200', operator: 'eq', expected: '200' }],
  purpose: '验证主流程',
}

const form = toCaseEditorForm(original, iface)
assert.equal(form.method, 'POST')
assert.equal(form.url, '/users')
assert.deepEqual(form.headers, [{ key: 'X-Case', value: '2' }])
assert.equal(form.body_content, '{"source":"case"}')
assert.equal(form.pre_script, 'caseBefore()')
assert.deepEqual(form.assertions, original.assertions)

const edited = toPreviewCase({ ...form, name: '已编辑用例' }, original)
assert.equal(edited.name, '已编辑用例')
assert.equal(edited.case_type, 'main')
assert.equal(edited.purpose, '验证主流程')
assert.equal(edited.param_overrides.service_key, 'case-service')
assert.deepEqual(edited.param_overrides.headers, [{ key: 'X-Case', value: '2' }])

const payload = buildPreviewRunPayload({
  environment: { id: 8 },
  parameterSet: { id: 9 },
  iface,
  caseData: edited,
})
assert.equal(payload.environment_id, 8)
assert.equal(payload.parameter_set_id, 9)
assert.equal(payload.interface_data.name, '用户详情')
assert.equal(payload.interface_data.service_key, 'user-service')
assert.equal(payload.param_overrides.url, '/users')
assert.deepEqual(payload.assertions, edited.assertions)
assert.equal(payload.test_case_name, '已编辑用例')
assert.equal(buildPreviewRunPayload({ iface, caseData: edited }), null)

const auditContentSource = readFileSync(new URL('../src/utils/auditContent.js', import.meta.url), 'utf8')
assert.match(auditContentSource, /label: '接口调试', codes: \['接口调试', '调试'\]/)
assert.match(auditContentSource, /label: '用例运行', codes: \['用例运行'\]/)
assert.match(auditContentSource, /audit_content_version/)
assert.match(auditContentSource, /\['调试', '接口调试'\]\.includes\(operation\)/)

const interfaceCasesSource = readFileSync(new URL('../src/views/InterfaceCases.vue', import.meta.url), 'utf8')
assert.match(interfaceCasesSource, /test_case_name: form\.value\.name \|\| null/)
assert.match(interfaceCasesSource, /test_case_name: tc\.name \|\| null/)

console.log('AI 预览用例字段映射与环境运行参数回归校验通过')
