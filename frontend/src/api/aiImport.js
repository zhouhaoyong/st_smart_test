/**
 * API 测试接口列表的 AI 用例生成接口。
 */
import request from '@/utils/request'
import { withAiRequestTimeout } from '@/utils/aiRequestTimeout'
import { streamAiRequest } from '@/api/aiStream'

const BASE = '/ai-import'

/** 为已有接口建立独立的用例生成预览，不调用模型、不写入正式用例。 */
export function prepareInterfaceCaseGeneration(data) {
  return request.post(`${BASE}/interface-case-generation/prepare`, data, {
    skipSuccessToast: true,
    skipErrorToast: true,
  })
}

/** 查询接口用例生成预览中的用例，搜索、分页均由后端按临时预览数据完成。 */
export function searchInterfaceCaseGenerationCases(data) {
  return request.post(`${BASE}/interface-case-generation/cases/search`, data, {
    skipSuccessToast: true,
    skipErrorToast: true,
  })
}

/** 保存已有接口的生成结果，只追加新用例，不覆盖历史用例。 */
export function saveInterfaceCaseGeneration(data) {
  return request.post(`${BASE}/interface-case-generation/save`, data, {
    skipSuccessToast: true,
    skipErrorToast: true,
    ...withAiRequestTimeout(),
  })
}

/** 放弃已有接口的生成预览，不影响正式接口和历史用例。 */
export function discardInterfaceCaseGeneration(previewId, projectId) {
  return request.delete(`${BASE}/interface-case-generation/${previewId}`, {
    params: { project_id: projectId },
    skipSuccessToast: true,
    skipErrorToast: true,
  })
}

/**
 * 上传并确定性解析文档，建立会话预览。
 * serviceKey 为第一步选择的默认服务，作用于本次解析出的全部接口；
 * 不选则整个字段不传，后端按“不绑定服务”处理。
 */
/**
 * 取本次生成的分批计划：不调模型，很快返回，用默认超时即可。
 * 前端据此逐批调用 aiImportGenerate，让每批各自享有完整的 AI 超时预算。
 */
export function interfaceCaseGenerationGeneratePlan(data, { signal } = {}) {
  return request.post(`${BASE}/generate-plan`, data, {
    signal,
    skipSuccessToast: true,
    skipErrorToast: true,
  })
}

/**
 * 生成一批接口的用例（前端逐批调用；单接口重试即只含一个 temp_id）；可传 signal 支持中止。
 * 成功与失败提示都统一由生成结果弹窗展示，故一并关掉两种全局 toast，避免一闪而过看不清原因。
 */
export function interfaceCaseGenerationGenerate(data, { signal, onEvent } = {}) {
  return streamAiRequest(`${BASE}/generate/stream`, data, onEvent, signal)
}

/** 保存接口列表生成预览中的单条用例修改，不提前写入正式用例。 */
export function interfaceCaseGenerationEditCase(data) {
  return request.post(`${BASE}/interface-case-generation/edit-case`, data, {
    skipSuccessToast: true,
    skipErrorToast: true,
  })
}
