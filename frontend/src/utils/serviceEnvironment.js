/**
 * 服务标识是跨环境复用的逻辑值，环境里的服务配置只决定当前环境如何解析它。
 * 这里集中处理页面展示和选择状态，避免各个导入入口自行把“当前环境没有”改成“无服务”。
 */

export function normalizeServiceKey(value) {
  const key = String(value ?? '').trim()
  return key || null
}

export function getEnvironmentServices(environment) {
  const items = environment?.service_config?.items
  if (!Array.isArray(items)) return []

  return items
    .filter(item => item && normalizeServiceKey(item.key))
    .map(item => ({
      ...item,
      key: normalizeServiceKey(item.key),
      name: String(item.name || item.key).trim(),
      path_prefix: String(item.path_prefix || '').trim(),
    }))
}

export function getEnabledEnvironmentServices(environment) {
  return getEnvironmentServices(environment)
    .filter(item => item.enabled === true && item.path_prefix)
}

export function resolveServiceSelection(serviceKey, environment) {
  const key = normalizeServiceKey(serviceKey)
  if (!key) return { key: null, status: 'none', service: null }

  const service = getEnvironmentServices(environment).find(item => item.key === key) || null
  if (!service) return { key, status: 'missing', service: null }
  if (service.enabled !== true || !service.path_prefix) {
    return { key, status: 'disabled', service }
  }
  return { key, status: 'resolved', service }
}

export function formatServiceOptionLabel(service) {
  const name = service?.name || service?.key || '服务'
  return service?.path_prefix ? `${name}（${service.path_prefix}）` : `${name}（当前环境未配置路径）`
}

export function matchServiceFromUrl(url, services = [], baseUrl = '') {
  let path = String(url || '').trim()
  try {
    const parsed = new URL(path)
    path = parsed.pathname + parsed.search
  } catch {}

  let basePath = ''
  try {
    basePath = new URL(baseUrl || '').pathname.replace(/\/+$/, '')
  } catch {}
  if (basePath && path.startsWith(basePath + '/')) path = path.slice(basePath.length)

  const matched = (services || [])
    .filter(service => service?.enabled === true && service.path_prefix)
    .filter(service => path === service.path_prefix || path.startsWith(service.path_prefix + '/'))
    .sort((a, b) => b.path_prefix.length - a.path_prefix.length)[0]
  if (!matched) return { service_key: null, url: normalizeServicePath(path) }
  return {
    service_key: matched.key,
    url: normalizeServicePath(path.slice(matched.path_prefix.length) || '/'),
  }
}

function normalizeServicePath(path) {
  const value = String(path || '').trim()
  if (!value) return '/'
  return '/' + value.replace(/^\/+/, '')
}
