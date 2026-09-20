<template>
  <el-dialog v-model="visible" title="模型详情" width="min(760px, calc(100vw - 40px))" top="8vh" append-to-body class="model-detail-dialog">
    <div v-if="model" class="model-detail">
      <div class="detail-hero">
        <div class="detail-hero-copy">
          <div class="detail-eyebrow">模型配置</div>
          <div class="detail-hero-name">{{ model.name || '未命名模型' }}</div>
          <div class="detail-hero-model">{{ model.model || '—' }}</div>
        </div>
        <el-tag :type="model.scope === 'platform' ? 'success' : 'primary'" effect="light" size="small">{{ scopeText }}</el-tag>
      </div>

      <div class="detail-grid">
        <section class="detail-section">
          <div class="detail-section-title"><span class="detail-section-dot" />模型信息</div>
          <el-descriptions :column="1" size="small" class="detail-descriptions">
            <el-descriptions-item label="模型别名">{{ model.name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="模型名称">{{ model.model || '—' }}</el-descriptions-item>
            <el-descriptions-item label="模型范围">{{ scopeText }}</el-descriptions-item>
            <el-descriptions-item :label="principalLabel">{{ principalName || '—' }}</el-descriptions-item>
            <el-descriptions-item v-if="canViewConnection" label="接口地址">
              <span class="detail-breakable">{{ model.base_url || '未配置' }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </section>

        <section class="detail-section">
          <div class="detail-section-title"><span class="detail-section-dot" />功能与状态</div>
          <el-descriptions :column="1" size="small" class="detail-descriptions">
            <el-descriptions-item label="状态">
              <el-tag :type="statusTagType" size="small">{{ statusText }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="能力检测">
              <el-tag :type="capabilityTagType(model.connectivity_status)" size="small">{{ connectivityText }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="思考能力">
              <el-tag :type="capabilityTagType(model.reasoning_status)" size="small">{{ reasoningText }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="用量返回能力">
              <el-tag :type="capabilityTagType(model.usage_status)" size="small">{{ usageText }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item v-if="model.scope === 'personal'" label="平台模型额度">{{ platformQuotaText }}</el-descriptions-item>
            <el-descriptions-item v-if="model.scope === 'personal'" label="用户模型额度">{{ personalQuotaText }}</el-descriptions-item>
            <el-descriptions-item v-if="model.invalidated_reason" label="失效原因">
              <span class="detail-breakable detail-danger">{{ model.invalidated_reason }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </section>
      </div>
    </div>
    <el-empty v-else description="暂无模型信息" :image-size="64" />

    <template #footer>
      <el-button type="primary" @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: Boolean,
  model: { type: Object, default: null },
  // owner: 本人配置；superadmin: 超管查看他人模型；member: 普通成员查看平台模型。
  viewerMode: { type: String, default: 'member' },
})
const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})
const scopeText = computed(() => {
  if (props.model?.scope === 'platform') return '平台模型'
  return props.viewerMode === 'superadmin' ? '用户模型' : '我的模型'
})
const principalLabel = computed(() => props.model?.scope === 'personal' ? '模型使用人' : '模型创建人')
const principalName = computed(() => props.model?.scope === 'personal'
  ? (props.model?.owner_name || props.model?.creator_name)
  : props.model?.creator_name)
const quotaText = quota => {
  if (!quota || Number(quota.daily_limit || 0) <= 0) return '未配置'
  return `今日剩余 ${Math.max(0, Number(quota.remaining || 0))} / ${quota.daily_limit} 次`
}
const platformQuotaText = computed(() => quotaText(props.model?.platform_quota))
const personalQuotaText = computed(() => quotaText(props.model?.personal_quota))
const canViewConnection = computed(() => ['owner', 'superadmin'].includes(props.viewerMode))
const statusText = computed(() => props.model?.enabled ? '启用' : '停用')
const statusTagType = computed(() => props.model?.enabled ? 'success' : 'info')
const connectivityText = computed(() => ({ passed: '已通过', failed: '未通过', unknown: '未检测' }[props.model?.connectivity_status] || '未检测'))
const reasoningText = computed(() => ({ supported: '支持', unsupported: '不支持', unknown: '未检测' }[props.model?.reasoning_status] || '未检测'))
const usageText = computed(() => ({ supported: '可返回', unsupported: '不返回', unknown: '未检测' }[props.model?.usage_status] || '未检测'))

function capabilityTagType(status) {
  return { passed: 'success', supported: 'success', failed: 'danger', unsupported: 'info', unknown: 'warning' }[status] || 'warning'
}
</script>

<style scoped>
.model-detail-dialog :deep(.el-dialog__body) { padding: 8px 24px 18px; }
.model-detail { color: #303133; }
.detail-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 2px 4px 18px;
  margin-bottom: 18px;
  border-bottom: 1px solid #f0f2f5;
}
.detail-hero-copy { min-width: 0; }
.detail-eyebrow { margin-bottom: 6px; color: #909399; font-size: 12px; }
.detail-hero-name { overflow: hidden; color: #1f2937; font-size: 20px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.detail-hero-model { margin-top: 5px; overflow: hidden; color: #64748b; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.detail-hero > :deep(.el-tag) { flex-shrink: 0; margin-top: 5px; }
.detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.detail-section { min-width: 0; overflow: hidden; border: 1px solid #ebeef5; border-radius: 10px; background: #fff; }
.detail-section-title { display: flex; align-items: center; gap: 8px; padding: 12px 14px; border-bottom: 1px solid #ebeef5; background: #f8fafc; color: #303133; font-size: 14px; font-weight: 600; }
.detail-section-dot { width: 6px; height: 16px; border-radius: 3px; background: #409eff; }
.detail-section:nth-child(2) .detail-section-dot { background: #67c23a; }
.detail-descriptions { padding: 2px 14px 8px; }
.detail-descriptions :deep(.el-descriptions__body) { background: transparent; }
.detail-descriptions :deep(.el-descriptions__table) { table-layout: fixed; }
.detail-descriptions :deep(.el-descriptions__cell) { padding: 10px 4px; border-bottom: 1px solid #f2f4f7; }
.detail-descriptions :deep(.el-descriptions__row:last-child .el-descriptions__cell) { border-bottom: none; }
.detail-descriptions :deep(.el-descriptions__label) { width: 92px; color: #64748b; font-weight: 500; }
.detail-descriptions :deep(.el-descriptions__content) { min-width: 0; color: #303133; word-break: break-word; }
.detail-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.detail-muted { color: #a8abb2; }
.detail-breakable { display: inline-block; max-width: 100%; word-break: break-all; }
.detail-danger { color: #f56c6c; }
@media (max-width: 800px) {
  .detail-grid { grid-template-columns: 1fr; }
}
</style>
