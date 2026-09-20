// 会和其他提示用「；」拼成一句，所以句尾不带句号
export const INTERFACE_COLLECTION_IMPORT_GUIDE = '建议按端或系统选择根目录，便于后续查找和执行用例'

// 导入模式与判重规则的完整说明。正文里只留模式按钮和核心数字，这段收进问号，
// 文件导入与接口列表用例生成共用同一份接口集选择口径。
export const IMPORT_MODE_TIPS = [
  '全量模式：列出文件中的全部接口，其中与平台完全一致的接口不会导入。',
  '增量模式：只列出新增和有变化的接口，无变化的接口从列表中隐藏。',
  '切换模式会重新请求后端，后端返回对应范围的接口；两种模式的保存规则一致。',
  '判重规则：按接口编号或「请求方法 + 地址」认出同一个接口；名称、地址、请求方法、请求参数任一变化即算有变化，已有接口原地更新，不会移动目录。',
]

// 第二步顶部的核心数字，两个导入弹窗共用同一套口径、措辞和标签色
export function buildImportModeStats({ newCount = 0, changedCount = 0, unchangedCount = 0 } = {}) {
  return [
    { key: 'total', label: '共解析', value: newCount + changedCount + unchangedCount, tagType: 'primary' },
    { key: 'new', label: '新增', value: newCount, tagType: 'success' },
    { key: 'changed', label: '有变化', value: changedCount, tagType: 'warning' },
    { key: 'unchanged', label: '无变化，不导入', value: unchangedCount, tagType: 'info' },
  ]
}

export function flattenCollectionTreeForSelect(nodes, depth = 0) {
  let result = []
  for (const node of (nodes || [])) {
    const prefix = depth > 0 ? '    '.repeat(depth) + '└ ' : ''
    result.push({ id: node.id, label: prefix + node.name, raw: node })
    if (node.children?.length) {
      result = result.concat(flattenCollectionTreeForSelect(node.children, depth + 1))
    }
  }
  return result
}

export function findCollectionPath(nodes, id) {
  for (const node of (nodes || [])) {
    if (node.id === id || String(node.id) === String(id)) return [node]
    const childPath = findCollectionPath(node.children, id)
    if (childPath.length) return [node, ...childPath]
  }
  return []
}

export function removeCollectionAncestorsFromSelection(nodes, nodeId, selectedIds) {
  const path = findCollectionPath(nodes, nodeId)
  if (path.length < 2) return [...(selectedIds || [])]
  const ancestorIds = new Set(path.slice(0, -1).map(node => String(node.id)))
  return (selectedIds || []).filter(id => !ancestorIds.has(String(id)))
}

// 新建接口集路径按 "||" 分层，去空白与空段；分隔符与后端保持一致
export function splitCollectionPathInput(text) {
  return String(text || '').split('||').map(item => item.trim()).filter(Boolean)
}

// 导入目标是否已填妥：选已有接口集看 id，新建看路径是否有有效层级
export function isImportTargetReady({ mode, collectionId, newPath }) {
  return mode === 'new' ? splitCollectionPathInput(newPath).length > 0 : !!collectionId
}

export function formatCollectionPath(nodes, collection, separator = ' / ') {
  if (!collection?.id) return '-'
  const path = findCollectionPath(nodes, collection.id)
  if (!path.length) return collection.name || `#${collection.id}`
  return path.map(node => node.name || `#${node.id}`).join(separator)
}

function normalizeCollectionCount(value) {
  return Math.max(0, Number(value) || 0)
}

export function getCollectionStatusType(collection) {
  const total = normalizeCollectionCount(collection?.interface_count)
  if (!total) return 'empty'

  const pending = normalizeCollectionCount(collection?.pending_interface_count)
  const done = normalizeCollectionCount(collection?.done_interface_count)
  if (collection?.interface_status === 'done' || (pending === 0 && done === total)) return 'done'
  return 'pending'
}

export function getCollectionStatusHint(collection) {
  const total = normalizeCollectionCount(collection?.interface_count)
  const pending = normalizeCollectionCount(collection?.pending_interface_count)
  if (!total) return '暂无接口'
  if (getCollectionStatusType(collection) === 'done') return `共 ${total} 个接口，全部已处理`
  return `共 ${total} 个接口，其中 ${pending} 个待处理`
}
