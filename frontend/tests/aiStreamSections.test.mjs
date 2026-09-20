import assert from 'node:assert/strict'
import { getAiStreamSectionState } from '../src/utils/aiStreamSections.js'

const inputStage = getAiStreamSectionState({
  loading: true,
  status: 'running',
  eventType: 'input',
  inputText: 'prompt',
  supportsReasoning: true,
})
assert.equal(inputStage.isInputActive, true)
assert.equal(inputStage.isReasoningActive, false)
assert.equal(inputStage.isOutputActive, false)
assert.equal(inputStage.shouldShowReasoningSection, true)

const reasoningStage = getAiStreamSectionState({
  loading: true,
  status: 'running',
  eventType: 'model_start',
  inputText: 'prompt',
  supportsReasoning: true,
})
assert.equal(reasoningStage.shouldShowReasoningSection, true)
assert.equal(reasoningStage.isReasoningActive, true)
assert.equal(reasoningStage.isOutputActive, false)
assert.equal(reasoningStage.shouldShowOutputSection, false)

const outputStage = getAiStreamSectionState({
  loading: true,
  status: 'running',
  eventType: 'delta',
  inputText: 'prompt',
  outputText: 'result',
  supportsReasoning: true,
})
assert.equal(outputStage.isReasoningActive, false)
assert.equal(outputStage.isOutputActive, true)

const finishedStage = getAiStreamSectionState({
  loading: false,
  status: 'success',
  eventType: 'done',
  inputText: 'prompt',
  reasoningText: 'think',
  outputText: 'result',
  supportsReasoning: true,
})
assert.equal(finishedStage.isInputActive, false)
assert.equal(finishedStage.isReasoningActive, false)
assert.equal(finishedStage.isOutputActive, false)

const unknownReasoningStage = getAiStreamSectionState({
  loading: true,
  status: 'running',
  eventType: 'model_start',
  inputText: 'prompt',
  supportsReasoning: null,
})
assert.equal(unknownReasoningStage.shouldShowReasoningSection, true)
assert.equal(unknownReasoningStage.isReasoningActive, true)
assert.equal(unknownReasoningStage.shouldShowOutputSection, false)

const nonReasoningModelStage = getAiStreamSectionState({
  loading: true,
  status: 'running',
  eventType: 'model_start',
  inputText: 'prompt',
  supportsReasoning: false,
})
assert.equal(nonReasoningModelStage.shouldShowReasoningSection, false)
assert.equal(nonReasoningModelStage.isOutputActive, true)
assert.equal(nonReasoningModelStage.shouldShowOutputSection, true)

const reasoningTextStage = getAiStreamSectionState({
  loading: true,
  status: 'running',
  eventType: 'reasoning_delta',
  inputText: 'prompt',
  reasoningText: 'thinking',
  supportsReasoning: false,
})
assert.equal(reasoningTextStage.shouldShowReasoningSection, true)
assert.equal(reasoningTextStage.isReasoningActive, true)
assert.equal(reasoningTextStage.shouldShowOutputSection, false)

const cancelledDuringReasoning = getAiStreamSectionState({
  loading: false,
  status: 'cancelled',
  eventType: 'done',
  inputText: 'prompt',
  reasoningText: 'thinking',
  supportsReasoning: true,
})
assert.equal(cancelledDuringReasoning.shouldShowReasoningSection, true)
assert.equal(cancelledDuringReasoning.shouldShowOutputSection, false)

console.log('aiStreamSections tests ok')
