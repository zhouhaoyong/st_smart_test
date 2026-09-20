const REF_PATTERN = /(?:\$\.[A-Za-z_]\w*|\{\{\s*[A-Za-z_]\w*(?:\.[\w.]+)?\s*\}\})/

function markConflict(match, kind, reason) {
  match.conflict_kind = match.conflict_kind || kind
  match.conflict_reason = match.conflict_reason || reason
  match._checked = false
  return 'conflict'
}

export function getParameterMatchStatus(match, groupKey) {
  const value = String(match?.value ?? '')
  const normalizedValue = value.trim().toLowerCase()
  const targetRef = String(match?.replaced || `$.${groupKey}`)

  if (value.includes(targetRef)) return 'parameterized'
  if (match?.conflict_reason) return 'conflict'
  if (value.trim() === '') {
    return markConflict(match, 'empty_value', '原值为空，需确认是否要参数化')
  }
  if (normalizedValue === '{}') return markConflict(match, 'empty_object', '原值为空对象，可能来自接口文档占位，需确认是否要参数化')
  if (normalizedValue === '[]') return markConflict(match, 'empty_array', '原值为空数组，需确认是否要参数化')
  if (['null', 'none'].includes(normalizedValue)) return markConflict(match, 'null_value', '原值为空值，需确认是否要参数化')
  if (REF_PATTERN.test(value)) return 'conflict'
  return 'pending'
}

export function isParameterMatchReplaceable(match, groupKey) {
  return ['pending', 'parameterized', 'conflict'].includes(getParameterMatchStatus(match, groupKey))
}

export function categorizeParameterMatches(groups) {
  const buckets = {
    pending: [],
    parameterized: [],
    conflict: [],
  }

  for (const group of groups || []) {
    const groupedMatches = { pending: [], parameterized: [], conflict: [] }

    for (const result of group.results || []) {
      const perResult = { pending: [], parameterized: [], conflict: [] }
      for (const match of result._flatMatches || []) {
        const status = getParameterMatchStatus(match, group.key)
        match._status = status
        perResult[status].push(match)
      }

      for (const status of Object.keys(perResult)) {
        if (perResult[status].length > 0) {
          groupedMatches[status].push({
            ...result,
            _flatMatches: perResult[status],
          })
        }
      }
    }

    for (const status of Object.keys(groupedMatches)) {
      if (groupedMatches[status].length > 0) {
        buckets[status].push({
          ...group,
          results: groupedMatches[status],
        })
      }
    }
  }

  return buckets
}
