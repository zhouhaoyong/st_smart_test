import assert from 'node:assert/strict'
import {
  AI_GENERATE_REQUEST_TIMEOUT_MS,
  AI_REQUEST_TIMEOUT_MS,
  withAiGenerateRequestTimeout,
  withAiRequestTimeout,
} from '../src/utils/aiRequestTimeout.js'

assert.equal(AI_REQUEST_TIMEOUT_MS, 600000)
assert.deepEqual(withAiRequestTimeout(), { timeout: 600000 })
assert.deepEqual(withAiRequestTimeout({ skipErrorToast: true }), { timeout: 600000, skipErrorToast: true })
assert.deepEqual(withAiRequestTimeout({ timeout: 120000 }), { timeout: 120000 })
assert.equal(AI_GENERATE_REQUEST_TIMEOUT_MS, 630000)
assert.deepEqual(withAiGenerateRequestTimeout({ skipErrorToast: true }), { timeout: 630000, skipErrorToast: true })

console.log('aiRequestTimeout tests ok')
