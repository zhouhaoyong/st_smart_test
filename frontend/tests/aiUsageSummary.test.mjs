import assert from 'node:assert/strict'
import { combineAiUsage, formatAiTokenCount, normalizeAiUsage } from '../src/utils/aiUsageSummary.js'

assert.deepEqual(
  normalizeAiUsage({
    input_tokens: 120,
    output_tokens: 30,
    total_tokens: 150,
    input_tokens_details: { cached_tokens: 80 },
  }),
  {
    input_tokens: 120,
    output_tokens: 30,
    cache_tokens: 80,
    total_tokens: 150,
  },
)

assert.deepEqual(
  combineAiUsage([
    { input_tokens: 120, output_tokens: 30, total_tokens: 150, cache_tokens: 8 },
    { input_tokens: 80, output_tokens: 20, total_tokens: 100 },
  ]),
  {
    input_tokens: 200,
    output_tokens: 50,
    cache_tokens: 8,
    total_tokens: 250,
  },
)

assert.deepEqual(
  combineAiUsage([{ input_tokens: 10, output_tokens: 5, total_tokens: 15 }]),
  {
    input_tokens: 10,
    output_tokens: 5,
    cache_tokens: null,
    total_tokens: 15,
  },
)

assert.equal(combineAiUsage([]), null)

assert.equal(formatAiTokenCount(1234), '1,234')
assert.equal(formatAiTokenCount(null), '-')

console.log('aiUsageSummary tests ok')
