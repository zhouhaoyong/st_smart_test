export function getMaxScroll(scrollHeight, clientHeight) {
  return Math.max(0, Number(scrollHeight || 0) - Number(clientHeight || 0))
}

export function clampScrollTop(scrollTop, scrollHeight, clientHeight) {
  const maxScroll = getMaxScroll(scrollHeight, clientHeight)
  if (maxScroll <= 0) return 0
  return Math.min(maxScroll, Math.max(0, Number(scrollTop || 0)))
}

export function getScrollRatio(scrollTop, scrollHeight, clientHeight) {
  const maxScroll = getMaxScroll(scrollHeight, clientHeight)
  if (maxScroll <= 0) return 0
  return clampScrollTop(scrollTop, scrollHeight, clientHeight) / maxScroll
}

export function getSyncedScrollTopByRatio({
  sourceScrollTop,
  sourceScrollHeight,
  sourceClientHeight,
  targetScrollHeight,
  targetClientHeight,
}) {
  const ratio = getScrollRatio(sourceScrollTop, sourceScrollHeight, sourceClientHeight)
  const targetMaxScroll = getMaxScroll(targetScrollHeight, targetClientHeight)
  if (targetMaxScroll <= 0) return 0
  return ratio * targetMaxScroll
}

export function getEditorScrollTopForHeading({ headingLine, lineHeight }) {
  return Math.max(0, Number(headingLine || 0) * Number(lineHeight || 0))
}
