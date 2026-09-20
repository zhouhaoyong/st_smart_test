<template>
  <section class="dashboard-page">
    <WorkbenchPageHeader title="数据看板">
      <template v-if="isSuperAdmin" #actions>
        <el-button type="danger" plain :loading="clearing" @click="handleClearBusinessData">清空项目数据</el-button>
      </template>
    </WorkbenchPageHeader>

    <div class="stat-grid">
      <WorkbenchStatCard v-for="item in stats" :key="item.assetType" v-bind="item" @click="handleCardClick(item.assetType)" />
    </div>

    <WorkbenchAssetListDialog v-model="assetDialog.visible" :project-id="projectId" :asset-type="assetDialog.assetType" :initial-status="assetDialog.status" :initial-system-id="scope.system_id" :initial-version-id="scope.version_id" />

    <el-dialog v-model="cleanupDialog.visible" title="清空项目数据" width="860px" class="cleanup-dialog" :close-on-click-modal="false" :close-on-press-escape="!cleanupBusy" :show-close="!cleanupBusy" :before-close="beforeCloseCleanupDialog" @closed="resetCleanupDialog">
      <el-steps :active="cleanupDialog.step" simple finish-status="success" class="wizard-steps-green">
        <el-step title="选择系统" />
        <el-step title="选择数据" />
        <el-step title="确认清理" />
      </el-steps>

      <section v-if="cleanupDialog.step === 0" class="cleanup-dialog-content">
        <p class="cleanup-dialog__hint">仅超级管理员可操作。请选择需要清理数据的系统，确认后会写入审计记录。</p>
        <div class="cleanup-selection-bar">
          <el-checkbox v-model="allCleanupSystemsSelected" :disabled="!systems.length">全部系统</el-checkbox>
          <span>已选 {{ cleanupDialog.systemIds.length }}/{{ systems.length }} 个系统</span>
        </div>
        <el-table :data="systems" height="310" class="cleanup-table">
          <el-table-column width="56" align="center">
            <template #default="{ row }">
              <el-checkbox :model-value="isCleanupSystemSelected(row.id)" @change="toggleCleanupSystem(row.id, $event)" />
            </template>
          </el-table-column>
          <el-table-column prop="name" label="系统名称" min-width="320" show-overflow-tooltip />
          <el-table-column prop="type" label="系统类型" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">{{ row.type || '-' }}</template>
          </el-table-column>
        </el-table>
      </section>

      <section v-else-if="cleanupDialog.step === 1" class="cleanup-dialog-content">
        <p class="cleanup-dialog__hint">清理范围：{{ cleanupSystemNames }}。系统和版本仅在其下数据全部选中时可一并清理。</p>
        <div class="cleanup-selection-bar">
          <el-checkbox v-model="allCleanupTypesSelected">全部数据</el-checkbox>
          <span>已选 {{ cleanupDialog.assetTypes.length }}/{{ cleanupTypes.length }} 个数据模块</span>
        </div>
        <el-table :data="cleanupOptions" class="cleanup-table" height="310">
          <el-table-column width="56" align="center">
            <template #default="{ row }">
              <el-checkbox
                :model-value="cleanupDialog.assetTypes.includes(row.value)"
                :disabled="isCleanupOptionDisabled(row.value)"
                @change="toggleCleanupType(row.value, $event)"
              />
            </template>
          </el-table-column>
          <el-table-column prop="label" label="数据模块" min-width="220" />
          <el-table-column label="待清理数量" min-width="260">
            <template #default="{ row }">{{ row.count }} 条<span v-if="row.suffix" class="cleanup-table__suffix">（{{ row.suffix }}）</span></template>
          </el-table-column>
        </el-table>
      </section>

      <section v-else class="cleanup-dialog-content">
        <el-alert title="这是危险操作。确认后将删除以下数据，且无法在本页面恢复。" type="error" :closable="false" show-icon />
        <p class="cleanup-dialog__hint">清理系统：{{ cleanupSystemNames }}</p>
        <el-table :data="selectedCleanupOptions" class="cleanup-table" height="250">
          <el-table-column prop="label" label="数据模块" min-width="220" />
          <el-table-column label="待清理数量" min-width="260">
            <template #default="{ row }">{{ row.count }} 条<span v-if="row.suffix" class="cleanup-table__suffix">（{{ row.suffix }}）</span></template>
          </el-table-column>
        </el-table>
      </section>

      <template #footer>
        <el-button :disabled="cleanupBusy" @click="cleanupDialog.visible = false">取消</el-button>
        <el-button v-if="cleanupDialog.step > 0" :disabled="cleanupBusy" @click="cleanupDialog.step -= 1">上一步</el-button>
        <el-button v-if="cleanupDialog.step < 2" type="primary" :loading="cleanupDialog.loading" :disabled="cleanupBusy || !canContinueCleanup" @click="goToNextCleanupStep">下一步</el-button>
        <el-button v-else type="danger" :loading="clearing" :disabled="cleanupBusy" @click="confirmClearBusinessData">确认清空</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, inject, reactive, ref } from 'vue'
import { CollectionTag, Connection, Document, FolderOpened, Monitor, Tickets, Warning } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'
import { clearWorkbenchProjectBusinessData, getWorkbenchProjectBusinessCleanupSummary } from '@/api/testWorkbench'
import { useUserStore } from '@/stores/user'
import WorkbenchAssetListDialog from '@/views/test-workbench/components/WorkbenchAssetListDialog.vue'
import WorkbenchPageHeader from '@/views/test-workbench/components/WorkbenchPageHeader.vue'
import WorkbenchStatCard from '@/views/test-workbench/components/WorkbenchStatCard.vue'

const { dashboardStats, refreshDashboardStats, refreshScopeOptions, scope, systems } = inject('workbenchContext')
const route = useRoute()
const userStore = useUserStore()
const projectId = computed(() => Number(route.params.id))
const assetDialog = reactive({ visible: false, assetType: 'system', status: '' })
const clearing = ref(false)
const isSuperAdmin = computed(() => Boolean(userStore.userInfo?.is_superuser))
const cleanupTypes = ['system', 'version', 'requirement', 'test_case', 'bug', 'legacy_item']
const cleanupChildTypes = ['requirement', 'test_case', 'bug', 'legacy_item']
const cleanupDialog = reactive({ visible: false, step: 0, loading: false, systemIds: [], assetTypes: [], summary: {} })
const cleanupBusy = computed(() => cleanupDialog.loading || clearing.value)
let cleanupRequestNo = 0

const stats = computed(() => [
  { label: '系统数量', value: dashboardStats.system_count, icon: Monitor, tone: 'blue', assetType: 'system' },
  { label: '版本数量', value: dashboardStats.version_count, icon: CollectionTag, tone: 'green', assetType: 'version' },
  { label: '需求数量', value: dashboardStats.requirement_count, icon: Document, tone: 'orange', assetType: 'requirement' },
  { label: '合并需求数量', value: dashboardStats.merged_requirement_count, icon: Connection, tone: 'purple', assetType: 'merged_requirement' },
  { label: '测试用例数量', value: dashboardStats.test_case_count, icon: Tickets, tone: 'purple', assetType: 'test_case' },
  { label: 'Bug 数量', value: dashboardStats.bug_count, icon: Warning, tone: 'red', assetType: 'bug' },
  { label: '未关闭 Bug 数', value: dashboardStats.open_bug_count, icon: Warning, tone: 'red', assetType: 'open_bug' },
  { label: '遗留项数量', value: dashboardStats.legacy_item_count, icon: FolderOpened, tone: 'cyan', assetType: 'legacy_item' },
  { label: '待处理遗留项数', value: dashboardStats.pending_legacy_count, icon: FolderOpened, tone: 'cyan', assetType: 'pending_legacy' },
])

const handleCardClick = (assetType) => {
  if (assetType === 'open_bug') {
    assetDialog.assetType = 'bug'
    assetDialog.status = 'unclosed'
  } else if (assetType === 'pending_legacy') {
    assetDialog.assetType = 'legacy_item'
    assetDialog.status = 'pending'
  } else {
    assetDialog.assetType = assetType
    assetDialog.status = ''
  }
  assetDialog.visible = true
}

const cleanupOptions = computed(() => [
  { value: 'system', label: '系统管理', count: cleanupDialog.summary.system_count || 0 },
  { value: 'version', label: '版本管理', count: cleanupDialog.summary.version_count || 0 },
  { value: 'requirement', label: '需求管理', count: cleanupDialog.summary.requirement_count || 0 },
  { value: 'test_case', label: '用例管理', count: cleanupDialog.summary.test_case_count || 0, suffix: `含 ${cleanupDialog.summary.test_execution_count || 0} 条执行记录` },
  { value: 'bug', label: 'Bug 管理', count: cleanupDialog.summary.bug_count || 0, suffix: `含 ${cleanupDialog.summary.bug_transition_count || 0} 条流转记录` },
  { value: 'legacy_item', label: '遗留项管理', count: cleanupDialog.summary.legacy_item_count || 0 },
])
const allCleanupSystemsSelected = computed({
  get: () => systems.value.length > 0 && cleanupDialog.systemIds.length === systems.value.length,
  set: value => { cleanupDialog.systemIds = value ? systems.value.map(item => item.id) : [] },
})
const allCleanupTypesSelected = computed({
  get: () => cleanupDialog.assetTypes.length === cleanupTypes.length,
  set: value => { cleanupDialog.assetTypes = value ? [...cleanupTypes] : [] },
})
const cleanupSystemNames = computed(() => systems.value.filter(item => cleanupDialog.systemIds.includes(item.id)).map(item => item.name).join('、'))
const selectedCleanupOptions = computed(() => cleanupOptions.value.filter(item => cleanupDialog.assetTypes.includes(item.value)))
const canSelectCleanupVersion = computed(() => cleanupChildTypes.every(item => cleanupDialog.assetTypes.includes(item)))
const canSelectCleanupSystem = computed(() => canSelectCleanupVersion.value && cleanupDialog.assetTypes.includes('version'))
const canContinueCleanup = computed(() => cleanupDialog.step === 0 ? cleanupDialog.systemIds.length > 0 : cleanupDialog.assetTypes.length > 0)

const formatCleanupResult = summary => {
  const items = [
    ['系统', summary?.system_count],
    ['版本', summary?.version_count],
    ['需求', summary?.requirement_count],
    ['用例', summary?.test_case_count],
    ['执行记录', summary?.test_execution_count],
    ['Bug', summary?.bug_count],
    ['流转记录', summary?.bug_transition_count],
    ['遗留项', summary?.legacy_item_count],
  ].filter(([, count]) => Number(count) > 0).map(([label, count]) => `${label} ${count} 条`)
  return items.length ? `项目数据已清理：${items.join('、')}` : '项目数据已清理，没有可清理数据'
}

const isCleanupOptionDisabled = (value) => (
  (value === 'version' && !canSelectCleanupVersion.value)
  || (value === 'system' && !canSelectCleanupSystem.value)
)

const normalizeCleanupTypes = () => {
  const selected = new Set(cleanupDialog.assetTypes)
  if (!canSelectCleanupVersion.value) selected.delete('version')
  if (!canSelectCleanupSystem.value) selected.delete('system')
  cleanupDialog.assetTypes = cleanupTypes.filter(item => selected.has(item))
}

const handleCleanupTypesChange = (types) => {
  cleanupDialog.assetTypes = types
  normalizeCleanupTypes()
}

const isCleanupSystemSelected = systemId => cleanupDialog.systemIds.includes(systemId)
const toggleCleanupSystem = (systemId, checked) => {
  const selected = new Set(cleanupDialog.systemIds)
  if (checked) selected.add(systemId)
  else selected.delete(systemId)
  cleanupDialog.systemIds = [...selected]
}
const toggleCleanupType = (assetType, checked) => {
  const selected = new Set(cleanupDialog.assetTypes)
  if (checked) selected.add(assetType)
  else selected.delete(assetType)
  handleCleanupTypesChange(cleanupTypes.filter(item => selected.has(item)))
}

const resetCleanupDialog = () => {
  cleanupRequestNo += 1
  cleanupDialog.step = 0
  cleanupDialog.loading = false
  cleanupDialog.systemIds = []
  cleanupDialog.assetTypes = []
  cleanupDialog.summary = {}
}

const handleClearBusinessData = () => {
  cleanupRequestNo += 1
  cleanupDialog.systemIds = systems.value.map(item => item.id)
  cleanupDialog.assetTypes = [...cleanupTypes]
  cleanupDialog.summary = {}
  cleanupDialog.step = 0
  cleanupDialog.visible = true
}

const beforeCloseCleanupDialog = done => {
  if (!cleanupBusy.value) done()
}

const goToNextCleanupStep = async () => {
  if (cleanupDialog.step === 0) {
    const requestNo = ++cleanupRequestNo
    cleanupDialog.loading = true
    try {
      const summary = await getWorkbenchProjectBusinessCleanupSummary(projectId.value, { system_ids: cleanupDialog.systemIds.join(',') })
      if (requestNo !== cleanupRequestNo || !cleanupDialog.visible) return
      cleanupDialog.summary = summary || {}
      cleanupDialog.step = 1
    } finally {
      if (requestNo === cleanupRequestNo) cleanupDialog.loading = false
    }
    return
  }
  cleanupDialog.step = 2
}

const confirmClearBusinessData = async () => {
  clearing.value = true
  try {
    const result = await clearWorkbenchProjectBusinessData(projectId.value, {
      system_ids: cleanupDialog.systemIds,
      asset_types: cleanupDialog.assetTypes,
    })
    cleanupDialog.visible = false
    ElMessage.success(formatCleanupResult(result))
    try {
      await refreshScopeOptions()
      await refreshDashboardStats()
    } catch (error) {
      console.warn('项目数据已清理，但刷新页面数据失败', error)
      ElMessage.info('数据已清理，但页面刷新失败，请手动刷新页面')
    }
  } finally {
    clearing.value = false
  }
}
</script>

<style scoped>
.dashboard-page { height: 100%; min-height: 0; display: flex; flex-direction: column; gap: 16px; overflow: hidden; }
.stat-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.cleanup-dialog-content { display: flex; flex-direction: column; gap: 14px; padding-top: 20px; }
.cleanup-dialog__hint { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; line-height: 20px; }
.cleanup-selection-bar { display: flex; align-items: center; justify-content: space-between; min-height: 34px; color: var(--el-text-color-regular); font-size: 13px; }
.cleanup-table :deep(.el-table__cell) { padding: 9px 0; }
.cleanup-table :deep(.el-table__header .cell), .cleanup-table :deep(.el-table__body .cell) { white-space: nowrap; }
.cleanup-table :deep(.el-table__body .cell) { overflow: hidden; text-overflow: ellipsis; }
.cleanup-table__suffix { color: var(--el-text-color-secondary); }
@media (max-width: 900px) { .stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
