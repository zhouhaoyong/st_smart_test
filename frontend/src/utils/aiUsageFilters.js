import { resolveAiFunctionFilter } from './aiUsageLabels.js'

function trimValue(value) {
  const text = String(value ?? '').trim()
  return text || undefined
}

function expandBoundaryTime(value, boundary) {
  const text = trimValue(value)
  if (!text) return undefined
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    return `${text} ${boundary === 'end' ? '23:59:59' : '00:00:00'}`
  }
  return text
}

export function buildAiUsageLogParams({
  page = 1,
  pageSize = 10,
  scope = 'all',
  userName = '',
  phone = '',
  keyword = '',
  model = '',
  modelScope = '',
  modelOwnerScope = '',
  action = '',
  result = '',
  department,
  callerType = '',
  timeRange = [],
  includeStats,
} = {}) {
  const params = {
    page,
    page_size: pageSize,
    scope,
  }

  const normalizedUserName = trimValue(userName)
  const normalizedPhone = trimValue(phone)
  const normalizedKeyword = trimValue(keyword)
  const normalizedModel = trimValue(model)
  const normalizedModelScope = trimValue(modelScope)
  const normalizedModelOwnerScope = trimValue(modelOwnerScope)
  const normalizedAction = resolveAiFunctionFilter(trimValue(action))
  const normalizedResult = trimValue(result)
  const normalizedCallerType = trimValue(callerType)

  if (normalizedUserName) params.user_name = normalizedUserName
  if (normalizedPhone) params.phone = normalizedPhone
  if (normalizedKeyword) params.keyword = normalizedKeyword
  if (normalizedModel) params.model = normalizedModel
  if (normalizedModelScope) params.model_scope = normalizedModelScope
  if (normalizedModelOwnerScope) params.model_owner_scope = normalizedModelOwnerScope
  if (normalizedAction) params.action = normalizedAction
  if (normalizedResult) params.result = normalizedResult
  if (department !== undefined && department !== null && department !== '') params.department = department
  if (normalizedCallerType) params.caller_type = normalizedCallerType
  if (Array.isArray(timeRange) && timeRange.length === 2) {
    const startTime = expandBoundaryTime(timeRange[0], 'start')
    const endTime = expandBoundaryTime(timeRange[1], 'end')
    if (startTime) params.start_time = startTime
    if (endTime) params.end_time = endTime
  }
  if (typeof includeStats === 'boolean') params.include_stats = includeStats

  return params
}
