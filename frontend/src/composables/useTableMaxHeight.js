import { ref, onUnmounted } from 'vue'

/**
 * 用 ResizeObserver 精确测量容器高度（像素），传给 el-table 的 max-height。
 * el-table 需要像素值才能开启内部 body 滚动 + 固定表头。
 */
export function useTableMaxHeight() {
  const tableMaxHeight = ref(400)
  let ro = null

  function observe(el) {
    if (!el) return
    ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const h = entry.contentBoxSize?.[0]?.blockSize ?? entry.contentRect?.height
        if (h > 0) tableMaxHeight.value = h
      }
    })
    ro.observe(el)
    // 初始值
    const h = el.clientHeight
    if (h > 0) tableMaxHeight.value = h
  }

  function unobserve() {
    ro?.disconnect()
    ro = null
  }

  onUnmounted(unobserve)

  return { tableMaxHeight, observeTable: observe, unobserveTable: unobserve }
}
