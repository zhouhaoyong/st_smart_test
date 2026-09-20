<template>
  <el-dialog v-model="visible" title="选择工作范围" width="860px" destroy-on-close @open="open">
    <p class="scope-dialog__hint">选择后将用于数据看板、需求、用例、Bug 和遗留项；保存后统一生效。</p>

    <el-form inline class="scope-filters" @submit.prevent="queryScope">
      <el-form-item label="系统">
        <el-input v-model="filters.name" clearable placeholder="搜索系统名称" @keyup.enter="queryScope" />
      </el-form-item>
      <el-form-item label="版本">
        <el-input v-model="filters.version_no" clearable placeholder="搜索版本号" @keyup.enter="queryScope" />
      </el-form-item>
      <el-form-item label="版本状态">
        <el-select v-model="filters.current_stage" clearable filterable allow-create default-first-option placeholder="全部状态">
          <el-option v-for="item in stageOptions" :key="item" :label="item" :value="item" />
        </el-select>
      </el-form-item>
      <el-form-item class="scope-filters__actions">
        <el-button @click="resetFilters">重置</el-button>
        <el-button type="primary" @click="queryScope">查询</el-button>
      </el-form-item>
    </el-form>

    <div class="scope-selection-bar">
      <el-checkbox :model-value="draft.allSystems" :disabled="!projectSystemTotal" @change="toggleAllSystems">
        全部系统
      </el-checkbox>
      <el-checkbox
        :model-value="draft.allVersions"
        :disabled="!availableVersionTotal || (!draft.allSystems && !draft.systemIds.length)"
        @change="toggleAllVersions"
      >
        全部版本
      </el-checkbox>
      <span>系统 {{ selectedSystemCount }}/{{ projectSystemTotal }}，版本 {{ selectedVersionCount }}/{{ availableVersionTotal }}</span>
    </div>

    <el-table
      v-loading="loading"
      :data="scopeItems"
      row-key="rowKey"
      height="350"
      class="scope-table"
    >
      <el-table-column width="56" align="center">
        <template #default="{ row }">
          <div :class="{ 'scope-table__version-check': row.rowType === 'version' }">
            <el-checkbox
              v-if="row.rowType === 'system'"
              :model-value="isSystemChecked(row)"
              :indeterminate="isSystemIndeterminate(row)"
              :disabled="!row.version_count"
              @click.stop
              @change="toggleSystem(row, $event)"
            />
            <el-checkbox v-else :model-value="isVersionSelected(row)" @click.stop @change="toggleVersion(row, $event)" />
          </div>
        </template>
      </el-table-column>
      <el-table-column label="系统 / 版本" min-width="300" show-overflow-tooltip>
        <template #default="{ row }">
          <button v-if="row.rowType === 'system'" class="scope-table__system-toggle" type="button" @click="toggleRow(row)">
            <el-icon :class="{ 'is-expanded': isSystemExpanded(row.id) }"><ArrowRight /></el-icon>
            <span :title="row.name">{{ row.name }}</span>
          </button>
          <span v-else class="scope-table__version-name" :title="row.version_no">{{ row.version_no }}</span>
        </template>
      </el-table-column>
      <el-table-column label="系统类型" min-width="170" show-overflow-tooltip>
        <template #default="{ row }">{{ row.rowType === 'system' ? (row.type || '-') : '-' }}</template>
      </el-table-column>
      <el-table-column label="版本状态" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag v-if="row.rowType === 'version' && row.current_stage" size="small" effect="plain">{{ row.current_stage }}</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
    </el-table>

    <div class="scope-pagination">
      <span>筛选和翻页不会清空已选范围</span>
      <el-pagination
        v-model:current-page="filters.page"
        v-model:page-size="filters.page_size"
        :total="total"
        :page-sizes="[10, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="loadScope"
        @size-change="queryScope"
      />
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :disabled="!draft.allVersions && !draft.versions.length" @click="save">应用范围</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'
import { getWorkbenchProjectDashboardAssets } from '@/api/testWorkbench'

const props = defineProps({
  modelValue: Boolean,
  projectId: { type: Number, required: true },
  value: { type: Object, required: true },
})
const emit = defineEmits(['update:modelValue', 'save'])
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const loading = ref(false)
const items = ref([])
const total = ref(0)
const projectSystemTotal = ref(0)
const projectVersionTotal = ref(0)
const draft = reactive({ systemIds: [], versions: [], allSystems: false, allVersions: false })
const filters = reactive({ name: '', version_no: '', current_stage: '', page: 1, page_size: 10 })
const stageOptions = ['规划中', '测试中', '已发布']
const expandedSystemIds = ref([])
let requestNo = 0
let selectionTask = Promise.resolve()

const selectedSystemIds = computed(() => new Set(draft.systemIds))
const selectedVersionIds = computed(() => new Set(draft.versions.map(item => item.id)))
const selectedSystemCount = computed(() => {
  if (draft.allSystems) return projectSystemTotal.value
  return selectedSystemIds.value.size
})
const availableVersionTotal = computed(() => projectVersionTotal.value)
const selectedVersionCount = computed(() => draft.allVersions ? availableVersionTotal.value : draft.versions.length)
const scopeItems = computed(() => items.value.flatMap(system => {
  const systemRow = { ...system, rowKey: `system-${system.id}`, rowType: 'system' }
  if (!expandedSystemIds.value.includes(system.id)) return [systemRow]
  return [
    systemRow,
    ...(system.versions || []).map(version => ({ ...version, rowKey: `version-${version.id}`, rowType: 'version' })),
  ]
}))

const loadScope = async () => {
  const currentRequestNo = ++requestNo
  loading.value = true
  try {
    const result = await getWorkbenchProjectDashboardAssets(props.projectId, { asset_type: 'scope', ...filters })
    if (currentRequestNo !== requestNo) return
    items.value = result?.items || []
    total.value = result?.total || 0
    projectSystemTotal.value = result?.project_system_total || 0
    projectVersionTotal.value = result?.project_version_total || 0
  } finally {
    if (currentRequestNo === requestNo) loading.value = false
  }
}
const queryScope = () => {
  filters.page = 1
  loadScope()
}
const resetFilters = () => {
  Object.assign(filters, { name: '', version_no: '', current_stage: '', page: 1 })
  loadScope()
}
const mergeVersions = versions => {
  const versionMap = new Map(draft.versions.map(item => [item.id, item]))
  versions.forEach(item => versionMap.set(item.id, item))
  draft.versions = [...versionMap.values()]
}
const fetchSystems = async () => {
  const systems = []
  let page = 1
  let totalCount = 0
  do {
    const result = await getWorkbenchProjectDashboardAssets(props.projectId, {
      asset_type: 'system', page, page_size: 100,
    })
    systems.push(...(result?.items || []))
    totalCount = result?.total || 0
    page += 1
  } while (systems.length < totalCount)
  return systems
}
const fetchVersions = async (systemId) => {
  const versions = []
  let page = 1
  let totalCount = 0
  do {
    const result = await getWorkbenchProjectDashboardAssets(props.projectId, {
      asset_type: 'version',
      ...(systemId ? { system_id: systemId } : {}),
      page,
      page_size: 100,
    })
    versions.push(...(result?.items || []))
    totalCount = result?.total || 0
    page += 1
  } while (versions.length < totalCount)
  return versions
}
const materializeAllVersions = async () => {
  if (!draft.allVersions) return
  const systemIds = draft.allSystems ? [] : [...draft.systemIds]
  const versions = []
  if (systemIds.length) {
    for (const systemId of systemIds) versions.push(...await fetchVersions(systemId))
  } else {
    versions.push(...await fetchVersions())
  }
  draft.versions = versions
  draft.allVersions = false
}
const materializeAllSystems = async () => {
  if (!draft.allSystems) return
  const systems = await fetchSystems()
  draft.systemIds = systems.map(item => item.id)
  draft.allSystems = false
}
const queueSelection = handler => {
  selectionTask = selectionTask.then(handler, handler)
  return selectionTask
}
const toggleAllSystems = checked => queueSelection(async () => {
  if (checked) {
    draft.allSystems = true
    draft.systemIds = []
    return
  }
  await materializeAllSystems()
  draft.systemIds = []
  draft.versions = []
  draft.allVersions = false
})
const toggleAllVersions = checked => queueSelection(async () => {
  if (!checked) {
    await materializeAllVersions()
    return
  }
  if (!draft.allSystems && !draft.systemIds.length) return
  draft.allVersions = true
  draft.versions = []
})
const isVersionSelected = row => draft.allVersions || selectedVersionIds.value.has(row.id)
const selectedVersionCountInSystem = systemId => draft.versions.filter(item => item.system_id === systemId).length
const isSystemChecked = row => draft.allSystems || (
  selectedSystemIds.value.has(row.id)
  && (draft.allVersions || selectedVersionCountInSystem(row.id) >= row.version_count)
)
const isSystemIndeterminate = row => !draft.allSystems
  && selectedSystemIds.value.has(row.id)
  && !isSystemChecked(row)
const toggleSystem = (row, checked) => queueSelection(async () => {
  if (draft.allSystems) await materializeAllSystems()
  await materializeAllVersions()
  if (checked) {
    draft.systemIds = [...new Set([...draft.systemIds, row.id])]
    if (!draft.allVersions) mergeVersions(await fetchVersions(row.id))
  } else {
    draft.systemIds = draft.systemIds.filter(id => id !== row.id)
    draft.versions = draft.versions.filter(item => item.system_id !== row.id)
  }
})
const toggleVersion = (row, checked) => queueSelection(async () => {
  await materializeAllVersions()
  if (checked) {
    if (!draft.allSystems && !draft.systemIds.includes(row.system_id)) draft.systemIds.push(row.system_id)
    mergeVersions([row])
  } else {
    draft.versions = draft.versions.filter(item => item.id !== row.id)
    if (!draft.allSystems && !draft.allVersions && !draft.versions.some(item => item.system_id === row.system_id)) {
      draft.systemIds = draft.systemIds.filter(id => id !== row.system_id)
    }
  }
})
const isSystemExpanded = systemId => expandedSystemIds.value.includes(systemId)
const toggleRow = row => {
  if (row.rowType !== 'system') return
  expandedSystemIds.value = isSystemExpanded(row.id)
    ? expandedSystemIds.value.filter(item => item !== row.id)
    : [...expandedSystemIds.value, row.id]
}
const open = async () => {
  const value = props.value || {}
  draft.systemIds = [...(value.systemIds || value.system_ids || [])]
  draft.versions = [...(value.versions || [])]
  draft.allSystems = Boolean(value.allSystems ?? value.all_systems)
  draft.allVersions = Boolean(value.allVersions ?? value.all_versions)
  expandedSystemIds.value = []
  Object.assign(filters, { name: '', version_no: '', current_stage: '', page: 1, page_size: 10 })
  await loadScope()
}
const save = () => {
  emit('save', {
    systemIds: draft.allSystems ? [] : [...draft.systemIds],
    versions: draft.allVersions ? [] : [...draft.versions],
    allSystems: draft.allSystems,
    allVersions: draft.allVersions,
  })
  visible.value = false
}
</script>

<style scoped>
.scope-dialog__hint { margin: 0 0 16px; color: var(--el-text-color-secondary); font-size: 13px; line-height: 20px; }
.scope-filters { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.2fr) auto; align-items: center; column-gap: 12px; margin-bottom: 12px; padding: 12px; background: var(--el-fill-color-lighter); }
.scope-filters :deep(.el-form-item) { display: flex; min-width: 0; margin-right: 0; margin-bottom: 0; }
.scope-filters :deep(.el-form-item__content) { min-width: 0; flex: 1; }
.scope-filters :deep(.el-input), .scope-filters :deep(.el-select) { width: 100%; }
.scope-filters__actions { margin-left: 0; flex-shrink: 0; white-space: nowrap; }
.scope-filters__actions :deep(.el-form-item__content) { flex: none; white-space: nowrap; }
.scope-filters__actions :deep(.el-button + .el-button) { margin-left: 8px; }
.scope-selection-bar { display: flex; align-items: center; justify-content: space-between; min-height: 36px; color: var(--el-text-color-regular); font-size: 13px; }
.scope-table :deep(.el-table__cell) { padding: 8px 0; }
.scope-table :deep(.el-table__header .cell), .scope-table :deep(.el-table__body .cell) { white-space: nowrap; }
.scope-table :deep(.el-table__body .cell) { overflow: hidden; text-overflow: ellipsis; }
.scope-table__system-toggle { display: inline-flex; width: 100%; min-width: 0; align-items: center; gap: 6px; overflow: hidden; padding: 0; border: 0; background: transparent; color: var(--el-text-color-primary); cursor: pointer; font: inherit; font-weight: 600; white-space: nowrap; }
.scope-table__system-toggle :deep(.el-icon) { color: var(--el-text-color-secondary); transition: transform .2s; }
.scope-table__system-toggle :deep(.el-icon.is-expanded) { transform: rotate(90deg); }
.scope-table__system-toggle > span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.scope-table__version-check { padding-left: 28px; }
.scope-table__version-name { display: block; min-width: 0; max-width: 100%; overflow: hidden; padding-left: 28px; box-sizing: border-box; text-overflow: ellipsis; white-space: nowrap; }
.scope-pagination { display: flex; align-items: center; justify-content: space-between; min-height: 48px; color: var(--el-text-color-secondary); font-size: 12px; }
.scope-pagination :deep(.el-pagination) { padding: 0; }
@media (max-width: 760px) {
  .scope-filters { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  .scope-filters__actions { grid-column: 1 / -1; justify-self: end; }
  .scope-pagination { align-items: flex-end; flex-direction: column; gap: 8px; }
}
</style>
