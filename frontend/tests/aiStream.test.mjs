import assert from 'node:assert/strict'

import { streamAiRequest } from '../src/api/aiStream.js'

const encoder = new TextEncoder()

function responseWithLines(lines) {
  return {
    ok: true,
    body: new ReadableStream({
      start(controller) {
        for (const line of lines) {
          controller.enqueue(encoder.encode(`${JSON.stringify(line)}\n`))
        }
        controller.close()
      },
    }),
  }
}

function responseWithChunks(chunks) {
  return {
    ok: true,
    body: new ReadableStream({
      start(controller) {
        chunks.forEach(chunk => controller.enqueue(chunk))
        controller.close()
      },
    }),
  }
}

const originalFetch = globalThis.fetch

try {
  let requestUrl = ''
  let requestOptions = null
  globalThis.fetch = async (url, options) => {
    requestUrl = url
    requestOptions = options
    return responseWithLines([
      {
        type: 'event',
        data: { type: 'heartbeat', message: 'AI正在处理中，请稍候' },
      },
      {
        type: 'complete',
        code: 200,
        message: '分析完成',
        data: { preview_id: 'preview-1' },
      },
    ])
  }

  const receivedEvents = []
  const result = await streamAiRequest(
    '/ai-import/generate/stream',
    { interface_ids: ['1'] },
    (event) => receivedEvents.push(event),
  )

  assert.deepEqual(receivedEvents, [
    { type: 'heartbeat', message: 'AI正在处理中，请稍候' },
  ])
  assert.deepEqual(result, { preview_id: 'preview-1' })
  assert.equal(requestUrl, '/api/v1/ai-import/generate/stream')
  assert.equal(requestOptions.method, 'POST')
  assert.deepEqual(JSON.parse(requestOptions.body), { interface_ids: ['1'] })

  globalThis.fetch = async () => responseWithLines([
    {
      type: 'error',
      code: 500,
      message: 'AI生成失败',
      data: { recommend_summary: { usage: { total_tokens: 1 } } },
    },
  ])

  await assert.rejects(
    () => streamAiRequest('/ai-import/generate/stream', {}),
    (error) => error.message === 'AI生成失败'
      && error.data.data.recommend_summary.usage.total_tokens === 1,
  )

  const multibytePayload = encoder.encode(`${JSON.stringify({
    type: 'complete',
    code: 200,
    data: { message: '中文结果' },
  })}\n`)
  const multibyteStart = multibytePayload.findIndex(byte => byte >= 0x80) + 1
  globalThis.fetch = async () => responseWithChunks([
    multibytePayload.slice(0, multibyteStart),
    multibytePayload.slice(multibyteStart),
    encoder.encode('data: [DONE]\n'),
  ])
  assert.deepEqual(await streamAiRequest('/ai-import/generate/stream', {}), { message: '中文结果' })

  globalThis.fetch = async () => responseWithLines([
    { type: 'heartbeat', data: { message: '处理中' } },
  ])
  await assert.rejects(
    () => streamAiRequest('/ai-import/generate/stream', {}),
    error => error.message === 'AI 未返回最终结果，请重试',
  )
} finally {
  globalThis.fetch = originalFetch
}
