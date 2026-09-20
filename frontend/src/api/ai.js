/**
 * AI 基础设施 — API wrapper module.
 * AI models, quota, usage logs — shared across all modules.
 */
import request from '@/utils/request'
import { withAiRequestTimeout } from '@/utils/aiRequestTimeout'

const BASE = '/ai'

// ============ AI Models ============

export function getAiModels(params = {}) {
  return request.get(`${BASE}/models`, { params })
}

// 模型详情（含接口地址）。列表不再返回 base_url，编辑回显 / 查看详情从这里取。
export function getAiModelDetail(id, config = {}) {
  return request.get(`${BASE}/models/${id}`, config)
}

export function getAiModelsForFeature(feature, config = {}) {
  return request.get(`${BASE}/models/for-feature`, { params: { feature }, ...config })
}

export function createAiModel(data) {
  return request.post(`${BASE}/models`, data)
}

export function updateAiModel(id, data) {
  return request.put(`${BASE}/models/${id}`, data)
}

export function deleteAiModel(id, config = {}) {
  return request.delete(`${BASE}/models/${id}`, config)
}

export function setAiModelQuota(id, dailyLimit) {
  return request.put(`${BASE}/quotas/models/${id}`, { daily_limit: dailyLimit })
}

export function getAiModelQuotas() {
  return request.get(`${BASE}/quotas/models`)
}

export function checkAiModelBalance(id, data, config = {}) {
  return request.post(`${BASE}/models/${id}/check-balance`, data, config)
}

export function getAiModelBalanceQueryConfig(id, config = {}) {
  return request.get(`${BASE}/models/${id}/balance-query-config`, config)
}

export function testAiModelBilling(id, data, config = {}) {
  return request.post(`${BASE}/models/${id}/test-billing`, data, config)
}

export function testAiModelBillingDraft(data, config = {}) {
  return request.post(`${BASE}/models/test-billing`, data, config)
}

// 模型能力检测（三合一）：一次真实探针同时判定 连通性 / 思考模式 / 用量统计。
// 已保存模型走 {id} 接口并落库；新建/编辑未保存配置走探测接口仅返回结果，保存时随表单一并落库。
export function testAiModelCapabilities(id, config = {}) {
  return request.post(`${BASE}/models/${id}/test-capabilities`, undefined, { timeout: 330000, ...config })
}

export function testAiModelCapabilitiesDraft(data, config = {}) {
  return request.post(`${BASE}/models/test-capabilities`, data, { timeout: 330000, ...config })
}

// reason: manual=用户点了终止；timeout=浏览器等待超时后中断，两者的审计文案不同。
export function resetAiModelCapabilities(id, config = {}, reason = 'manual') {
  return request.post(`${BASE}/models/${id}/reset-capabilities`, undefined, { params: { reason }, ...config })
}

export function fetchAiModels(data, config = {}) {
  return request.post(`${BASE}/models/fetch-models`, data, config)
}

// ============ Usage & Quota ============

export function getAiQuota() {
  return request.get(`${BASE}/usage/quota`)
}

export function getAiPlatformQuotaSetting() {
  return request.get(`${BASE}/quotas/platform-setting`)
}

export function setAiPlatformQuotaSetting(dailyLimit) {
  return request.put(`${BASE}/quotas/platform-setting`, { daily_limit: dailyLimit })
}

export function getAiUsageLogs(params = {}) {
  return request.get(`${BASE}/usage/logs`, { params })
}

// 用量统计弹窗：按用户 + 时间维度查询平台模型 / 我的模型用量。
export function getUserQuotaStats(params = {}) {
  return request.get(`${BASE}/usage/user-quota-stats`, { params })
}

export function deleteAiUsageLogsBatch(ids, config = {}) {
  return request.post(`${BASE}/usage/logs/delete-batch`, { ids }, {
    skipSuccessToast: true,
    ...config,
  })
}

export function deleteAiUsageLogsAll(params = {}, config = {}) {
  return request.post(`${BASE}/usage/logs/delete-all`, params, {
    skipSuccessToast: true,
    ...config,
  })
}

// ============ Quota Management (Superadmin) ============

export function getQuotaUsers(q = '', params = {}) {
  return request.get(`${BASE}/quotas/users`, { params: { q, ...params } })
}
