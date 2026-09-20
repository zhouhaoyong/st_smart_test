function includesText(value, keyword) {
  if (!keyword) return true
  return String(value ?? '').toLowerCase().includes(String(keyword).trim().toLowerCase())
}

export function filterParameterItems(items = [], filters = {}) {
  return items.filter(item =>
    includesText(item.display_name, filters.name) &&
    includesText(item.key, filters.key) &&
    includesText(item.value, filters.value)
  )
}
