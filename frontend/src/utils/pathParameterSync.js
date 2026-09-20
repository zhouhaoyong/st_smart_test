const PATH_PARAMETER_PATTERN = /\{([^{}]*)\}/g

function normalizeKey(value) {
  return String(value ?? '').trim()
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function isValidPathParameterName(value) {
  const key = normalizeKey(value)
  return Boolean(key) && /^[^\s{}\/?#]+$/u.test(key)
}

export function extractPathParameterNames(url = '') {
  const names = []
  String(url ?? '').replace(PATH_PARAMETER_PATTERN, (_match, rawName) => {
    const name = normalizeKey(rawName)
    if (isValidPathParameterName(name) && !names.includes(name)) names.push(name)
    return _match
  })
  return names
}

export function validatePathParameterUrl(url = '') {
  const source = String(url ?? '')
  const matches = [...source.matchAll(PATH_PARAMETER_PATTERN)]
  const remaining = source.replace(PATH_PARAMETER_PATTERN, '')
  if (remaining.includes('{') || remaining.includes('}')) {
    return { valid: false, message: 'URL 中的路径参数格式有误，请使用 {参数名}' }
  }
  const invalidName = matches.find(match => !isValidPathParameterName(match[1]))
  if (invalidName) return { valid: false, message: 'URL 中的路径参数名不能为空，且不能包含空格或花括号' }
  return { valid: true, message: '' }
}

export function validatePathParameterList(params = []) {
  const keys = (Array.isArray(params) ? params : []).map(item => normalizeKey(item?.key)).filter(Boolean)
  const invalidName = keys.find(key => !isValidPathParameterName(key))
  if (invalidName) return { valid: false, message: `路径参数“${invalidName}”格式有误，请填写不含空格或花括号的参数名` }
  if (new Set(keys).size !== keys.length) return { valid: false, message: '路径参数名不能重复，请检查参数配置' }
  return { valid: true, message: '' }
}

function createPathParameter(key) {
  return {
    key,
    value: '',
    required: true,
    description: '',
    type: 'string',
    type_source: 'manual',
  }
}

export function syncPathParametersFromUrl(url = '', currentParams = []) {
  if (!validatePathParameterUrl(url).valid) return Array.isArray(currentParams) ? currentParams : []
  const currentList = Array.isArray(currentParams) ? currentParams : []
  const currentByKey = new Map()
  currentList.forEach(item => {
    const key = normalizeKey(item?.key)
    if (isValidPathParameterName(key) && !currentByKey.has(key)) currentByKey.set(key, item)
  })
  const names = extractPathParameterNames(url)
  return names.map((key, index) => {
    const current = currentByKey.get(key)
    if (current) return current
    if (currentList.length === names.length && currentList[index]) return { ...currentList[index], key }
    return createPathParameter(key)
  })
}

function replacePathParameter(url, oldKey, newKey) {
  const pattern = new RegExp(`\\{\\s*${escapeRegExp(oldKey)}\\s*\\}`, 'g')
  return url.replace(pattern, `{${newKey}}`)
}

function removePathParameter(url, key) {
  const segmentPattern = new RegExp(`/\\{\\s*${escapeRegExp(key)}\\s*\\}(?=\\/|[?#]|$)`, 'g')
  const tokenPattern = new RegExp(`\\{\\s*${escapeRegExp(key)}\\s*\\}`, 'g')
  const suffixIndex = url.search(/[?#]/)
  const path = suffixIndex >= 0 ? url.slice(0, suffixIndex) : url
  const suffix = suffixIndex >= 0 ? url.slice(suffixIndex) : ''
  const nextPath = path.replace(segmentPattern, '').replace(tokenPattern, '')
  return `${nextPath.length > 1 ? nextPath.replace(/\/+$/, '') : nextPath}${suffix}`
}

function appendPathParameter(url, key) {
  const source = String(url ?? '')
  if (extractPathParameterNames(source).includes(key)) return source
  const suffixIndex = source.search(/[?#]/)
  const base = suffixIndex >= 0 ? source.slice(0, suffixIndex) : source
  const suffix = suffixIndex >= 0 ? source.slice(suffixIndex) : ''
  const separator = base && !base.endsWith('/') ? '/' : ''
  return `${base}${separator}{${key}}${suffix}`
}

export function syncUrlFromPathParameters(url = '', previousParams = [], currentParams = []) {
  const source = String(url ?? '')
  if (!validatePathParameterUrl(source).valid || !validatePathParameterList(currentParams).valid) return source

  const previousKeys = (Array.isArray(previousParams) ? previousParams : [])
    .map(item => normalizeKey(item?.key))
    .filter(Boolean)
  const currentKeys = (Array.isArray(currentParams) ? currentParams : [])
    .map(item => normalizeKey(item?.key))
    .filter(Boolean)
  const currentKeySet = new Set(currentKeys)
  const previousKeySet = new Set(previousKeys)
  const renamePairs = []

  previousKeys.forEach((oldKey, index) => {
    const newKey = currentKeys[index]
    if (
      newKey &&
      oldKey !== newKey &&
      !currentKeySet.has(oldKey) &&
      !previousKeySet.has(newKey)
    ) {
      renamePairs.push([oldKey, newKey])
    }
  })

  let nextUrl = source
  const renamedKeys = new Set(renamePairs.map(([oldKey]) => oldKey))
  renamePairs.forEach(([oldKey, newKey]) => {
    nextUrl = replacePathParameter(nextUrl, oldKey, newKey)
  })
  previousKeys.forEach(oldKey => {
    if (!currentKeySet.has(oldKey) && !renamedKeys.has(oldKey)) nextUrl = removePathParameter(nextUrl, oldKey)
  })
  currentKeys.forEach(key => {
    if (!extractPathParameterNames(nextUrl).includes(key)) nextUrl = appendPathParameter(nextUrl, key)
  })
  return nextUrl
}
