/**
 * 接口列表 AI 生成用例的生成策略（前端镜像）。
 *
 * 与 backend/services/ai_import/generation.py 保持同一套口径：
 * - 每个接口的主流程用例一律由系统生成，不消耗额度；
 * - AI 只补充逆向 / 异常增量，补多少由「生成模式 × 接口类型」决定；
 * - 分批按接口数量均衡切，每批 6～10 个接口，因此前端能算出与后端一致的调用次数。
 * 改这里必须同步改后端，否则界面预估会失真。
 */

export const OPERATION_TYPES = ['read', 'write', 'delete', 'auth', 'other']

export const OPERATION_TYPE_LABELS = {
  read: '查询类',
  write: '写入类',
  delete: '删除类',
  auth: '鉴权类',
  other: '其他',
}

// 每个接口的增量用例数量上限（不含系统生成的主流程用例）
export const EXTRA_CASE_LIMITS = Object.freeze({
  main: { read: 0, write: 0, delete: 0, auth: 0, other: 0 },
  normal: { read: 3, write: 4, delete: 2, auth: 3, other: 2 },
  full: { read: 5, write: 7, delete: 4, auth: 5, other: 4 },
})

export const AI_BATCH_MAX_INTERFACES = 10

const AUTH_KEYWORDS = ['login', 'logout', 'auth', 'token', 'signin', 'sign_in', '登录', '登出', '鉴权', '认证']
const DELETE_KEYWORDS = ['delete', 'remove', 'destroy', '删除', '移除']

export function normalizeMode(mode) {
  return EXTRA_CASE_LIMITS[mode] ? mode : 'normal'
}

/** 接口类型：优先采信 AI 辅助分析结论，缺失时按请求方法与名称粗判。 */
export function resolveOperationType(iface) {
  const declared = String(iface?.operation_type || '').trim().toLowerCase()
  if (OPERATION_TYPES.includes(declared)) return declared

  const method = String(iface?.method || '').toUpperCase()
  const text = `${iface?.name || ''} ${iface?.url || ''} ${iface?.operation_id || ''}`.toLowerCase()

  if (AUTH_KEYWORDS.some(k => text.includes(k))) return 'auth'
  if (method === 'DELETE' || DELETE_KEYWORDS.some(k => text.includes(k))) return 'delete'
  if (['GET', 'HEAD', 'OPTIONS'].includes(method)) return 'read'
  if (['POST', 'PUT', 'PATCH'].includes(method)) return 'write'
  return 'other'
}

export function extraCaseLimit(mode, operationType) {
  const table = EXTRA_CASE_LIMITS[normalizeMode(mode)]
  return table[OPERATION_TYPES.includes(operationType) ? operationType : 'other']
}

export function coveragePlan(iface, mode) {
  const operationType = resolveOperationType(iface)
  return {
    tempId: iface?.temp_id,
    operationType,
    maxCases: extraCaseLimit(mode, operationType),
  }
}

/** 按接口数量均衡分批，口径与后端一致，用于估算调用次数。 */
export function planGenerationBatches(plans) {
  const items = Array.isArray(plans) ? plans : []
  if (!items.length) return []
  const batchCount = Math.ceil(items.length / AI_BATCH_MAX_INTERFACES)
  const baseSize = Math.floor(items.length / batchCount)
  const remainder = items.length % batchCount
  const batches = []
  let cursor = 0
  for (let index = 0; index < batchCount; index += 1) {
    const size = baseSize + (index < remainder ? 1 : 0)
    batches.push(items.slice(cursor, cursor + size))
    cursor += size
  }
  return batches
}

/**
 * 界面预估：本次大概生成多少个用例、需要调用模型多少次。
 * 数量按上限估算（每接口 1 个系统主流程用例 + 增量上限），实际只会更少。
 */
export function estimateGeneration(interfaces, mode) {
  const normalizedMode = normalizeMode(mode)
  const items = Array.isArray(interfaces) ? interfaces : []
  const plans = items.map(i => coveragePlan(i, normalizedMode))
  const aiPlans = plans.filter(p => p.maxCases > 0)
  return {
    mode: normalizedMode,
    interfaces: items.length,
    cases: plans.reduce((sum, p) => sum + 1 + p.maxCases, 0),
    aiCalls: planGenerationBatches(aiPlans).length,
  }
}
