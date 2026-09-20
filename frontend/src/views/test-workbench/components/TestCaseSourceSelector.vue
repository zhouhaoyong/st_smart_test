<template>
  <section class="source-selector">
    <div class="source-selector__header">
      <div>
        <h4>来源需求</h4>
        <p>仅查询当前项目筛选范围内已确认且可用的需求。</p>
      </div>
      <span class="source-selector__scope">当前范围：{{ scopeText }}</span>
    </div>
    <div class="source-selector__type-row">
      <el-radio-group :model-value="sourceType" @change="changeSourceType">
        <el-radio-button label="merged_requirement">AI 合并需求</el-radio-button>
        <el-radio-button label="completed_requirement">AI 补全需求</el-radio-button>
        <el-radio-button label="requirement">原始需求</el-radio-button>
      </el-radio-group>
      <div class="source-selector__selection-summary">
        <span>已选 {{ selectedSources.length }} 条</span>
        <el-button v-if="selectedSources.length" link type="primary" @click="clear">清空选择</el-button>
      </div>
    </div>
    <div class="source-selector__query">
      <el-input v-model="filters.keyword" clearable placeholder="输入需求编号或标题" @keyup.enter="query" />
      <el-button type="primary" @click="query">查询</el-button>
    </div>
    <el-table v-loading="loading" :data="items" height="300" class="source-table">
      <el-table-column width="104" align="left">
        <template #header>
          <el-checkbox
            :model-value="isPageAllSelected"
            :indeterminate="isPagePartiallySelected"
            @change="togglePageSelection"
          >全选本页</el-checkbox>
        </template>
        <template #default="{ row }"><el-checkbox :model-value="isSelected(row)" @change="toggle(row, $event)" /></template>
      </el-table-column>
      <el-table-column prop="title" label="需求标题" min-width="210" show-overflow-tooltip />
      <el-table-column prop="system_name" label="所属系统" width="120" show-overflow-tooltip />
      <el-table-column prop="version_no" label="所属版本" width="110" show-overflow-tooltip />
      <el-table-column prop="created_at" label="创建时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="creator_name" label="创建人" width="110" show-overflow-tooltip>
        <template #default="{ row }">{{ row.creator_name || '—' }}</template>
      </el-table-column>
    </el-table>
    <el-pagination
      v-model:current-page="filters.page" v-model:page-size="filters.page_size"
      :total="total" :page-sizes="[10, 50, 100]" layout="total, sizes, prev, pager, next"
      @current-change="load" @size-change="query"
    />
  </section>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { getWorkbenchTestCaseSources } from '@/api/testWorkbench'
import { formatBeijingTime } from '@/utils/beijingTime'

const props = defineProps({
  projectId: { type: Number, required: true },
  scope: { type: Object, required: true },
  sourceType: { type: String, required: true },
  selectedSources: { type: Array, required: true },
})
const emit = defineEmits(['update:sourceType', 'update:selectedSources', 'error'])
const filters = reactive({ keyword: '', page: 1, page_size: 10 })
const items = ref([])
const total = ref(0)
const loading = ref(false)
let requestNo = 0

const formatTime = value => formatBeijingTime(value) || '—'
const parseIds = value => String(value || '').split(',').map(Number).filter(Boolean)
const scopeText = computed(() => {
  const systemCount = parseIds(props.scope.system_ids).length
  const versionCount = parseIds(props.scope.version_ids).length
  return `${systemCount ? `已选 ${systemCount} 个系统` : '全部系统'}，${versionCount ? `已选 ${versionCount} 个版本` : '全部版本'}`
})
const isSelected = item => props.selectedSources.some(source => source.id === item.id && source.source_type === props.sourceType)
const pageSelectedCount = computed(() => items.value.filter(item => isSelected(item)).length)
const isPageAllSelected = computed(() => items.value.length > 0 && pageSelectedCount.value === items.value.length)
const isPagePartiallySelected = computed(() => pageSelectedCount.value > 0 && !isPageAllSelected.value)
const load = async () => {
  const currentRequestNo = ++requestNo
  loading.value = true
  emit('error', '')
  try {
    const result = await getWorkbenchTestCaseSources(props.projectId, {
      source_type: props.sourceType,
      system_ids: parseIds(props.scope.system_ids),
      version_ids: parseIds(props.scope.version_ids),
      ...filters,
    })
    if (currentRequestNo !== requestNo) return
    items.value = result?.items || []
    total.value = result?.total || 0
    return result
  } catch (error) {
    if (currentRequestNo === requestNo) emit('error', error?.response?.data?.message || error?.data?.message || error?.message || '来源需求查询失败')
    return null
  } finally {
    if (currentRequestNo === requestNo) loading.value = false
  }
}
const query = () => { filters.page = 1; load() }
const changeSourceType = async value => {
  emit('update:sourceType', value)
  emit('update:selectedSources', [])
  await nextTick()
  query()
}
const toggle = (item, checked) => {
  const selected = props.selectedSources.filter(source => source.id !== item.id || source.source_type !== props.sourceType)
  if (checked) selected.push({ ...item, source_type: props.sourceType })
  emit('update:selectedSources', selected)
}
const togglePageSelection = checked => {
  const pageKeys = new Set(items.value.map(item => `${props.sourceType}:${item.id}`))
  const selected = props.selectedSources.filter(source => !pageKeys.has(`${source.source_type}:${source.id}`))
  if (checked) selected.push(...items.value.map(item => ({ ...item, source_type: props.sourceType })))
  emit('update:selectedSources', selected)
}
const clear = () => emit('update:selectedSources', [])
const reset = () => {
  Object.assign(filters, { keyword: '', page: 1, page_size: 10 })
  items.value = []
  total.value = 0
}
watch(() => props.scope, () => {
  reset()
  emit('update:selectedSources', [])
}, { deep: true })
defineExpose({ load, reset })
</script>

<style scoped>
.source-selector { width: 100%; }
.source-selector__header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.source-selector__header { margin-bottom: 14px; }
.source-selector__header h4 { margin: 0 0 5px; font-size: 15px; }
.source-selector__header p { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
.source-selector__scope { color: var(--el-text-color-secondary); font-size: 13px; white-space: nowrap; }
.source-selector__type-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.source-selector__selection-summary { display: inline-flex; align-items: center; gap: 10px; color: var(--el-text-color-secondary); font-size: 13px; white-space: nowrap; }
.source-selector__query { display: flex; gap: 8px; margin: 14px 0; }
.source-table :deep(.el-table__header .cell), .source-table :deep(.el-table__body .cell) { white-space: nowrap; }
.source-table :deep(.el-table__body .cell) { overflow: hidden; text-overflow: ellipsis; }
.source-selector :deep(.el-pagination) { justify-content: flex-end; padding-top: 14px; }
@media (max-width: 720px) {
  .source-selector__header, .source-selector__type-row { flex-direction: column; align-items: flex-start; }
  .source-selector__scope, .source-selector__selection-summary { white-space: normal; }
}
</style>
