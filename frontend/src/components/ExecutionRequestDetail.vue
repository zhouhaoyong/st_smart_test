<template>
  <div class="execution-request-detail">
    <div class="request-meta">
      <span>请求地址：{{ requestUrl || '-' }}</span>
    </div>
    <el-tabs v-model="tab" class="detail-tabs">
      <el-tab-pane label="查询参数" name="params">
        <pre class="code-block">{{ paramsText || '(无)' }}</pre>
      </el-tab-pane>
      <el-tab-pane label="路径参数" name="path">
        <pre class="code-block">{{ pathParamsText || '(无)' }}</pre>
      </el-tab-pane>
      <el-tab-pane label="请求体" name="body">
        <pre class="code-block">{{ bodyText || '(无)' }}</pre>
      </el-tab-pane>
      <el-tab-pane label="请求头" name="headers">
        <pre class="code-block">{{ headersText || '(无)' }}</pre>
      </el-tab-pane>
      <el-tab-pane v-if="showProxy" label="代理" name="proxy">
        <pre class="code-block">{{ proxyText || '(无)' }}</pre>
      </el-tab-pane>
      <el-tab-pane v-if="showService" label="服务" name="service">
        <ServiceInfoTable :service="service" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ServiceInfoTable from '@/components/ServiceInfoTable.vue'

const props = defineProps({
  // 传 'auto' 表示交给组件自动定位到第一个有数据的页签
  activeTab: { type: String, default: 'body' },
  // 请求方法：只影响自动定位的优先级，查询类先看查询参数，其余先看请求体
  method: { type: String, default: '' },
  requestUrl: { type: String, default: '' },
  paramsText: { type: String, default: '' },
  pathParamsText: { type: String, default: '' },
  bodyText: { type: String, default: '' },
  headersText: { type: String, default: '' },
  proxyText: { type: String, default: '' },
  service: { type: [Object, String, Array], default: null },
  showProxy: { type: Boolean, default: true },
  showService: { type: Boolean, default: true },
})

const emit = defineEmits(['update:activeTab'])

// 查询参数、路径参数、请求体、请求头恒定展示（无数据时显示「(无)」），
// 保证调试、运行结果、测试报告的页签结构完全一致，不因数据有无而变化
const availableTabs = computed(() => {
  const tabs = ['params', 'path', 'body', 'headers']
  if (props.showProxy) tabs.push('proxy')
  if (props.showService) tabs.push('service')
  return tabs
})

// 判断页签里到底有没有内容：各调用方格式化空值的写法不一致（运行结果给 {}、[]，
// 报告已归一成空串，curl 工具给「(无)」），只看文本非空会把自动定位带偏
const EMPTY_TEXTS = new Set(['', '{}', '[]', 'null', 'undefined', '""', '(无)'])
const hasTabData = (text) => {
  const trimmed = String(text ?? '').trim()
  if (EMPTY_TEXTS.has(trimmed)) return false
  try {
    const parsed = JSON.parse(trimmed)
    if (parsed === null) return false
    if (Array.isArray(parsed)) return parsed.length > 0
    if (typeof parsed === 'object') return Object.keys(parsed).length > 0
  } catch { /* 非 JSON 文本按原文判断 */ }
  return true
}

// 查询类请求先看查询参数，其余方法先看请求体；代理、服务不参与自动定位
const READ_METHODS = ['GET', 'HEAD', 'OPTIONS']
const tabPriority = computed(() => (
  READ_METHODS.includes(String(props.method || '').trim().toUpperCase())
    ? ['params', 'path', 'body', 'headers']
    : ['body', 'params', 'path', 'headers']
))

// 自动定位到优先级里第一个有数据的页签，都没有数据时落在优先级第一项
const autoTab = computed(() => {
  const textOf = {
    params: props.paramsText,
    path: props.pathParamsText,
    body: props.bodyText,
    headers: props.headersText,
  }
  return tabPriority.value.find(name => hasTabData(textOf[name])) || tabPriority.value[0]
})

// 自动定位只决定初始落点：用户手动切过页签后父级持有具体值，不会再跳回去
const tab = computed({
  get: () => {
    if (props.activeTab === 'auto') return autoTab.value
    return availableTabs.value.includes(props.activeTab) ? props.activeTab : 'body'
  },
  set: value => emit('update:activeTab', value),
})
</script>

<style scoped>
.request-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 10px 0 12px;
  color: #606266;
  font-size: 13px;
  word-break: break-all;
}
.detail-tabs { margin-top: 2px; }
.detail-tabs :deep(.el-tabs__content) { padding-top: 8px; }
.detail-tabs :deep(.el-tab-pane) { min-height: 0; }
.code-block {
  max-height: min(280px, 32vh);
  overflow: auto;
  margin: 0;
  padding: 10px;
  border: 1px solid #edf1f7;
  border-radius: 6px;
  background: #f7f9fc;
  font-family: SFMono-Regular, Consolas, monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
