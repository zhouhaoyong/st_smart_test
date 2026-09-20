export function escapeHtml(text) {
  return String(text ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]))
}

function escapeRegExp(text) {
  return String(text).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function collectParameterHighlightValues(matches = []) {
  return [...new Set(
    matches.flatMap(m => [m?.value, m?.replaced]).filter(Boolean)
  )].sort((a, b) => String(b).length - String(a).length)
}

export function highlightParameterText(text, matches = [], options = {}) {
  let html = escapeHtml(text || '')
  const renderValue = options.clickable ? renderClickableParameterReplacementValue : renderParameterReplacementValue
  collectParameterHighlightValues(matches).forEach(value => {
    const escaped = escapeHtml(value)
    if (!escaped) return
    html = html.replace(new RegExp(escapeRegExp(escaped), 'g'), renderValue(value, matches, options))
  })
  return html
}

export function findReplacementMatch(value, matches = []) {
  return matches.find(m =>
    String(m?.replaced ?? '') === String(value ?? '') ||
    String(m?.value ?? '') === String(value ?? '')
  )
}

function parameterNameFromMatch(match = {}) {
  const ref = String(match.replaced || '')
  return String(match.paramKey || match.key || ref.replace(/^\$\./, '') || '')
}

function parameterPreviewValue(value, match = {}, options = {}) {
  const status = match._status || ''
  if (options.previewMode === 'after' && status !== 'parameterized') return String(match.paramValue ?? value ?? match.replaced ?? '')
  if (options.previewMode === 'after' && status === 'parameterized') return String(match.paramValue ?? value ?? '')
  return String(value ?? '')
}

export function renderParameterReplacementValue(value, matches = [], options = {}) {
  const match = findReplacementMatch(value, matches)
  if (!match) return escapeHtml(value)

  const preview = escapeHtml(parameterPreviewValue(value, match, options))
  const emptyClass = String(match.value ?? '').trim() === '' ? ' is-empty' : ''
  return `<span class="param-replace-target${emptyClass}">${preview}</span>`
}

export function renderClickableParameterReplacementValue(value, matches = [], options = {}) {
  const match = findReplacementMatch(value, matches)
  if (!match) return escapeHtml(value)

  const preview = escapeHtml(parameterPreviewValue(value, match, options))
  const key = escapeHtml(match.nodeKey || '')
  const currentValue = escapeHtml(value)
  const currentValueAttr = currentValue ? ` data-param-current-value="${currentValue}"` : ''
  const emptyClass = String(match.value ?? '').trim() === '' ? ' is-empty' : ''
  return `<button type="button" class="param-replace-target clickable${emptyClass}" data-param-match-key="${key}"${currentValueAttr}>${preview}</button>`
}

export function buildParameterMatchDetail(match = {}) {
  const parameterRef = String(match.replaced || '')
  const parameterValue = String(match.paramValue ?? '')
  const parameterName = parameterNameFromMatch(match)
  const isDeparameterize = match._status === 'parameterized'
  const originalValue = String(match.currentValue ?? match.value ?? '')
  const before = isDeparameterize ? parameterRef : originalValue
  const after = isDeparameterize ? parameterValue : parameterRef
  return {
    before,
    after,
    beforeLabel: isDeparameterize ? '当前引用' : '参数化前',
    afterLabel: isDeparameterize ? '参数当前值（去参数化后）' : '参数化后',
    parameterRef,
    parameterValue,
    parameterName,
    summary: `${before || '(空)'} -> ${after || '(空)'}`,
    modeLabel: isDeparameterize ? '去参数化' : '参数化',
  }
}

export function renderParameterConfigJson(value, matches = [], rootPath = '', options = {}) {
  let html = escapeHtml(JSON.stringify(value ?? [], null, 2))
  const items = Array.isArray(value) ? value : []
  const renderValue = options.clickable ? renderClickableParameterReplacementValue : renderParameterReplacementValue

  matches
    .filter(match => String(match?.path || '').startsWith(`${rootPath}.`))
    .forEach(match => {
      const [indexText] = String(match.path).slice(rootPath.length + 1).split('.')
      const index = Number(indexText)
      const item = items[index]
      if (!item || !item.key) return
      const key = String(item.key)

      if (item.value) {
        const escapedValue = escapeHtml(item.value)
        const renderedValue = renderValue(item.value, [{ ...match, key, value: item.value }], options)
        html = html.replace(`&quot;value&quot;: &quot;${escapedValue}&quot;`, `&quot;value&quot;: &quot;${renderedValue}&quot;`)
      }
    })

  return html
}

function matchesByParamIndex(matches = [], rootPath = '') {
  const result = new Map()
  matches
    .filter(match => String(match?.path || '').startsWith(`${rootPath}.`))
    .forEach(match => {
      const [indexText] = String(match.path).slice(rootPath.length + 1).split('.')
      const index = Number(indexText)
      if (Number.isInteger(index)) result.set(index, match)
    })
  return result
}

function findPathToken(path, item) {
  const key = String(item?.key ?? '')
  const value = String(item?.value ?? '')
  if (value && path.includes(value)) return value
  if (key && path.includes(`{${key}}`)) return `{${key}}`
  if (key && path.includes(`:${key}`)) return `:${key}`
  if (key && path.includes(`<${key}>`)) return `<${key}>`
  return value || (key ? `{${key}}` : '')
}

export function renderParameterPathPreview(url = '', params = [], matches = [], rootPath = 'path_params', options = {}) {
  let html = escapeHtml(url || '(无)')
  const items = Array.isArray(params) ? params : []
  const matchMap = matchesByParamIndex(matches, rootPath)
  const renderValue = options.clickable ? renderClickableParameterReplacementValue : renderParameterReplacementValue

  matchMap.forEach((match, index) => {
    const item = items[index]
    if (!item) return
    const token = findPathToken(String(url || ''), item)
    if (!token) return
    const rendered = renderValue(token, [{ ...match, key: item.key, value: token }], options)
    html = html.replace(escapeHtml(token), rendered)
  })

  return html
}

export function renderParameterQueryPreview(params = [], matches = [], rootPath = 'query_params', options = {}) {
  const items = Array.isArray(params) ? params : []
  if (items.length === 0) return '(无)'

  const matchMap = matchesByParamIndex(matches, rootPath)
  const renderValue = options.clickable ? renderClickableParameterReplacementValue : renderParameterReplacementValue
  const pairs = items.map((item, index) => {
    const key = escapeHtml(item?.key || `param${index + 1}`)
    const value = String(item?.value ?? '')
    const match = matchMap.get(index)
    const renderedValue = match
      ? renderValue(value, [{ ...match, key: item?.key, value }], options)
      : escapeHtml(value)
    return `${key}=${renderedValue}`
  })
  return `?${pairs.join('&')}`
}

export function renderParameterHeaderPreview(headers = [], matches = [], rootPath = 'headers', options = {}) {
  const items = Array.isArray(headers) ? headers : []
  if (items.length === 0) return '(无)'

  const matchMap = matchesByParamIndex(matches, rootPath)
  const renderValue = options.clickable ? renderClickableParameterReplacementValue : renderParameterReplacementValue
  return items.map((item, index) => {
    const key = escapeHtml(item?.key || `Header-${index + 1}`)
    const value = String(item?.value ?? '')
    const match = matchMap.get(index)
    const renderedValue = match
      ? renderValue(value, [{ ...match, key: item?.key, value }], options)
      : escapeHtml(value)
    return `${key}: ${renderedValue}`
  }).join('\n')
}

function getJsonPathValue(value, pathParts) {
  let cursor = value
  for (const part of pathParts) {
    if (Array.isArray(cursor) && /^\d+$/.test(part)) {
      cursor = cursor[Number(part)]
    } else if (cursor && typeof cursor === 'object' && part in cursor) {
      cursor = cursor[part]
    } else {
      return undefined
    }
  }
  return cursor
}

function renderJsonScalar(value) {
  return JSON.stringify(value)
}

export function renderParameterBodyJson(raw, matches = [], rootPath = 'body_content_json', options = {}) {
  const text = String(raw ?? '')
  if (!text) return escapeHtml(text)
  const renderValue = options.clickable ? renderClickableParameterReplacementValue : renderParameterReplacementValue

  let parsed
  try {
    parsed = JSON.parse(text)
  } catch {
    return highlightParameterText(text, matches.filter(match => match?.path === rootPath.replace(/_json$/, '')), options)
  }

  let html = escapeHtml(JSON.stringify(parsed, null, 2))
  matches
    .filter(match => String(match?.path || '').startsWith(`${rootPath}.`))
    .forEach(match => {
      const pathParts = String(match.path).slice(rootPath.length + 1).split('.').filter(Boolean)
      const value = getJsonPathValue(parsed, pathParts)
      if (value === undefined) return

      const lastKey = pathParts[pathParts.length - 1]
      const escapedKey = escapeHtml(lastKey)
      const jsonValue = renderJsonScalar(value)
      const matchValue = value !== null && typeof value === 'object' ? jsonValue : String(value)
      const renderedValue = renderValue(matchValue, [{ ...match, value: matchValue }], options)
      const escapedJsonValue = escapeHtml(jsonValue)
      const escapedStringValue = escapeHtml(String(value))

      if (typeof value === 'string') {
        html = html.replace(
          `&quot;${escapedKey}&quot;: &quot;${escapedStringValue}&quot;`,
          `&quot;${escapedKey}&quot;: &quot;${renderedValue}&quot;`
        )
      } else if (value !== null && typeof value === 'object') {
        const replacementValue = options.previewMode === 'after' && match._status !== 'parameterized'
          ? `&quot;${renderedValue}&quot;`
          : renderedValue
        html = html.replace(
          `&quot;${escapedKey}&quot;: ${escapedJsonValue}`,
          `&quot;${escapedKey}&quot;: ${replacementValue}`
        )
      } else {
        const replacementValue = options.previewMode === 'after' && match._status !== 'parameterized'
          ? `&quot;${renderedValue}&quot;`
          : renderedValue
        html = html.replace(
          `&quot;${escapedKey}&quot;: ${escapedJsonValue}`,
          `&quot;${escapedKey}&quot;: ${replacementValue}`
        )
      }
    })
  return html
}
