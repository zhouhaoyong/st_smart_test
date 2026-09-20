/**
 * 接口列表 AI 生成用例的前端辅助。
 * 默认断言与空用例的请求覆盖模板，均对齐运行契约（param_overrides 固定键）。
 */

// 默认断言：响应体业务码 $.code == "200"，运行时按值比较，不区分数据类型。
export const DEFAULT_ASSERTION = {
  type: 'jsonpath',
  expression: '$.code',
  operator: 'eq',
  expected: '200',
}

/**
 * 由接口原生信息构造一份空的 param_overrides，字段与运行契约保持一致。
 * 用例未参数化时，直接沿用接口自带的方法 / URL / 头 / 体等发起请求。
 * 不含服务：服务由接口在运行时兜底，用例这里写空值会被判成“明确不使用服务”。
 */
export function blankParamOverrides(iface = {}) {
  return {
    method: iface.method || 'GET',
    url: iface.url || '',
    headers: iface.headers || [],
    query_params: iface.query_params || [],
    path_params: iface.path_params || [],
    body_type: iface.body_type || '',
    body_content: iface.body_content || null,
    pre_script: iface.pre_script || '',
    post_script: iface.post_script || '',
  }
}

const clone = (value, fallback) => {
  if (value == null) return fallback
  try { return JSON.parse(JSON.stringify(value)) } catch { return fallback }
}

const hasOwn = (value, key) => Object.prototype.hasOwnProperty.call(value || {}, key)

/**
 * 将 AI 预览用例转换为正式用例编辑弹窗使用的字段结构。
 * 用例覆盖存在时优先使用覆盖；缺失字段才回退到解析后的接口定义。
 */
export function toCaseEditorForm(caseData = {}, iface = {}) {
  const overrides = caseData?.param_overrides && typeof caseData.param_overrides === 'object'
    ? caseData.param_overrides
    : {}
  const pick = (key, fallback) => hasOwn(overrides, key) ? overrides[key] : fallback
  return {
    name: caseData.name || '',
    description: caseData.description || '',
    priority: caseData.priority || 'high',
    case_type: caseData.case_type || 'main',
    purpose: caseData.purpose || '',
    warnings: clone(caseData.warnings, []),
    todo: clone(caseData.todo, []),
    method: pick('method', iface.method || 'GET') || 'GET',
    url: pick('url', iface.url || '') || '',
    headers: clone(pick('headers', iface.headers || []), []),
    query_params: clone(pick('query_params', iface.query_params || []), []),
    path_params: clone(pick('path_params', iface.path_params || []), []),
    body_type: pick('body_type', iface.body_type || '') || '',
    body_content: pick('body_content', iface.body_content || '') ?? '',
    body_schema_types: clone(pick('body_schema_types', iface.body_schema_types || {}), {}),
    pre_script: pick('pre_script', iface.pre_script || '') || '',
    post_script: pick('post_script', iface.post_script || '') || '',
    // 只回显用例自己指定过的服务，不从接口继承：继承来的值一旦回写，
    // 用户回到上一步改接口服务时用例会留着过期值。
    service_key: pick('service_key', null) || null,
    assertions: clone(caseData.assertions, [dictDefaultAssertion()]),
  }
}

function dictDefaultAssertion() {
  return { ...DEFAULT_ASSERTION }
}

/** 将编辑弹窗的完整字段写回 AI 预览用例，保留生成元数据。 */
export function toPreviewCase(form = {}, original = {}) {
  const paramOverrides = {
    method: form.method || 'GET',
    url: form.url || '',
    headers: clone(form.headers, []),
    query_params: clone(form.query_params, []),
    path_params: clone(form.path_params, []),
    body_type: form.body_type || '',
    body_content: form.body_content ?? '',
    body_schema_types: clone(form.body_schema_types, {}),
    pre_script: form.pre_script || '',
    post_script: form.post_script || '',
  }
  // 服务只在用例层面显式指定过才写：写一个空的服务标识会被单条运行
  // 误判成“明确不使用服务”，从而盖掉接口自身的服务归属。
  const serviceKey = String(form.service_key || '').trim()
  if (serviceKey) paramOverrides.service_key = serviceKey
  return {
    ...clone(original, {}),
    name: form.name || '',
    description: form.description || '',
    priority: form.priority || 'high',
    case_type: form.case_type || original.case_type || 'main',
    param_overrides: paramOverrides,
    assertions: clone(form.assertions, []),
  }
}

/**
 * 构造未落库 AI 用例的运行请求。
 * environment / parameterSet 只传当前左下角选择结果，执行器负责读取其完整配置。
 */
export function buildPreviewRunPayload({ environment, parameterSet = null, iface = {}, caseData = {} } = {}) {
  if (!environment?.id) return null
  return {
    environment_id: environment.id,
    parameter_set_id: parameterSet?.id || null,
    test_case_name: caseData.name || null,
    interface_data: {
      name: iface.name || '',
      method: iface.method || 'GET',
      url: iface.url || '',
      service_key: iface.service_key || null,
      headers: clone(iface.headers, []),
      query_params: clone(iface.query_params, []),
      path_params: clone(iface.path_params, []),
      body_type: iface.body_type || '',
      body_content: iface.body_content || '',
      body_schema_types: clone(iface.body_schema_types, {}),
      pre_script: iface.pre_script || '',
      post_script: iface.post_script || '',
    },
    param_overrides: clone(caseData.param_overrides, blankParamOverrides(iface)),
    assertions: clone(caseData.assertions, []),
  }
}
