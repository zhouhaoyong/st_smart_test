export function groupGenerationFailures(result) {
  if (!result?.failedDetails?.length) return []

  const groups = new Map()
  result.failedDetails.forEach(item => {
    const key = item.batchIndex || 'unknown'
    if (!groups.has(key)) {
      const batch = result.batchResults?.find(entry => String(entry.index) === String(key))
      groups.set(key, {
        batchIndex: batch?.index || item.batchIndex || '-',
        interfaceCount: batch?.interfaceCount || 0,
        reason: item.reason || '处理失败',
        type: item.type || 'error',
        items: [],
      })
    }
    groups.get(key).items.push(item)
  })
  return [...groups.values()]
}
