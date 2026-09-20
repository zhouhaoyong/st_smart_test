<template>
  <el-tabs v-model="tab" class="result-tabs">
    <el-tab-pane label="接口信息" name="info">
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="接口名称">{{ name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="请求方法">
          <el-tag size="small">{{ method || '-' }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="请求路径">{{ url || '-' }}</el-descriptions-item>
        <el-descriptions-item label="完整请求地址">
          <span class="full-url">{{ fullUrl || '-' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="请求体类型">{{ bodyType || '无' }}</el-descriptions-item>
      </el-descriptions>
    </el-tab-pane>
    <el-tab-pane :label="`查询参数 (${queryParamCount})`" name="query">
      <CodePreview :content="queryParamsText" />
    </el-tab-pane>
    <el-tab-pane label="请求体" name="body">
      <CodePreview :content="bodyText" :copy-disabled="bodyCopyDisabled" />
    </el-tab-pane>
    <el-tab-pane :label="`请求头 (${headerCount})`" name="headers">
      <CodePreview :content="headersText" />
    </el-tab-pane>
  </el-tabs>
</template>

<script setup>
import { computed } from 'vue'
import CodePreview from '@/components/CodePreview.vue'

const props = defineProps({
  activeTab: { type: String, default: 'info' },
  name: { type: String, default: '' },
  method: { type: String, default: '' },
  url: { type: String, default: '' },
  fullUrl: { type: String, default: '' },
  bodyType: { type: String, default: '' },
  queryParamsText: { type: String, default: '(无)' },
  bodyText: { type: String, default: '(无)' },
  headersText: { type: String, default: '(无)' },
  queryParamCount: { type: Number, default: 0 },
  headerCount: { type: Number, default: 0 },
  bodyCopyDisabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:activeTab'])

const tab = computed({
  get: () => props.activeTab,
  set: value => emit('update:activeTab', value),
})
</script>

<style scoped>
.full-url {
  display: inline-block;
  max-width: 100%;
  font-family: SFMono-Regular, Consolas, Monaco, monospace;
  word-break: break-all;
}
.result-tabs :deep(.el-tabs__header) { margin-bottom: 12px; }
</style>
