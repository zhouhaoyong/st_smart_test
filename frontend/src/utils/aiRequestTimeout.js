export const AI_REQUEST_TIMEOUT_MS = 600000
// 后端需要在模型超时后完成预览落库与审计，生成请求给服务端留出收尾缓冲。
export const AI_GENERATE_REQUEST_TIMEOUT_MS = AI_REQUEST_TIMEOUT_MS + 30000

export function withAiRequestTimeout(config = {}) {
  return {
    timeout: AI_REQUEST_TIMEOUT_MS,
    ...config,
  }
}

export function withAiGenerateRequestTimeout(config = {}) {
  return {
    timeout: AI_GENERATE_REQUEST_TIMEOUT_MS,
    ...config,
  }
}
