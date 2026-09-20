const REF_PATTERN = /\$\.[A-Za-z_]\w*/

function sourceContainsReference(source = {}) {
  return [
    source.source_name,
    source.field_path,
    source.match_type,
    source.value,
  ].some(value => REF_PATTERN.test(String(value ?? '')))
}

export function candidateIgnoredReason(candidate = {}, existingKeys = { keys: new Set(), values: new Set() }) {
  const key = String(candidate.key || '').trim()
  if (!key) return 'invalid'
  if (existingKeys.keys.has(key)) return 'existing'
  if (candidate.candidate_status === 'type_conflict') return 'type_conflict'
  if (candidate.candidate_status === 'empty' || String(candidate.value ?? '').trim() === '') return 'empty_value'
  if (candidate.candidate_status === 'invalid') return 'invalid_value'
  if (candidate.candidate_status === 'needs_confirmation') return 'needs_confirmation'
  if (REF_PATTERN.test(String(candidate.value ?? ''))) return 'parameterized'
  if ((candidate.sources || []).some(sourceContainsReference)) return 'parameterized'
  return ''
}

function mergeIgnoredCandidate(current, next) {
  const hitCount = Number(current.hit_count || 1) + Number(next.hit_count || 1)
  const sources = [
    ...(current.sources || []),
    ...(next.sources || []),
  ]
  const values = new Set([
    ...(current.ignored_values || []),
    current.value,
    next.value,
  ].map(value => String(value ?? '')).filter(Boolean))

  return {
    ...current,
    hit_count: hitCount || current.hit_count || next.hit_count || 1,
    sources,
    ignored_values: [...values],
  }
}

export function splitParameterCandidates(candidates = [], existingItems = []) {
  const existingKeys = {
    keys: new Set(existingItems.map(item => String(item.key || '').trim()).filter(Boolean)),
    values: new Set(existingItems.map(item => String(item.value ?? '').trim()).filter(Boolean)),
  }
  const visible = []
  const review = []
  const existing = []
  const invalid = []
  const byBucketAndKey = new Map()

  const bucketForReason = reason => {
    if (reason === 'existing' || reason === 'parameterized') return existing
    if (reason === 'invalid' || reason === 'invalid_value') return invalid
    return review
  }

  const mergeIntoBucket = (bucket, candidate) => {
    const key = String(candidate.key || '').trim()
    if (!key) {
      bucket.push(candidate)
      return
    }
    const bucketName = bucket === existing ? 'existing' : bucket === invalid ? 'invalid' : 'review'
    const mapKey = `${bucketName}:${key}`
    const current = byBucketAndKey.get(mapKey)
    if (current) {
      const merged = mergeIgnoredCandidate(current, candidate)
      const index = bucket.indexOf(current)
      if (index >= 0) bucket[index] = merged
      byBucketAndKey.set(mapKey, merged)
    } else {
      bucket.push(candidate)
      byBucketAndKey.set(mapKey, candidate)
    }
  }

  for (const candidate of candidates || []) {
    const reason = candidateIgnoredReason(candidate, existingKeys)
    const normalized = {
      ...candidate,
      ignored_reason: reason,
    }
    if (reason) mergeIntoBucket(bucketForReason(reason), normalized)
    else {
      visible.push(normalized)
    }
  }

  return { visible, review, existing, invalid }
}

export function candidateIgnoredReasonLabel(reason) {
  return {
    existing: '已存在',
    existing_value: '值已存在',
    parameterized: '已参数化',
    invalid: '无效参数',
    invalid_value: '非法值',
    empty_value: '待补充',
    type_conflict: '类型冲突',
    needs_confirmation: '需要确认',
  }[reason] || ''
}
