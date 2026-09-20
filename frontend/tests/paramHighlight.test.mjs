import assert from 'node:assert/strict'
import {
  collectParameterHighlightValues,
  highlightParameterText,
  renderParameterConfigJson,
  renderParameterBodyJson,
  buildParameterMatchDetail,
  renderClickableParameterReplacementValue,
  renderParameterHeaderPreview,
  renderParameterPathPreview,
  renderParameterQueryPreview,
  renderParameterReplacementValue,
} from '../src/utils/paramHighlight.js'

const matches = [{ value: '', replaced: '$.project_id' }]

assert.deepEqual(collectParameterHighlightValues(matches), ['$.project_id'])
assert.equal(
  highlightParameterText('[{"key":"project_id","value":"$.project_id"}]', matches),
  '[{&quot;key&quot;:&quot;project_id&quot;,&quot;value&quot;:&quot;<span class="param-replace-target is-empty">$.project_id</span>&quot;}]'
)

assert.equal(
  renderParameterReplacementValue('$.project_id', [{ key: 'project_id', value: '', replaced: '$.project_id' }]),
  '<span class="param-replace-target is-empty">$.project_id</span>'
)

assert.equal(
  renderParameterConfigJson([{ key: 'project_id', value: '' }], [{ path: 'path_params.0.value', replaced: '$.project_id' }], 'path_params'),
  '[\n  {\n    &quot;key&quot;: &quot;project_id&quot;,\n    &quot;value&quot;: &quot;&quot;\n  }\n]'
)

assert.match(
  renderParameterConfigJson([{ key: 'token', value: 'abc' }], [{ path: 'param_overrides.headers.0.value', replaced: '$.token' }], 'param_overrides.headers', { previewMode: 'after' }),
  /<span class="param-replace-target">abc<\/span>/
)

assert.doesNotMatch(
  renderParameterConfigJson([{ key: 'test1', value: 'test1updated' }], [{ path: 'query_params.0.value', replaced: '$.test1', paramValue: 'test1updated' }], 'query_params'),
  /&quot;key&quot;: &quot;<span/
)

const bodyWithoutTarget = JSON.stringify({
  phone: '<phone>',
  password: '<password>',
  real_name: '<real_name>',
  nick_name: {},
  department: 1,
}, null, 2)

assert.equal(
  renderParameterBodyJson(bodyWithoutTarget, [{ path: 'body_content_json.test1', value: '测试', replaced: '$.test1', paramValue: '测试' }], 'body_content_json'),
  bodyWithoutTarget.replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]))
)

const bodyWithTarget = JSON.stringify({
  password: '<password>',
  test1: '测试',
  test2: { name: 'zhy' },
}, null, 2)
const renderedBody = renderParameterBodyJson(
  bodyWithTarget,
  [{ path: 'body_content_json.test1', value: '测试', replaced: '$.test1', paramValue: '测试' }],
  'body_content_json'
)
assert.match(renderedBody, /&quot;test1&quot;: &quot;<span class="param-replace-target">测试<\/span>/)
assert.doesNotMatch(renderedBody, /pa<span class="param-replace-target">/)

assert.match(
  renderParameterBodyJson(
    bodyWithTarget,
    [{ path: 'body_content_json.test1', value: '测试', replaced: '$.test1', paramValue: '测试' }],
    'body_content_json',
    { previewMode: 'after' }
  ),
  /&quot;test1&quot;: &quot;<span class="param-replace-target">测试<\/span>/
)

assert.match(
  renderParameterBodyJson(
    JSON.stringify({ limit: 10 }, null, 2),
    [{ path: 'body_content_json.limit', value: '10', replaced: '$.limit', paramValue: '10' }],
    'body_content_json',
    { previewMode: 'after' }
  ),
  /&quot;limit&quot;: &quot;<span class="param-replace-target">10<\/span>&quot;/
)

const renderedConflictBody = renderParameterBodyJson(
  JSON.stringify({ name: {}, tags: [], description: null }, null, 2),
  [
    { nodeKey: 'body-object', path: 'body_content_json.name', value: '{}', replaced: '$.name', paramValue: 'zhangsan', conflict_kind: 'empty_object', _status: 'conflict' },
    { nodeKey: 'body-array', path: 'body_content_json.tags', value: '[]', replaced: '$.tags', paramValue: 'tag-a', conflict_kind: 'empty_array', _status: 'conflict' },
    { nodeKey: 'body-null', path: 'body_content_json.description', value: 'null', replaced: '$.description', paramValue: 'desc', conflict_kind: 'null_value', _status: 'conflict' },
  ],
  'body_content_json',
  { previewMode: 'after', clickable: true }
)
assert.match(renderedConflictBody, /&quot;name&quot;: &quot;<button type="button" class="param-replace-target clickable" data-param-match-key="body-object" data-param-current-value="\{\}">zhangsan<\/button>&quot;/)
assert.match(renderedConflictBody, /&quot;tags&quot;: &quot;<button type="button" class="param-replace-target clickable" data-param-match-key="body-array" data-param-current-value="\[\]">tag-a<\/button>&quot;/)
assert.match(renderedConflictBody, /&quot;description&quot;: &quot;<button type="button" class="param-replace-target clickable" data-param-match-key="body-null" data-param-current-value="null">desc<\/button>&quot;/)

assert.equal(
  renderParameterPathPreview(
    '/api/v1/reports/{report_id}',
    [{ key: 'report_id', value: '' }],
    [{ path: 'path_params.0.value', value: '', replaced: '$.report_id', paramValue: '123' }],
    'path_params',
    { previewMode: 'after' }
  ),
  '/api/v1/reports/<span class="param-replace-target">123</span>'
)

assert.equal(
  renderParameterQueryPreview(
    [
      { key: 'skip', value: '0' },
      { key: 'limit', value: '10' },
    ],
    [{ path: 'query_params.1.value', value: '10', replaced: '$.limit', paramValue: '10' }],
    'query_params',
    { previewMode: 'after' }
  ),
  '?skip=0&limit=<span class="param-replace-target">10</span>'
)

assert.equal(
  renderParameterQueryPreview(
    [
      { key: 'skip', value: '' },
      { key: 'limit', value: '10' },
    ],
    [{ nodeKey: 'q1', path: 'query_params.0.value', value: '', replaced: '$.skip', paramValue: '0', conflict_kind: 'empty_value' }],
    'query_params',
    { previewMode: 'after', clickable: true }
  ),
  '?skip=<button type="button" class="param-replace-target clickable is-empty" data-param-match-key="q1">0</button>&limit=10'
)

assert.equal(
  renderClickableParameterReplacementValue('10', [{ nodeKey: 'm1', value: '10', replaced: '$.limit', paramValue: '10' }], { previewMode: 'after' }),
  '<button type="button" class="param-replace-target clickable" data-param-match-key="m1" data-param-current-value="10">10</button>'
)

assert.equal(
  renderClickableParameterReplacementValue('$.limit', [{ nodeKey: 'm2', value: '$.limit', replaced: '$.limit', paramValue: '10', _status: 'parameterized' }], { previewMode: 'after' }),
  '<button type="button" class="param-replace-target clickable" data-param-match-key="m2" data-param-current-value="$.limit">10</button>'
)

assert.equal(
  renderParameterHeaderPreview(
    [
      { key: 'Authorization', value: 'Bearer abc' },
      { key: 'X-Tenant', value: 'cq' },
    ],
    [{ nodeKey: 'h1', path: 'headers.0.value', value: 'Bearer abc', replaced: '$.token', paramValue: 'Bearer abc' }],
    'headers',
    { clickable: true, previewMode: 'after' }
  ),
  'Authorization: <button type="button" class="param-replace-target clickable" data-param-match-key="h1" data-param-current-value="Bearer abc">Bearer abc</button>\nX-Tenant: cq'
)

assert.deepEqual(
  buildParameterMatchDetail({ value: '10', replaced: '$.limit', paramValue: '10', _status: 'pending' }),
  {
    before: '10',
    after: '$.limit',
    beforeLabel: '参数化前',
    afterLabel: '参数化后',
    parameterRef: '$.limit',
    parameterValue: '10',
    parameterName: 'limit',
    summary: '10 -> $.limit',
    modeLabel: '参数化',
  }
)

assert.deepEqual(
  buildParameterMatchDetail({ value: '$.limit', replaced: '$.limit', paramValue: '10', _status: 'parameterized' }),
  {
    before: '$.limit',
    after: '10',
    beforeLabel: '当前引用',
    afterLabel: '参数当前值（去参数化后）',
    parameterRef: '$.limit',
    parameterValue: '10',
    parameterName: 'limit',
    summary: '$.limit -> 10',
    modeLabel: '去参数化',
  }
)

assert.deepEqual(
  buildParameterMatchDetail({ value: 'stale', currentValue: '{}', replaced: '$.name', paramValue: 'zhangsan', _status: 'conflict' }),
  {
    before: '{}',
    after: '$.name',
    beforeLabel: '参数化前',
    afterLabel: '参数化后',
    parameterRef: '$.name',
    parameterValue: 'zhangsan',
    parameterName: 'name',
    summary: '{} -> $.name',
    modeLabel: '参数化',
  }
)

console.log('paramHighlight tests ok')
