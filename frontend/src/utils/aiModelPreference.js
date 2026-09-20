const STORAGE_KEY = 'smart_test:last_ai_model_id'

const hasModelId = value => value !== null && value !== undefined && String(value).trim() !== ''
const sameModelId = (left, right) => hasModelId(left) && hasModelId(right) && String(left) === String(right)

function resolveStorage(storage) {
  if (storage !== undefined) return storage
  try {
    return globalThis.localStorage
  } catch {
    return null
  }
}

export function readLastAiModelId(storage) {
  const target = resolveStorage(storage)
  if (!target || typeof target.getItem !== 'function') return null
  try {
    const value = target.getItem(STORAGE_KEY)
    return hasModelId(value) ? String(value).trim() : null
  } catch {
    return null
  }
}

export function rememberAiModel(modelId, storage) {
  if (!hasModelId(modelId)) return
  const target = resolveStorage(storage)
  if (!target || typeof target.setItem !== 'function') return
  try {
    target.setItem(STORAGE_KEY, String(modelId))
  } catch {
    // 本地存储不可用时不影响当前 AI 操作。
  }
}

export function findAiModel(candidates, modelId) {
  if (!Array.isArray(candidates)) return null
  return candidates.find(item => sameModelId(item?.id, modelId)) || null
}

export function pickPreferredAiModelId(candidates, currentId = null, rememberedId = readLastAiModelId()) {
  const list = Array.isArray(candidates) ? candidates : []
  return findAiModel(list, currentId)?.id
    ?? findAiModel(list, rememberedId)?.id
    ?? list[0]?.id
    ?? null
}
