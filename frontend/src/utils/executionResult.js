export function normalizeExecutionStep(step = {}, caseName = '') {
  const interfaceName = step.interface_name || step.name || ''

  return {
    name: interfaceName,
    interfaceName,
    caseName: caseName || step.test_case_name || '',
    status: step.status,
    msg: step.msg,
    statusCode: step.statusCode ?? step.status_code ?? 0,
    duration: step.duration,
    assertionDiffs: step.assertionDiffs || step.assertion_results?.diffs || [],
    request: step.request,
    response: step.response,
    logs: step.logs || '',
  }
}

export function summarizeAssertionDiffs(diffs = []) {
  const list = Array.isArray(diffs) ? diffs : []
  const failed = list.filter(item => item?.result !== 'pass').length
  return {
    total: list.length,
    passed: list.length - failed,
    failed,
  }
}

export function formatResponseBody(value) {
  if (value === null || value === undefined || value === '') return ''
  if (typeof value !== 'string') {
    try { return JSON.stringify(value, null, 2) } catch { return String(value) }
  }

  const normalized = value.replace(/^\uFEFF/, '').trim()
  if (!normalized) return ''
  try {
    return JSON.stringify(JSON.parse(normalized), null, 2)
  } catch {
    return value.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  }
}

/**
 * 从一步执行结果的响应里取出可展示的响应体文本。
 * 优先级：响应体 → 结构化 JSON → 纯文本 → 整个响应对象，取第一个有内容的。
 */
export function pickResponseBodyText(response) {
  if (!response) return ''
  const candidates = []
  if (Object.prototype.hasOwnProperty.call(response, 'body')) candidates.push(response.body)
  if (Object.prototype.hasOwnProperty.call(response, 'json') && response.json != null) candidates.push(response.json)
  if (Object.prototype.hasOwnProperty.call(response, 'text')) candidates.push(response.text)
  for (const candidate of candidates) {
    const text = formatResponseBody(candidate)
    if (text) return text
  }
  return candidates.length ? '' : formatResponseBody(response)
}

/**
 * 断言实际值展示：空值要显示成看得见的形式，路径取不到字段时直接说明，
 * 避免这一格留白让人分不清「值是空的」还是「路径写错了」。
 */
export function formatAssertionActual(value, found = true) {
  // 历史报告没有取值标记，按取到处理，保持旧数据展示不变
  if (found === false) return '字段不存在'
  if (value === undefined) return ''
  if (value === null) return 'null'
  if (value === '') return '""'
  if (Array.isArray(value) && value.length === 0) return '[]'
  if (typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0) return '{}'
  if (typeof value === 'string') return value
  try { return JSON.stringify(value, null, 2) } catch { return String(value) }
}

export function formatExecutionValue(value, emptyText = '(无)') {
  if (value === null || value === undefined || value === '') return emptyText
  if (typeof value === 'string') return value
  try { return JSON.stringify(value, null, 2) } catch { return String(value) }
}
