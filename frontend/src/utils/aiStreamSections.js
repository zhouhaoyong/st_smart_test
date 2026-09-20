const FINISHED_STATUSES = new Set(['success', 'failed', 'cancelled'])
const INPUT_EVENT_TYPES = new Set(['input', 'stage', 'call_start', 'message_start'])
const REASONING_EVENT_TYPES = new Set(['reasoning_start', 'reasoning_delta', 'reasoning_end'])
const OUTPUT_EVENT_TYPES = new Set([
  'delta',
  'message_delta',
  'message_end',
  'output_start',
  'output_delta',
  'output_end',
  'model_success',
  'model_failed',
])

export function getAiStreamSectionState(payload = {}) {
  const status = String(payload.status || '').trim()
  const eventType = String(payload.eventType || '').trim()
  const loading = Boolean(payload.loading)
  const inputText = String(payload.inputText || '')
  const reasoningText = String(payload.reasoningText || '')
  const outputText = String(payload.outputText || '')
  const supportsReasoning = payload.supportsReasoning === true
  const reasoningSupportUnknown = payload.supportsReasoning !== true && payload.supportsReasoning !== false

  const isFinished = FINISHED_STATUSES.has(status)
  const isStreaming = loading && !isFinished
  const hasInput = Boolean(inputText)
  const hasReasoning = Boolean(reasoningText)
  const hasOutput = Boolean(outputText)
  const isInputEvent = INPUT_EVENT_TYPES.has(eventType)
  const isReasoningEvent = REASONING_EVENT_TYPES.has(eventType)
  const isOutputEvent = OUTPUT_EVENT_TYPES.has(eventType)
  const isIntermediateStage = isStreaming && hasInput && !hasOutput && !isInputEvent && !isOutputEvent

  const hasReasoningSignal = hasReasoning || isReasoningEvent
  const shouldKeepReasoningSlot = (
    hasReasoningSignal
    || supportsReasoning
    || (reasoningSupportUnknown && isIntermediateStage)
  )
  const shouldShowReasoningSection = shouldKeepReasoningSlot && (supportsReasoning || reasoningSupportUnknown || hasReasoningSignal)

  const isInputActive = isStreaming && hasInput && isInputEvent
  const isReasoningActive = isStreaming && !hasOutput && shouldShowReasoningSection && (
    hasReasoningSignal
    || isIntermediateStage
  )
  const shouldShowOutputSection = !isReasoningActive && (
    hasOutput
    || isOutputEvent
    || (!shouldShowReasoningSection && (hasInput || isStreaming))
    || (isFinished && !shouldShowReasoningSection)
  )
  const isOutputActive = isStreaming && !isReasoningActive && (
    hasOutput
    || isOutputEvent
    || (hasInput && !isInputEvent)
  )

  return {
    isFinished,
    isInputActive,
    isReasoningActive,
    isOutputActive,
    shouldShowReasoningSection,
    shouldShowOutputSection,
  }
}
