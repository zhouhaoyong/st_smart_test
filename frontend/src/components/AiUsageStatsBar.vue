<template>
  <!-- AI 用量公共组件：默认展示对话单轮，也支持导入流程展示阶段合计。
       单轮口径：第 N 轮 | 输入 | 输出 | 缓存(有才展示) | 耗时；阶段合计口径：输入 | 输出 | 缓存 | 总消耗。
       token 各项取模型真实返回值，拿不到的项不展示；阶段合计中的缓存未返回时明确标为未提供；
       耗时统一取「前端计时」（发起→流式结束由前端测量），与后端 elapsed_ms 解耦，避免前后端时间对不上。 -->
  <div
    v-if="variant === 'summary' ? usage : (round || round === 0)"
    class="ai-usage-bar"
    :class="{
      'ai-usage-bar--summary': variant === 'summary',
      'ai-usage-bar--summary-grid': variant === 'summary' && layout === 'grid',
    }"
  >
    <template v-if="variant === 'summary'">
      <span class="usage-summary-title">Token 消耗</span>
      <span class="usage-summary-item">
        <span>输入</span>
        <el-tag class="usage-summary-value" size="small" type="success" effect="light" round>{{ formatAiTokenCount(usage.input_tokens) }}</el-tag>
      </span>
      <span class="usage-summary-item">
        <span>输出</span>
        <el-tag class="usage-summary-value" size="small" type="warning" effect="light" round>{{ formatAiTokenCount(usage.output_tokens) }}</el-tag>
      </span>
      <span class="usage-summary-item">
        <span>缓存</span>
        <el-tag class="usage-summary-value" size="small" type="info" effect="light" round>{{ usage.cache_tokens == null ? '未提供' : formatAiTokenCount(usage.cache_tokens) }}</el-tag>
      </span>
      <span class="usage-summary-item">
        <span>总消耗</span>
        <el-tag class="usage-summary-value" size="small" type="primary" effect="light" round>{{ formatAiTokenCount(usage.total_tokens) }}</el-tag>
      </span>
    </template>
    <template v-else>
      <!-- 顺序：先轮次 + 用量统计，再模型信息（模型信息更偏参考、放在末尾） -->
      <el-tag class="usage-round" size="small" type="primary" effect="light" round>第 {{ displayRound }} 轮</el-tag>
      <span v-if="usage && usage.input_tokens != null" class="usage-item">
        <el-tag size="small" type="success" effect="light" round>输入 {{ fmt(usage.input_tokens) }}</el-tag>
      </span>
      <span v-if="usage && usage.output_tokens != null" class="usage-item">
        <el-tag size="small" type="warning" effect="light" round>输出 {{ fmt(usage.output_tokens) }}</el-tag>
      </span>
      <span v-if="usage && usage.cache_tokens != null" class="usage-item">
        <el-tag size="small" type="info" effect="light" round>缓存 {{ fmt(usage.cache_tokens) }}</el-tag>
      </span>
      <span v-if="elapsedText" class="usage-item">
        <el-tag size="small" effect="light" round>耗时 {{ elapsedText }}</el-tag>
      </span>
      <span v-if="modelText" class="usage-item usage-model">
        <el-tag size="small" effect="plain" round>
          <span :title="modelTitle">{{ modelText }}</span>
        </el-tag>
      </span>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatAiTokenCount } from '@/utils/aiUsageSummary'

const props = defineProps({
  // 后端 0 基轮次（首轮补全为 0，之后每次提交 +1）；整理成文步骤沿用对话已进行的轮数
  round: { type: [Number, String], default: 0 },
  // 归一后的用量：{ input_tokens, output_tokens, cache_tokens, total_tokens }，可为 null
  usage: { type: Object, default: null },
  // summary 用于阶段合计；round 用于工作台单轮展示，默认保持原有行为。
  variant: { type: String, default: 'round' },
  // summary 默认横向展示；明细弹窗可切换为 2×2，避免窄弹窗内信息拥挤。
  layout: {
    type: String,
    default: 'inline',
    validator: value => ['inline', 'grid'].includes(value),
  },
  // 本轮耗时(ms)：统一取「前端计时」，避免与后端 elapsed_ms 口径不一致导致展示数字对不上。
  // 异常（停止 / 报错）未产出时由上层不传（null），本条不展示耗时。
  elapsedMs: { type: [Number, String], default: null },
  // 本轮实际所用模型及调用后额度：{ alias, scope, quota:{ used, limit, remaining } }，可为 null。
  // 用于展示「模型别名｜模型类型｜今日已用：x次｜今日剩余：Y次」，别名超 10 字省略、悬浮显示全称。
  model: { type: Object, default: null },
})

// 别名超 10 字省略；完整别名通过 title 悬浮展示。
const aliasDisplay = computed(() => {
  const alias = String(props.model?.alias || '').trim() || '未命名模型'
  return alias.length > 10 ? `${alias.slice(0, 10)}…` : alias
})
const modelTitle = computed(() => String(props.model?.alias || '').trim() || '未命名模型')
const modelTypeLabel = computed(() => (props.model?.scope === 'personal' ? '我的模型' : '平台模型'))
// 额度文案：limit<0 不限；未配置(空/<=0)提示未配置；否则展示已用与剩余。
const quotaText = computed(() => {
  const quota = props.model?.quota
  if (!quota) return '额度未配置'
  const limit = Number(quota.limit)
  if (limit < 0) return '额度不限'
  if (!Number.isFinite(limit) || limit <= 0) return '额度未配置'
  const used = Number(quota.used)
  const remaining = quota.remaining == null
    ? Math.max(0, limit - (Number.isFinite(used) ? used : 0))
    : Math.max(0, Number(quota.remaining))
  const usedText = Number.isFinite(used) ? used : 0
  return `今日已用：${usedText}次｜今日剩余：${remaining}次`
})
const modelText = computed(() => (
  props.model?.alias || props.model?.scope
    ? `${aliasDisplay.value}｜${modelTypeLabel.value}｜${quotaText.value}`
    : ''
))

// 展示层从 1 起：后端 0 基（is_followup/收敛闸门依赖 0 基，不改），仅在这里 +1 供用户阅读
const displayRound = computed(() => Number(props.round || 0) + 1)

// token 数按量级缩写，避免长串数字造成"用了好多"的错觉：
// <1000 显示原值；≥1000 显示 K；≥100万 显示 M，均保留 2 位小数。
const fmt = value => {
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value ?? '')
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(2)}K`
  return String(n)
}

// 耗时：<1s 显示毫秒，≥1s 显示秒（保留 1 位小数）；未计时或异常值（null / 负数）不展示
const elapsedText = computed(() => {
  const ms = Number(props.elapsedMs)
  if (!Number.isFinite(ms) || ms < 0) return ''
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
})
</script>

<style scoped>
.ai-usage-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 12px;
  margin-top: 12px;
  padding-top: 9px;
  border-top: 1px dashed var(--el-border-color-lighter);
  font-size: 12px;
  line-height: 1.6;
}
.ai-usage-bar--summary {
  width: fit-content;
  max-width: 100%;
  align-self: center;
  margin-top: 0;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  box-sizing: border-box;
  display: grid;
  grid-template-columns: max-content repeat(4, max-content);
  justify-content: start;
  gap: 6px 14px;
  text-align: left;
}
.usage-summary-title {
  color: var(--el-text-color-secondary);
  font-weight: 600;
  white-space: nowrap;
}
.usage-summary-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.usage-summary-value {
  min-width: 42px;
  justify-content: center;
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}
@media (max-width: 640px) {
  .ai-usage-bar--summary {
    grid-template-columns: max-content repeat(2, max-content);
  }
  .usage-summary-title { grid-column: 1 / -1; }
}
.ai-usage-bar--summary-grid {
  width: 100%;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 14px;
}
.ai-usage-bar--summary-grid .usage-summary-title {
  grid-column: 1 / -1;
  font-size: 14px;
}
.ai-usage-bar--summary-grid .usage-summary-item {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color);
}
.ai-usage-bar--summary-grid .usage-summary-value {
  font-size: 14px;
}
@media (max-width: 640px) {
  .ai-usage-bar--summary-grid {
    grid-template-columns: 1fr;
  }
}
/* 轮次做成小胶囊，与右侧彩色用量标签区分开 */
.usage-round {
  font-weight: 600;
  white-space: nowrap;
}
.usage-item {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}
/* 模型+额度行：略强调，超长时省略优先保证别名可读 */
.usage-model :deep(.el-tag) {
  max-width: 100%;
  font-weight: 500;
}
.usage-model :deep(.el-tag span) {
  overflow: hidden;
  text-overflow: ellipsis;
}
/* 数值标签：等宽数字更稳，加粗更醒目 */
.usage-item :deep(.el-tag) {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
</style>
