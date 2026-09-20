import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: Number(import.meta.env.VITE_REQUEST_TIMEOUT) || 120000
})

const resolveHashLoginPath = () => `${import.meta.env.BASE_URL}#/login`

const isAuthenticationFailure = (code, message) => {
  if (code === 401) return true
  if (code !== 403) return false
  return /未授权|重新登录|登录已过期|登录失效/.test(String(message || ''))
}

// 防止多个认证失败同时触发重复提示和重复跳转
let isRedirectingToLogin = false

const logoutAndRedirect = (message) => {
  if (isRedirectingToLogin) return
  isRedirectingToLogin = true
  localStorage.removeItem('access_token')
  localStorage.removeItem('user_info')
  ElMessage.error(message || '登录已过期，请重新登录')
  setTimeout(() => {
    window.location.href = resolveHashLoginPath()
  }, 1500)
}

// 请求拦截器
request.interceptors.request.use(
  config => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

// 响应拦截器
request.interceptors.response.use(
  response => {
    const res = response.data

    // 统一响应格式：{ code, message, data }
    if (res && typeof res === 'object' && 'code' in res) {
      if (res.code !== 200) {
        if (isAuthenticationFailure(res.code, res.message)) {
          logoutAndRedirect(res.message)
          return Promise.reject(new Error(res.message || '登录已过期，请重新登录'))
        }

        if (!response.config?.skipErrorToast) {
          ElMessage.error(res.message || '请求失败')
        }

        const error = new Error(res.message || '请求失败')
        error.response = response
        error.data = res
        return Promise.reject(error)
      }

      if (res.message && res.message !== 'success' && !response.config?.skipSuccessToast) {
        ElMessage.success(res.message)
      }

      return 'data' in res ? res.data : res
    }

    return res
  },
  error => {
    // 主动取消的请求（AbortController）不是错误，静默透传给调用方处理
    if (axios.isCancel?.(error) || error.code === 'ERR_CANCELED' || error.name === 'CanceledError') {
      return Promise.reject(error)
    }

    const status = error.response?.status
    const data = error.response?.data

    if (!error.config?.skipErrorToast) {
      if (status === 401) {
        logoutAndRedirect(data?.message)
      } else if (status === 403 && isAuthenticationFailure(403, data?.message || data?.detail)) {
        // 403 分两类：凭证/登录态失效（后端以特定文案返回）按登录失效处理，跳登录页
        logoutAndRedirect(data?.message || data?.detail)
      } else if (status === 403) {
        // 其余 403 为纯粹的权限不足（已登录但无该操作权限），仅提示一次，不跳转
        ElMessage.error(data?.message || data?.detail || '请求失败')
      } else if (status === 404) {
        ElMessage.error(data?.message || '请求的资源不存在')
      } else if (status === 422) {
        const detail = data?.detail
        const msg = data?.message || (Array.isArray(detail)
          ? detail.map(e => e.msg).join('; ')
          : (data?.data?.message || '参数验证失败'))
        ElMessage.error(msg)
      } else if (status === 400) {
        ElMessage.error(data?.message || data?.detail || data?.data?.message || '请求参数有误')
      } else if (status && status >= 500) {
        ElMessage.error(data?.message || data?.detail || '服务器内部错误，请稍后重试')
      } else {
        ElMessage.error(error.message || '网络连接失败，请检查网络')
      }
    }

    return Promise.reject(error)
  }
)

export default request
