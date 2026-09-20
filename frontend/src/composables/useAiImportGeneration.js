/**
 * 接口列表 —— 分批生成用例。
 *
 * 为什么要分批发请求：后端的超时预算是「每次模型调用各自一份」，而前端的超时
 * 预算原先覆盖「整个生成请求」。接口一多就要串行跑好几批，后端还没跑完前端就
 * 先掐断，已完成批次的成果全部丢失、额度却照扣。
 * 改成前端先取分批计划、再逐批发请求后：每批各自享有完整超时预算，进度可见，
 * 可中途停止，且每批一返回就落到界面上，停止或失败都不会丢掉已完成的部分。
 *
 * 失败不自动阻断：任一批失败都只记账并继续下一批，最后汇总交给用户决定是否重试。
 */
import { ref, computed } from 'vue'
import { interfaceCaseGenerationGeneratePlan, interfaceCaseGenerationGenerate } from '@/api/aiImport'
import { combineAiUsage } from '@/utils/aiUsageSummary'

// 同时兼容原来的 axios 取消和流式 fetch 的 AbortError。
export function isCanceledError(e) {
  return e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError' || e?.name === 'AbortError'
}

function responseDetailMessage(value) {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    return value
      .map(item => (typeof item === 'string' ? item : item?.msg || item?.message || ''))
      .filter(Boolean)
      .join('；')
  }
  return value?.message || value?.msg || ''
}

// 以后端 message/detail 为准，取不到时才退回网络层文案
export function extractErrorMessage(e) {
  const data = e?.response?.data
  const detail = responseDetailMessage(e?.data?.detail || data?.detail)
  const networkError = !data && (
    e?.code === 'ERR_NETWORK' || String(e?.message || '').toLowerCase() === 'network error'
  )
  if (networkError) return '网络连接失败，未能连接到 AI 生成服务，请检查服务状态或网络连接'
  return e?.data?.message || data?.message || detail || e?.message || '生成失败，未获取到具体原因'
}

export function normalizeGenerationFailureReason(e) {
  const detail = typeof e === 'string' ? e : extractErrorMessage(e)
  const lower = detail.toLowerCase()
  if (detail.includes('超时') || lower.includes('timeout') || lower.includes('timed out')) {
    return {
      type: 'timeout',
      message: 'AI模型响应超时，等待超过10分钟',
      detail,
    }
  }
  return { type: 'error', message: detail, detail }
}

/**
 * 校验每批生成接口的返回契约。
 * 后端即使模型调用失败，也应返回每个接口的系统基础用例；缺少该结果时
 * 不能继续按成功批次处理，否则界面会把“0 个用例”误显示为成功。
 */
export function validateGenerationResult(data, batchIds) {
  const returnedInterfaces = Array.isArray(data?.interfaces) ? data.interfaces : []
  const returned = new Map(returnedInterfaces.map(item => [String(item?.temp_id || ''), item]))
  const invalidIds = (batchIds || []).filter(id => {
    const item = returned.get(String(id))
    return !item || !Array.isArray(item.generated_cases) || item.generated_cases.length === 0
  })
  if (invalidIds.length) {
    const error = new Error('生成服务未返回有效的用例结果，请检查模型配置后重试')
    error.invalidTempIds = invalidIds
    throw error
  }
  return data
}

// 失败明细在弹窗里全文展示，过多会撑爆弹窗；超出部分由「另有 N 个」兜底
const MAX_FAILED_DETAILS = 50

/**
 * @param {object} ctx 由主弹窗提供的上下文取值函数
 * @param {() => string} ctx.previewId
 * @param {() => number|string} ctx.projectId
 * @param {() => string} ctx.mode 当前生成模式
 * @param {() => number|null} ctx.modelId 当前用例生成模型
 * @param {() => object} [ctx.serviceOverrides] 界面上当前的服务归属映射，随请求同步进预览会话
 * @param {() => string} ctx.nameOf 按 temp_id 取接口名，用于请求级失败时的明细
 * @param {(data: object) => void} ctx.onBatchDone 每批成功后立刻回填列表
 * @param {(ids: string[], failure: object) => void} [ctx.onBatchFailed] 请求级失败后回填失败状态
 */
export function useAiImportBatchGeneration(ctx) {
  const generating = ref(false)
  const targetIds = ref([])
  const totalBatches = ref(0)
  const currentBatch = ref(0)
  const currentBatchStatus = ref('未开始')
  const completedBatches = ref(0)
  const failedBatches = ref(0)
  const pendingBatches = ref(0)
  const doneInterfaces = ref(0)
  const usedCalls = ref(0)

  let abort = null
  let stopped = false

  // 等待卡片上的真实进度：当前批次与已处理接口数
  const progressText = computed(() => {
    const total = targetIds.value.length
    if (!totalBatches.value || currentBatch.value === 0 || currentBatchStatus.value === '准备中') {
      return `正在准备处理 ${total} 个接口…`
    }

    const batch = `${currentBatch.value}/${totalBatches.value}`
    const prefix = currentBatchStatus.value === '失败'
      ? `第 ${batch} 批接口处理失败`
      : currentBatchStatus.value === '已完成'
        ? `已完成第 ${batch} 批接口`
        : currentBatchStatus.value === '已停止，结果未确认'
          ? `已停止处理第 ${batch} 批接口`
          : `正在处理第 ${batch} 批接口`

    return `${prefix} · 已处理 ${doneInterfaces.value}/${total} 个接口`
  })

  function stop() {
    stopped = true
    if (generating.value && currentBatch.value) currentBatchStatus.value = '已停止，结果未确认'
    if (abort) abort.abort()
  }

  function reset() {
    stop()
    generating.value = false
    targetIds.value = []
    totalBatches.value = 0
    currentBatch.value = 0
    currentBatchStatus.value = '未开始'
    completedBatches.value = 0
    failedBatches.value = 0
    pendingBatches.value = 0
    doneInterfaces.value = 0
    usedCalls.value = 0
    abort = null
  }

  /**
   * 逐批生成，返回可直接喂给结果弹窗的汇总。
   * @param {string[]} ids 本次要生成的接口 temp_id
   */
  async function run(ids) {
    const targets = Array.from(new Set(ids || []))
    if (!targets.length) return null

    stopped = false
    generating.value = true
    targetIds.value = targets
    totalBatches.value = 0
    currentBatch.value = 0
    currentBatchStatus.value = '准备中'
    completedBatches.value = 0
    failedBatches.value = 0
    pendingBatches.value = 0
    doneInterfaces.value = 0
    usedCalls.value = 0

    const base = {
      preview_id: ctx.previewId(),
      project_id: Number(ctx.projectId()),
      mode: ctx.mode(),
      // 界面上调整过的服务归属随请求上报，保证模型拿到的接口信息与界面一致
      service_overrides: ctx.serviceOverrides ? ctx.serviceOverrides() : undefined,
    }
    let generatedCases = 0
    const failedIds = new Set()
    const failedDetails = []
    const batchResults = []
    const usageParts = []

    function summarize(outcome, errorMessage = '') {
      return {
        outcome,
        single: targets.length === 1,
        targetCount: targets.length,
        aiCallCount: usedCalls.value,
        totalBatches: totalBatches.value,
        completedBatches: completedBatches.value,
        failedBatches: failedBatches.value,
        pendingBatches: pendingBatches.value,
        currentBatch: currentBatch.value,
        currentBatchStatus: currentBatchStatus.value,
        processedInterfaces: doneInterfaces.value,
        generatedInterfaces: targets.length - failedIds.size,
        generatedCases,
        failedInterfaces: failedIds.size,
        failedDetails: failedDetails.slice(0, MAX_FAILED_DETAILS),
        batchResults: batchResults.slice(),
        retryIds: Array.from(failedIds),
        errorMessage,
        usage: usageParts.length ? combineAiUsage(usageParts) : null,
      }
    }

    try {
      // ---------- 1. 取分批计划：纯计算，不消耗额度 ----------
      let plan = null
      abort = new AbortController()
      try {
        plan = await interfaceCaseGenerationGeneratePlan({ ...base, temp_ids: targets }, { signal: abort.signal })
      } catch (e) {
        if (isCanceledError(e)) {
          currentBatchStatus.value = '已停止，结果未确认'
          return summarize('canceled', '你已停止本次生成，尚未开始产出用例。')
        }
        const reason = normalizeGenerationFailureReason(e)
        targets.forEach(id => failedIds.add(id))
        ctx.onBatchFailed?.(targets, reason)
        failedDetails.push(...targets.map(id => ({
          name: ctx.nameOf(id),
          reason: reason.message,
          detail: reason.detail,
          type: reason.type,
        })))
        return summarize('failed', reason.message)
      }

      const batches = plan?.batches || []
      totalBatches.value = batches.length
      pendingBatches.value = batches.length
      if (!batches.length) {
        targets.forEach(id => failedIds.add(id))
        currentBatchStatus.value = '无可处理批次'
        const reason = { type: 'error', message: '没有可生成的接口，请返回上一步重新选择。', detail: '' }
        ctx.onBatchFailed?.(targets, reason)
        failedDetails.push(...targets.map(id => ({
          name: ctx.nameOf(id),
          reason: reason.message,
          detail: reason.detail,
          type: reason.type,
        })))
        return summarize('failed', '没有可生成的接口，请返回上一步重新选择。')
      }

      // ---------- 2. 逐批生成：一批一个请求，各自独立超时 ----------
      for (const batch of batches) {
        if (stopped) break
        currentBatch.value = batch.index
        currentBatchStatus.value = '处理中'
        const batchIds = batch.temp_ids || []
        abort = new AbortController()
        try {
          const data = await interfaceCaseGenerationGenerate({
            ...base,
            temp_ids: batchIds,
            selected_model_id: batch.requires_model ? ctx.modelId() : null,
            batch_index: batch.index,
            total_batches: totalBatches.value,
          }, { signal: abort.signal })
          validateGenerationResult(data, batchIds)
          // 每批当场回填，用户能眼看着用例往上涨；中途停止也不会丢
          ctx.onBatchDone(data)
          const summary = data?.generation_summary || {}
          if (summary.usage) usageParts.push(summary.usage)
          usedCalls.value += Number(summary.ai_call_count || 0)
          generatedCases += Number(summary.generated_cases || 0)
          for (const item of summary.failed_details || []) {
            if (item?.temp_id) failedIds.add(item.temp_id)
            const failure = normalizeGenerationFailureReason(item?.reason || '未返回失败原因')
            failedDetails.push({
              batchIndex: batch.index,
              name: item?.name || item?.temp_id || '未知接口',
              reason: failure.message,
              detail: failure.detail,
              type: failure.type,
            })
          }
          batchResults.push({
            index: batch.index,
            interfaceCount: batchIds.length,
            status: summary.failed_interfaces ? 'partial' : 'success',
            generatedCases: Number(summary.generated_cases || 0),
            failedInterfaces: Number(summary.failed_interfaces || 0),
          })
          completedBatches.value += 1
          pendingBatches.value = Math.max(0, totalBatches.value - completedBatches.value - failedBatches.value)
          currentBatchStatus.value = '已完成'
        } catch (e) {
          if (isCanceledError(e)) {
            stopped = true
            currentBatchStatus.value = '已停止，结果未确认'
            break
          }
          // 请求级失败（超时、断网等）：整批记账后继续下一批，不自动阻断
          const reason = normalizeGenerationFailureReason(e)
          ctx.onBatchFailed?.(batchIds, reason)
          for (const id of batchIds) {
            failedIds.add(id)
            failedDetails.push({
              batchIndex: batch.index,
              name: ctx.nameOf(id),
              reason: reason.message,
              detail: reason.detail,
              type: reason.type,
            })
          }
          batchResults.push({
            index: batch.index,
            interfaceCount: batchIds.length,
            status: 'failed',
            generatedCases: 0,
            failedInterfaces: batchIds.length,
            reason: reason.message,
            type: reason.type,
          })
          failedBatches.value += 1
          pendingBatches.value = Math.max(0, totalBatches.value - completedBatches.value - failedBatches.value)
          currentBatchStatus.value = '失败'
        }
        doneInterfaces.value += batchIds.length
      }
    } finally {
      generating.value = false
      abort = null
    }

    if (stopped) {
      return summarize('canceled', generatedCases
        ? `你已停止本次生成，已完成的 ${generatedCases} 个用例保留在列表中。`
        : '你已停止本次生成，尚未产出用例。')
    }
    if (!generatedCases) {
      currentBatchStatus.value = failedBatches.value ? '已完成，全部批次失败' : currentBatchStatus.value
      return summarize('failed', failedDetails.length
        ? (failedDetails[0]?.reason || '')
        : '接口信息可能不完整，请检查后重试。')
    }
    currentBatchStatus.value = failedBatches.value ? '已完成，存在失败批次' : '全部完成'
    return summarize(failedIds.size ? 'partial' : 'success')
  }

  return {
    generating,
    targetIds,
    totalBatches,
    currentBatch,
    currentBatchStatus,
    completedBatches,
    failedBatches,
    pendingBatches,
    doneInterfaces,
    usedCalls,
    progressText,
    run,
    stop,
    reset,
  }
}
