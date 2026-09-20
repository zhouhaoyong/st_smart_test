import { computed, ref, shallowRef } from 'vue'
import { getAiModelsForFeature } from '@/api/ai'

/**
 * Shared composable — fetch the model info for a given AI feature.
 * Returns primary model name and fallback list.
 */
export function useAiModelInfo() {
  const primaryModel = ref('')
  const fallbackModels = ref([])
  const supportsReasoning = ref(null)
  const loading = shallowRef(false)
  const error = ref('')

  async function fetch(feature) {
    loading.value = true
    error.value = ''
    try {
      const res = await getAiModelsForFeature(feature, { skipErrorToast: true, skipSuccessToast: true })
      const candidates = res?.candidates || []
      if (candidates.length > 0) {
        primaryModel.value = candidates[0].name
        fallbackModels.value = candidates.slice(1).map(m => m.name)
        supportsReasoning.value = Boolean(candidates[0].supports_reasoning)
      } else {
        primaryModel.value = ''
        fallbackModels.value = []
        supportsReasoning.value = null
        error.value = '未找到可用模型'
      }
    } catch (e) {
      primaryModel.value = ''
      fallbackModels.value = []
      supportsReasoning.value = null
      error.value = e?.data?.message || '获取模型信息失败'
    } finally {
      loading.value = false
    }
  }

  const modelHint = computed(() => {
    if (!primaryModel.value) return '未配置模型'
    let text = primaryModel.value
    if (fallbackModels.value.length) {
      text += `（备用：${fallbackModels.value.join('、')}）`
    }
    return text
  })

  return { primaryModel, fallbackModels, supportsReasoning, loading, error, fetch, modelHint }
}
