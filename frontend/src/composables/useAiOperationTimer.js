import { ref, computed, onBeforeUnmount } from 'vue'

function pad(value) {
  return String(value).padStart(2, '0')
}

export function formatAiElapsed(ms) {
  const totalSeconds = Math.max(0, Math.floor(Number(ms || 0) / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return hours > 0
    ? `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
    : `${pad(minutes)}:${pad(seconds)}`
}

/**
 * 记录用户从点击开始到流程结束所感知的耗时，不代表模型单次调用耗时。
 */
export function useAiOperationTimer() {
  const elapsedMs = ref(0)
  const running = ref(false)
  const elapsedText = computed(() => formatAiElapsed(elapsedMs.value))

  let startedAt = 0
  let timer = null

  function refresh() {
    if (!startedAt) return
    elapsedMs.value = Math.max(0, performance.now() - startedAt)
  }

  function clearTimer() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function start() {
    clearTimer()
    startedAt = performance.now()
    elapsedMs.value = 0
    running.value = true
    timer = setInterval(refresh, 1000)
  }

  function stop() {
    refresh()
    clearTimer()
    running.value = false
    return elapsedMs.value
  }

  function reset() {
    clearTimer()
    startedAt = 0
    elapsedMs.value = 0
    running.value = false
  }

  onBeforeUnmount(reset)

  return {
    elapsedMs,
    elapsedText,
    running,
    start,
    stop,
    reset,
  }
}
