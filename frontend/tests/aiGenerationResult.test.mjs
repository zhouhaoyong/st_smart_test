import assert from 'node:assert/strict'

import { groupGenerationFailures } from '../src/utils/aiGenerationResult.js'

const result = {
  failedDetails: [
    { batchIndex: 2, name: '订单查询', reason: '请求超时', type: 'timeout' },
    { batchIndex: 2, name: '订单创建', reason: '请求超时', type: 'timeout' },
    { batchIndex: 3, name: '用户详情', reason: '模型返回无效结果', type: 'error' },
  ],
  batchResults: [
    { index: 2, interfaceCount: 2 },
    { index: 3, interfaceCount: 1 },
  ],
}

assert.deepEqual(groupGenerationFailures(result), [
  {
    batchIndex: 2,
    interfaceCount: 2,
    reason: '请求超时',
    type: 'timeout',
    items: result.failedDetails.slice(0, 2),
  },
  {
    batchIndex: 3,
    interfaceCount: 1,
    reason: '模型返回无效结果',
    type: 'error',
    items: [result.failedDetails[2]],
  },
])

assert.deepEqual(groupGenerationFailures(null), [])

console.log('AI generation result helpers passed')
