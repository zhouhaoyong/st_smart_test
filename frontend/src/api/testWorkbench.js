import request from '@/utils/request'
import { streamAiRequest } from '@/api/aiStream'

// 项目
export const getWorkbenchProjects = (params) => request({ url: '/test-workbench/projects', method: 'get', params })
export const getWorkbenchProject = (id) => request({ url: `/test-workbench/projects/${id}`, method: 'get' })
export const getWorkbenchProjectUsers = (id) => request({ url: `/test-workbench/projects/${id}/users`, method: 'get' })
export const getWorkbenchProjectDashboard = (id, params) => request({ url: `/test-workbench/projects/${id}/dashboard`, method: 'get', params })
export const getWorkbenchProjectDashboardAssets = (id, params) => request({ url: `/test-workbench/projects/${id}/dashboard-assets`, method: 'get', params })
export const getWorkbenchTestCaseSources = (id, params) => request({
  url: `/test-workbench/projects/${id}/test-case-sources`,
  method: 'get',
  params,
  paramsSerializer: { indexes: null },
})
export const getWorkbenchProjectBusinessCleanupSummary = (id, params) => request({ url: `/test-workbench/projects/${id}/business-cleanup-summary`, method: 'get', params })
export const clearWorkbenchProjectBusinessData = (id, data) => request({ url: `/test-workbench/projects/${id}/clear-business-data`, method: 'post', data, skipSuccessToast: true })
export const createWorkbenchProject = (data) => request({ url: '/test-workbench/projects', method: 'post', data })
export const updateWorkbenchProject = (id, data) => request({ url: `/test-workbench/projects/${id}`, method: 'put', data })
export const deleteWorkbenchProject = (id) => request({ url: `/test-workbench/projects/${id}`, method: 'delete' })
export const copyWorkbenchProject = (id) => request({ url: `/test-workbench/projects/${id}/copy`, method: 'post' })

// 系统
export const getWorkbenchSystems = (project_id) => request({ url: '/test-workbench/systems', method: 'get', params: { project_id } })
export const createWorkbenchSystem = (data) => request({ url: '/test-workbench/systems', method: 'post', data })
export const updateWorkbenchSystem = (id, data) => request({ url: `/test-workbench/systems/${id}`, method: 'put', data })
export const deleteWorkbenchSystem = (id) => request({ url: `/test-workbench/systems/${id}`, method: 'delete' })

// 版本
export const getWorkbenchVersions = (system_id) => request({ url: '/test-workbench/versions', method: 'get', params: { system_id } })
export const createWorkbenchVersion = (data) => request({ url: '/test-workbench/versions', method: 'post', data })
export const updateWorkbenchVersion = (id, data) => request({ url: `/test-workbench/versions/${id}`, method: 'put', data })
export const deleteWorkbenchVersion = (id) => request({ url: `/test-workbench/versions/${id}`, method: 'delete' })

// 单条需求
export const getWorkbenchRequirements = (version_id) => request({ url: '/test-workbench/requirements', method: 'get', params: { version_id } })
export const saveWorkbenchRequirement = (data) => request({ url: '/test-workbench/requirements', method: 'post', data })
export const updateWorkbenchRequirement = (id, data) => request({ url: `/test-workbench/requirements/${id}`, method: 'put', data })
export const deleteWorkbenchRequirement = (id) => request({ url: `/test-workbench/requirements/${id}`, method: 'delete' })
export const batchDeleteWorkbenchRequirements = (data) => request({ url: '/test-workbench/requirements/batch-delete', method: 'post', data })
export const getWorkbenchRequirementDetail = (id) => request({ url: `/test-workbench/requirements/${id}/detail`, method: 'get' })
export const getWorkbenchRequirementRelations = (id) => request({ url: `/test-workbench/requirements/${id}/relations`, method: 'get' })
export const confirmWorkbenchRequirement = (id) => request({ url: `/test-workbench/requirements/${id}/confirm`, method: 'post' })
export const batchConfirmWorkbenchRequirements = (data) => request({ url: '/test-workbench/requirements/batch-confirm', method: 'post', data })

// 补全需求：AI 结果独立保存，与原始需求状态互不影响。
export const getWorkbenchCompletedRequirements = (version_id) => request({ url: '/test-workbench/completed-requirements', method: 'get', params: { version_id } })
export const getWorkbenchCompletedRequirementDetail = (id) => request({ url: `/test-workbench/completed-requirements/${id}/detail`, method: 'get' })
export const updateWorkbenchCompletedRequirement = (id, data) => request({ url: `/test-workbench/completed-requirements/${id}`, method: 'put', data })
export const deleteWorkbenchCompletedRequirement = (id) => request({ url: `/test-workbench/completed-requirements/${id}`, method: 'delete' })
export const batchDeleteWorkbenchCompletedRequirements = (data) => request({ url: '/test-workbench/completed-requirements/batch-delete', method: 'post', data })
export const confirmWorkbenchCompletedRequirement = (id) => request({ url: `/test-workbench/completed-requirements/${id}/confirm`, method: 'post' })
export const batchConfirmWorkbenchCompletedRequirements = (data) => request({ url: '/test-workbench/completed-requirements/batch-confirm', method: 'post', data })

// 单条需求 AI 追问 / 整理成文
// 追问过程不落库：累积问答由前端持有，每次请求整包回传（见 useRequirementRefinement.js）。
export const getWorkbenchRequirementAiModel = (id) => request({
  url: `/test-workbench/requirements/${id}/ai-model`,
  method: 'get',
  skipErrorToast: true,
})
export const saveWorkbenchRequirementAi = (id, data) => request({ url: `/test-workbench/requirements/${id}/ai-refine/save`, method: 'post', data })

const streamWorkbenchRequirementAi = (url, data, onEvent, signal) => streamAiRequest(url, data, onEvent, signal)

// data: { round, history, answers, supplement, initial_content? }
export const askWorkbenchRequirementAiStream = (id, data, onEvent, signal) => streamWorkbenchRequirementAi(`/test-workbench/requirements/${id}/ai-refine/ask/stream`, data, onEvent, signal)
// data: { history }
export const composeWorkbenchRequirementAiStream = (id, data, onEvent, signal) => streamWorkbenchRequirementAi(`/test-workbench/requirements/${id}/ai-refine/compose/stream`, data, onEvent, signal)
export const compareWorkbenchRequirementAiStream = (id, data, onEvent, signal) => streamWorkbenchRequirementAi(`/test-workbench/requirements/${id}/ai-refine/compare/stream`, data, onEvent, signal)

// 合并需求
export const getWorkbenchMergedRequirements = (version_id) => request({ url: '/test-workbench/merged-requirements', method: 'get', params: { version_id } })
export const getWorkbenchMergedRequirement = (id) => request({ url: `/test-workbench/merged-requirements/${id}`, method: 'get' })
export const remergeWorkbenchMergedRequirementPreview = (id) => request({ url: `/test-workbench/merged-requirements/${id}/remerge-preview`, method: 'post', timeout: 120000 })
// 重新合并保存：随正文一并回传最新来源需求 id，覆盖 source_requirement_ids 并清除「可能过期」标记
export const remergeSaveWorkbenchMergedRequirement = (id, data) => request({ url: `/test-workbench/merged-requirements/${id}/remerge-save`, method: 'post', data })
export const updateWorkbenchMergedRequirement = (id, data) => request({ url: `/test-workbench/merged-requirements/${id}`, method: 'put', data })
export const deleteWorkbenchMergedRequirement = (id) => request({ url: `/test-workbench/merged-requirements/${id}`, method: 'delete' })

// 合并需求 AI 补全（复用需求 AI 追问 / 整理成文交互）
// 「对话式合并」保存前没有任何业务记录：作用域 { version_id, source_type, source_ids, title }
// 与累积问答一起每次回传，后端重新读取来源需求正文。
export const getWorkbenchMergeRequirementAiModel = () => request({
  url: '/test-workbench/requirements/merge-ai-model',
  method: 'get',
  skipErrorToast: true,
})
export const askWorkbenchMergeAiStream = (data, onEvent, signal) => streamWorkbenchRequirementAi('/test-workbench/requirements/merge-ai/ask/stream', data, onEvent, signal)
export const composeWorkbenchMergeAiStream = (data, onEvent, signal) => streamWorkbenchRequirementAi('/test-workbench/requirements/merge-ai/compose/stream', data, onEvent, signal)
export const compareWorkbenchMergeAiStream = (data, onEvent, signal) => streamWorkbenchRequirementAi('/test-workbench/requirements/merge-ai/compare/stream', data, onEvent, signal)
export const saveWorkbenchMergeAi = (data) => request({ url: '/test-workbench/requirements/merge-ai/save', method: 'post', data })
export const confirmWorkbenchMergedRequirement = (id) => request({ url: `/test-workbench/merged-requirements/${id}/confirm`, method: 'post' })
export const batchConfirmWorkbenchMergedRequirements = (data) => request({ url: '/test-workbench/merged-requirements/batch-confirm', method: 'post', data })
export const getWorkbenchMergedRequirementAiModel = (id) => request({
  url: `/test-workbench/merged-requirements/${id}/ai-model`,
  method: 'get',
  skipErrorToast: true,
})
export const saveWorkbenchMergedRequirementAi = (id, data) => request({ url: `/test-workbench/merged-requirements/${id}/ai-refine/save`, method: 'post', data })
export const askWorkbenchMergedRequirementAiStream = (id, data, onEvent, signal) => streamWorkbenchRequirementAi(`/test-workbench/merged-requirements/${id}/ai-refine/ask/stream`, data, onEvent, signal)
export const composeWorkbenchMergedRequirementAiStream = (id, data, onEvent, signal) => streamWorkbenchRequirementAi(`/test-workbench/merged-requirements/${id}/ai-refine/compose/stream`, data, onEvent, signal)
export const compareWorkbenchMergedRequirementAiStream = (id, data, onEvent, signal) => streamWorkbenchRequirementAi(`/test-workbench/merged-requirements/${id}/ai-refine/compare/stream`, data, onEvent, signal)

// 用例
export const getWorkbenchTestCaseAiModel = () => request({ url: '/test-workbench/test-cases/ai-model', method: 'get', skipErrorToast: true })
export const askWorkbenchTestCasePreflightStream = (data, onEvent, signal) => streamWorkbenchRequirementAi('/test-workbench/test-cases/preflight/ask/stream', data, onEvent, signal)
export const generateWorkbenchTestCases = (data) => request({ url: '/test-workbench/test-cases/generate', method: 'post', data, timeout: 600000, skipErrorToast: true })
export const createWorkbenchTestCase = (data) => request({ url: '/test-workbench/test-cases', method: 'post', data })
export const batchCreateWorkbenchTestCases = (data) => request({ url: '/test-workbench/test-cases/batch', method: 'post', data })
export const updateWorkbenchTestCase = (id, data) => request({ url: `/test-workbench/test-cases/${id}`, method: 'put', data })
export const confirmWorkbenchTestCase = (id) => request({ url: `/test-workbench/test-cases/${id}/confirm`, method: 'post' })
export const batchConfirmWorkbenchTestCases = (data) => request({ url: '/test-workbench/test-cases/batch-confirm', method: 'post', data })
export const batchCancelConfirmWorkbenchTestCases = (data) => request({ url: '/test-workbench/test-cases/batch-cancel-confirm', method: 'post', data })
export const batchDeleteWorkbenchTestCases = (data) => request({ url: '/test-workbench/test-cases/batch-delete', method: 'post', data })
export const batchExecuteWorkbenchTestCases = (data) => request({ url: '/test-workbench/test-cases/batch-execute', method: 'post', data })
export const deleteWorkbenchTestCase = (id) => request({ url: `/test-workbench/test-cases/${id}`, method: 'delete' })

// 执行
export const createWorkbenchExecution = (data) => request({ url: '/test-workbench/executions', method: 'post', data })
export const getWorkbenchTestCaseExecutions = (testCaseId) => request({ url: `/test-workbench/test-cases/${testCaseId}/executions`, method: 'get' })
export const correctWorkbenchExecution = (executionId, data) => request({ url: `/test-workbench/executions/${executionId}`, method: 'put', data })

// Bug
export const createWorkbenchBug = (data) => request({ url: '/test-workbench/bugs', method: 'post', data })
export const updateWorkbenchBug = (id, data) => request({ url: `/test-workbench/bugs/${id}`, method: 'put', data })
export const deleteWorkbenchBug = (id) => request({ url: `/test-workbench/bugs/${id}`, method: 'delete' })
export const batchDeleteWorkbenchBugs = (data) => request({ url: '/test-workbench/bugs/batch-delete', method: 'post', data })
export const getWorkbenchBugTransitions = (id) => request({ url: `/test-workbench/bugs/${id}/transitions`, method: 'get' })
export const assignWorkbenchBug = (id, data) => request({ url: `/test-workbench/bugs/${id}/assign`, method: 'post', data })
export const resolveWorkbenchBug = (id, data) => request({ url: `/test-workbench/bugs/${id}/resolve`, method: 'post', data })
export const verifyWorkbenchBug = (id, data) => request({ url: `/test-workbench/bugs/${id}/verify`, method: 'post', data })
export const transferWorkbenchBugToLegacy = (id) => request({ url: `/test-workbench/bugs/${id}/transfer-to-legacy`, method: 'post' })

// 遗留项
export const createWorkbenchLegacyItem = (data) => request({ url: '/test-workbench/legacy-items', method: 'post', data })
export const updateWorkbenchLegacyItem = (id, data) => request({ url: `/test-workbench/legacy-items/${id}`, method: 'put', data })
export const deleteWorkbenchLegacyItem = (id) => request({ url: `/test-workbench/legacy-items/${id}`, method: 'delete' })
