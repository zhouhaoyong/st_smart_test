const TOKEN_FIELDS = Object.freeze({
  input_tokens: ['input_tokens', 'prompt_tokens'],
  output_tokens: ['output_tokens', 'completion_tokens'],
  total_tokens: ['total_tokens'],
})
const CACHE_TOKEN_FIELDS = ['cache_tokens', 'prompt_cache_hit_tokens', 'cached_tokens', 'cache_read_input_tokens']

function toToken(value) {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null
  const number = Number(value)
  return Number.isFinite(number) ? Math.round(number) : null
}

function pickToken(usage, fields) {
  for (const field of fields) {
    const value = toToken(usage?.[field])
    if (value !== null) return value
  }
  return null
}

/**
 * 将接口返回的一次模型用量归一成前端阶段汇总使用的字段。
 * 没有任何 Token 数据时返回 null，由调用方决定是否展示统计区。
 */
export function normalizeAiUsage(usage) {
  if (!usage || typeof usage !== 'object') return null
  const normalized = Object.fromEntries(
    Object.entries(TOKEN_FIELDS).map(([name, fields]) => [name, pickToken(usage, fields)]),
  )
  normalized.cache_tokens = pickToken(usage, CACHE_TOKEN_FIELDS)
  if (normalized.cache_tokens === null) {
    normalized.cache_tokens = pickToken(usage.input_tokens_details, ['cached_tokens'])
  }
  return Object.values(normalized).some(value => value !== null) ? normalized : null
}

/**
 * 合并同一 AI 阶段的多次模型调用。
 * 某项只有部分调用返回时，只累加实际拿到的值；缓存没有返回时保持为空。
 */
export function combineAiUsage(usages) {
  const present = (Array.isArray(usages) ? usages : [usages])
    .map(normalizeAiUsage)
    .filter(Boolean)
  if (!present.length) return null

  const sum = field => {
    const values = present.map(item => item[field]).filter(value => value !== null)
    return values.length ? values.reduce((total, value) => total + value, 0) : null
  }

  return {
    input_tokens: sum('input_tokens'),
    output_tokens: sum('output_tokens'),
    cache_tokens: sum('cache_tokens'),
    total_tokens: sum('total_tokens'),
  }
}

export function formatAiTokenCount(value) {
  const number = toToken(value)
  return number === null ? '-' : number.toLocaleString('en-US')
}
