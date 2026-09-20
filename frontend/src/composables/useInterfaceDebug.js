import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { debugRequest } from '@/api/executor'
import { fetchToken as fetchTokenApi } from '@/api/environment'

// Token 缓存：避免每次调试都重新获取（模块级，接口管理与用例管理共用同一份）
const tokenCache = {}
let activeEnvironmentId = null

const AUTH_HEADER_NAMES = new Set([
  'authorization', 'x-auth-token', 'x-api-key', 'x-access-token',
  'cookie', 'token', 'access_token', 'jwt',
])

function stableSerialize(value) {
  if (Array.isArray(value)) return `[${value.map(stableSerialize).join(',')}]`
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${stableSerialize(value[key])}`).join(',')}}`
  }
  return JSON.stringify(value)
}

function clearEnvironmentTokenEntries(envId) {
  const prefix = `${String(envId)}:`
  Object.keys(tokenCache).forEach(key => {
    if (key.startsWith(prefix)) delete tokenCache[key]
  })
}

function touchEnvironment(envId) {
  if (activeEnvironmentId !== null && String(activeEnvironmentId) !== String(envId)) {
    clearEnvironmentTokenEntries(activeEnvironmentId)
    clearEnvironmentTokenEntries(envId)
  }
  activeEnvironmentId = envId
}

function tokenCacheKey(env) {
  return `${String(env.id)}:${stableSerialize(env.token_config || {})}`
}

export async function getOrFetchToken(env) {
  const cfg = env?.token_config
  if (!cfg) return null
  touchEnvironment(env.id)
  // 自动获取已关闭，使用手动Token
  if (cfg.enabled === false) {
    const t = cfg.manual_token
    const prefix = cfg.token_prefix || 'Bearer '
    if (!t) return null
    return t.startsWith(prefix) ? t.slice(prefix.length) : prefix ? t.replace(new RegExp('^' + prefix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i'), '') : t
  }
  // 自动获取已开启但没有配置URL
  if (!cfg.url) return null
  const cacheKey = tokenCacheKey(env)
  const cached = tokenCache[cacheKey]
  if (cached && (Date.now() - cached.fetchedAt) < 30 * 60 * 1000) {
    return cached.token
  }
  try {
    const res = await fetchTokenApi(env.id, null, { skipSuccessToast: true, skipErrorToast: true })
    if (res?.token) {
      tokenCache[cacheKey] = { token: res.token, fetchedAt: Date.now() }
    }
    return res?.token || null
  } catch { return null }
}

export function clearTokenCache(envId) {
  clearEnvironmentTokenEntries(envId)
}

/**
 * 接口调试：接口管理页与用例管理页共用同一套调试状态与请求逻辑，
 * 保证两处「调试」按钮的行为、展示字段完全一致。
 * @param {Object} options
 * @param {import('vue').Ref} options.environment 当前运行环境
 * @param {import('vue').Ref} options.parameterSet 当前参数集
 */
export function useInterfaceDebug({ environment, parameterSet }) {
  const debugDialogVisible = ref(false)
  const debugInterface = ref(null)
  const debugLoading = ref(false)
  const debugMethod = ref('GET')
  const debugRequestUrl = ref('')
  const debugFullUrl = ref('')
  const debugReqHeaders = ref({})
  const debugReqProxy = ref('')
  const debugReqService = ref(null)
  const debugReqParams = ref({})
  const debugReqPathParams = ref([])
  const debugRequestBody = ref('')
  const debugResponse = ref(null)
  const debugRespHeaders = ref(null)
  const debugError = ref('')
  const debugStatusCode = ref(0)
  const debugDuration = ref(0)
  const debugLogs = ref('')

  const ensureDebugEnvironment = () => {
    const env = environment.value
    if (!env?.id || !env?.base_url) {
      ElMessage.warning('请先选择运行环境，未配置请前往"环境管理"页面配置')
      return null
    }
    return env
  }

  const resetDebugResult = () => {
    debugResponse.value = null
    debugRespHeaders.value = null
    debugError.value = ''
    debugLogs.value = ''
    debugStatusCode.value = 0
    debugDuration.value = 0
    debugReqProxy.value = ''
    debugReqService.value = null
  }

  const sendDebugRequest = async () => {
    const intf = debugInterface.value
    if (!intf || debugLoading.value) return
    debugLoading.value = true
    debugError.value = ''
    debugResponse.value = null

    const env = environment.value
    if (!env || !env.base_url) {
      ElMessage.warning('请先选择运行环境')
      debugLoading.value = false
      return
    }
    touchEnvironment(env.id)
    let baseURL = env.base_url.trim()
    if (!baseURL.startsWith('http')) baseURL = 'http://' + baseURL
    if (env.port && env.port !== 80 && env.port !== 443) baseURL += ':' + env.port

    // 合并请求头：环境 < 接口（接口显式设置优先，过滤空 key 和空 value）
    const headers = {}
    if (env.global_headers) {
      Object.entries(env.global_headers).forEach(([k, v]) => {
        const key = (k || '').trim()
        if (key && v != null && v !== '') headers[key] = v
      })
    }
    const tokenHeaderKey = (env.token_config?.header_key || 'Authorization').toLowerCase()
    const tokenPrefix = env.token_config?.token_prefix || 'Bearer '
    const ifaceHasAuth = (intf.headers || []).some(h => {
      const key = (h.key || '').trim()
      return key && (key.toLowerCase() === tokenHeaderKey || AUTH_HEADER_NAMES.has(key.toLowerCase()))
    })
    ;(intf.headers || []).forEach(h => {
      const key = (h.key || '').trim()
      if (key) headers[key] = h.value ?? ''
    })

    // 接口显式设置任一认证头时，完全跳过 Token 请求；否则才使用环境 Token。
    if (!ifaceHasAuth) {
      const freshToken = await getOrFetchToken(env)
      if (freshToken) {
        const existingKey = Object.keys(headers).find(k => k.toLowerCase() === tokenHeaderKey)
        if (existingKey) headers[existingKey] = tokenPrefix + freshToken
        else headers[env.token_config?.header_key || 'Authorization'] = tokenPrefix + freshToken
      }
    }

    const params = {}
    ;(intf.query_params || []).forEach(p => {
      const key = (p.key || '').trim()
      const val = p.value ?? ''
      if (key && val !== '') params[key] = val
    })
    // 未选择请求体类型（none）时不发送请求体，即使内容还留着
    let body = null
    if (intf.body_type && intf.body_content) {
      const raw = (intf.body_content || '').trim()
      if (raw && !['null', 'none', 'undefined'].includes(raw.toLowerCase())) {
        body = intf.body_type === 'json'
          ? (() => { try { return JSON.stringify(JSON.parse(raw)) } catch { return raw } })()
          : raw
      }
    }

    debugLoading.value = true
    resetDebugResult()
    debugMethod.value = intf.method || 'GET'
    debugRequestUrl.value = intf.url
    debugReqHeaders.value = headers
    debugReqParams.value = params
    debugReqPathParams.value = intf.path_params || []
    debugRequestBody.value = body || ''

    try {
      const result = await debugRequest({
        method: intf.method,
        url: intf.url,
        base_url: baseURL,
        port: env.port || null,
        headers,
        body,
        params,
        timeout: env.timeout || 30,
        environment_id: env.id,
        parameter_set_id: parameterSet?.value?.id || null,
        interface_id: intf.id || null,
        path_params: intf.path_params || null,
        service_key: intf.service_key || null,
        pre_script: intf.pre_script || null,
        post_script: intf.post_script || null,
        body_type: intf.body_type || '',
      })

      // 使用后端实际请求数据展示（已合并环境headers、token、变量解析）
      if (result.request) {
        debugMethod.value = result.request.method || intf.method
        debugFullUrl.value = result.request.url || (baseURL + intf.url)
        debugReqHeaders.value = result.request.headers || {}
        debugReqParams.value = result.request.params || {}
        debugReqPathParams.value = result.request.path_params || intf.path_params || []
        debugRequestBody.value = result.request.body || ''
        debugReqProxy.value = result.request.proxy || ''
        debugReqService.value = result.request.service || null
      }
      if (result.response) {
        debugStatusCode.value = result.response.status_code
        debugResponse.value = result.response.body
        debugRespHeaders.value = result.response.headers
        debugDuration.value = result.duration
        debugLogs.value = result.logs || ''
      } else {
        debugError.value = result.error || '请求失败'
        debugDuration.value = result.duration
        debugLogs.value = result.logs || ''
      }
    } catch (e) {
      debugError.value = e.response?.data?.detail || e.message || '请求失败'
    } finally {
      debugLoading.value = false
    }
  }

  /** 打开调试弹窗并立即发起一次调试 */
  const openDebug = (intf) => {
    if (!ensureDebugEnvironment()) return false
    debugInterface.value = intf
    debugMethod.value = intf?.method || 'GET'
    debugRequestUrl.value = intf?.url || ''
    debugFullUrl.value = ''
    debugReqPathParams.value = intf?.path_params || []
    resetDebugResult()
    debugDialogVisible.value = true
    sendDebugRequest()
    return true
  }

  return {
    debugDialogVisible,
    debugInterface,
    debugLoading,
    debugMethod,
    debugRequestUrl,
    debugFullUrl,
    debugReqHeaders,
    debugReqProxy,
    debugReqService,
    debugReqParams,
    debugReqPathParams,
    debugRequestBody,
    debugResponse,
    debugRespHeaders,
    debugError,
    debugStatusCode,
    debugDuration,
    debugLogs,
    ensureDebugEnvironment,
    resetDebugResult,
    sendDebugRequest,
    openDebug,
  }
}
