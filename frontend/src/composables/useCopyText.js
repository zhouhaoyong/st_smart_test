import { ElMessage } from 'element-plus'
import { copyToClipboard } from '@/utils/clipboard'

export function useCopyText() {
  const copyText = async (value) => {
    if (value === null || value === undefined || value === '') return false
    try {
      if (!await copyToClipboard(value)) throw new Error('clipboard unavailable')
      ElMessage.success('已复制')
      return true
    } catch {
      ElMessage.error('复制失败，请手动复制')
      return false
    }
  }

  return { copyText }
}
