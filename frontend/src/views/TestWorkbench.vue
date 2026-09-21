<template>
  <div class="workbench-page">
    <WorkbenchScopeSidebar
      :active-section="activeSection"
      :nav-items="navItems"
      :system-label="systemScopeLabel"
      :version-label="versionScopeLabel"
      :has-systems="systems.length > 0"
      @select-section="selectSection"
      @edit-scope="openScopeEditor"
      @open-scope-tab="openScopeEditor"
    />

    <main class="wb-main">
      <router-view />
    </main>

    <WorkbenchScopeCreateDialog
      :dialog="createDialog"
      :form="createForm"
      :saving="createSaving"
      @submit="submitCreate"
    />

    <WorkbenchScopeSelectorDialog
      v-model="scopeDialog.visible"
      :project-id="projectId"
      :value="scopeEditorValue"
      @save="saveScope"
    />

    <WorkbenchExecutionDialog
      :dialog="executionDialog"
      :form="executionForm"
      :test-case="selectedCase"
      :history="executionHistory"
      :correcting-id="correctingExecutionId"
      @load-history="loadExecutionHistory(selectedCase?.id)"
      @correct="startCorrectExecution"
      @cancel-correct="cancelCorrectExecution"
      @submit="submitExecution"
    />

    <WorkbenchBugDialog :dialog="bugDialog" :form="bugForm" :test-case="selectedCase" @submit="submitBug" />

    <WorkbenchLegacyDialog :dialog="legacyDialog" :form="legacyForm" :versions="versions" @submit="submitLegacy" />
  </div>
</template>

<script setup>
import { computed, inject, onMounted, provide, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import WorkbenchScopeSidebar from '@/views/test-workbench/components/WorkbenchScopeSidebar.vue'
import WorkbenchScopeSelectorDialog from '@/views/test-workbench/components/WorkbenchScopeSelectorDialog.vue'
import WorkbenchScopeCreateDialog from '@/views/test-workbench/components/WorkbenchScopeCreateDialog.vue'
import WorkbenchExecutionDialog from '@/views/test-workbench/components/WorkbenchExecutionDialog.vue'
import WorkbenchBugDialog from '@/views/test-workbench/components/WorkbenchBugDialog.vue'
import WorkbenchLegacyDialog from '@/views/test-workbench/components/WorkbenchLegacyDialog.vue'
import {
  createWorkbenchBug,
  createWorkbenchExecution,
  correctWorkbenchExecution,
  getWorkbenchTestCaseExecutions,
  createWorkbenchLegacyItem,
  getWorkbenchProjectDashboard,
  getWorkbenchProjectDashboardAssets,
  getWorkbenchProject,
  createWorkbenchSystem,
  createWorkbenchVersion,
  getWorkbenchSystems,
  getWorkbenchVersions,
} from '@/api/testWorkbench'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const detailBreadcrumb = inject('detailBreadcrumb', ref(''))

const projectId = computed(() => Number(route.params.id))
const queryId = value => {
  const id = Number(value)
  return Number.isInteger(id) && id > 0 ? id : undefined
}
const systems = ref([])
const versions = ref([])
const dashboardStats = reactive({
  system_count: 0,
  version_count: 0,
  requirement_count: 0,
  merged_requirement_count: 0,
  test_case_count: 0,
  bug_count: 0,
  legacy_item_count: 0,
  open_bug_count: 0,
  my_open_bug_count: 0,
  my_pending_bug_count: 0,
  my_verification_bug_count: 0,
  pending_legacy_count: 0,
})

const selectedProject = ref(null)
const selectedSystem = ref(null)
const selectedVersion = ref(null)
const selectedSystems = ref([])
const selectedVersions = ref([])
const scopeAllSystems = ref(false)
const scopeAllVersions = ref(false)
const selectedCase = ref(null)
const selectedExecution = ref(null)
const assetListRefreshKey = ref(0)
const scopeRefreshKey = ref(0)
let scopeRequestNo = 0
let dashboardRequestNo = 0
let systemRequestNo = 0
let versionRequestNo = 0

const scope = computed(() => ({
  system_id: !scopeAllSystems.value && selectedSystems.value.length === 1 ? selectedSystems.value[0].id : undefined,
  version_id: !scopeAllVersions.value && selectedVersions.value.length === 1 ? selectedVersions.value[0].id : undefined,
  system_ids: !scopeAllSystems.value && selectedSystems.value.length
    ? selectedSystems.value.map(item => item.id).join(',')
    : undefined,
  version_ids: !scopeAllVersions.value && selectedVersions.value.length
    ? selectedVersions.value.map(item => item.id).join(',')
    : undefined,
}))
const scopeEditorValue = computed(() => ({
  systemIds: selectedSystems.value.map(item => item.id),
  versions: selectedVersions.value,
  allSystems: scopeAllSystems.value,
  allVersions: scopeAllVersions.value,
}))
const scopeStorageKey = computed(() => `tw_scope_${userStore.userInfo?.id || 'anonymous'}_${projectId.value}`)
const readScope = () => {
  try { return JSON.parse(localStorage.getItem(scopeStorageKey.value)) || {} } catch { return {} }
}
const persistScope = () => {
  try {
    localStorage.setItem(scopeStorageKey.value, JSON.stringify({
      system_ids: selectedSystems.value.map(item => item.id),
      version_ids: selectedVersions.value.map(item => item.id),
      all_systems: scopeAllSystems.value,
      all_versions: scopeAllVersions.value,
    }))
  } catch { /* 忽略本地存储异常 */ }
}

const sectionByRouteName = {
  TestWorkbenchDashboard: 'dashboard',
  TestWorkbenchPending: 'pending',
  TestWorkbenchSystems: 'systems',
  TestWorkbenchVersions: 'versions',
  TestWorkbenchRequirements: 'requirements',
  TestWorkbenchMergedRequirements: 'requirements',
  TestWorkbenchCases: 'cases',
  TestWorkbenchBugs: 'bugs',
  TestWorkbenchLegacy: 'legacy',
}
const activeSection = computed(() => sectionByRouteName[route.name] || 'dashboard')

const createDialog = reactive({ visible: false, kind: 'system' })
const createForm = reactive({ name: '', type: '', description: '' })
const createSaving = ref(false)

const executionDialog = reactive({ visible: false })
const executionForm = reactive({ result: 'passed', actual_result: '', remark: '', submit_bug: false })
const executionHistory = ref([])
const correctingExecutionId = ref(null)
const bugDialog = reactive({ visible: false })
const bugForm = reactive({ title: '', steps: '', actual_result: '', expected_result: '', severity: 'minor', priority: 'P2', assignee_id: null, verifier_id: null })
const legacyDialog = reactive({ visible: false })
const legacyForm = reactive({ title: '', type: 'bug', description: '', planned_version_id: null })
const scopeDialog = reactive({ visible: false, activeTab: 'system' })
const selectedScopeVersionTotal = ref(0)
const selectedScopeVersionName = ref('')

// 待办红点 = 待我处理 + 待我验证（项目级，不叠加系统/版本作用域）。
const pendingBadge = computed(() => dashboardStats.my_open_bug_count || 0)
const systemScopeLabel = computed(() => {
  if (!systems.value.length) return '暂无系统'
  const count = scopeAllSystems.value ? systems.value.length : selectedSystems.value.length
  if (count === 1) return selectedSystems.value[0]?.name || systems.value[0]?.name || '暂无系统'
  return `已选择 ${count} 个系统`
})
const versionScopeLabel = computed(() => {
  if (!systems.value.length || !selectedScopeVersionTotal.value) return '暂无版本'
  const count = scopeAllVersions.value ? selectedScopeVersionTotal.value : selectedVersions.value.length
  if (count === 1) return selectedVersions.value[0]?.version_no || versions.value[0]?.version_no || selectedScopeVersionName.value || '暂无版本'
  return `已选择 ${count} 个版本`
})
const navItems = computed(() => [
  { key: 'dashboard', label: '数据看板' },
  { key: 'systems', label: '系统管理' },
  { key: 'versions', label: '版本管理' },
  { key: 'requirements', label: '需求管理' },
  { key: 'cases', label: '用例管理' },
  { key: 'bugs', label: 'Bug 管理' },
  { key: 'legacy', label: '遗留项管理' },
  { key: 'pending', label: '待办事项', badge: pendingBadge.value },
])

const loadProject = async () => {
  if (!projectId.value) return
  const res = await getWorkbenchProject(projectId.value)
  selectedProject.value = res || null
  detailBreadcrumb.value = selectedProject.value?.name || ''
}

const loadDashboardStats = async () => {
  if (!projectId.value) return
  const currentRequestNo = ++dashboardRequestNo
  const requestedScope = { ...scope.value }
  const stats = await getWorkbenchProjectDashboard(projectId.value, requestedScope)
  if (currentRequestNo !== dashboardRequestNo) return
  Object.assign(dashboardStats, stats || {})
}

const loadProjectVersions = async () => {
  const rows = []
  let page = 1
  let total = 0
  do {
    const result = await getWorkbenchProjectDashboardAssets(projectId.value, { asset_type: 'version', page, page_size: 100 })
    rows.push(...(result?.items || []))
    total = result?.total || 0
    page += 1
  } while (rows.length < total)
  return rows
}

const loadSystems = async () => {
  if (!projectId.value) return
  systems.value = await getWorkbenchSystems(projectId.value)
  const savedScope = readScope()
  const savedSystemIds = Array.isArray(savedScope.system_ids) ? savedScope.system_ids.map(Number).filter(Boolean) : []
  const savedVersionIds = Array.isArray(savedScope.version_ids) ? savedScope.version_ids.map(Number).filter(Boolean) : []
  if (savedScope.all_systems || savedScope.all || (savedScope.all_versions && !savedSystemIds.length)) {
    await selectAllScope()
  } else if (savedScope.all_versions && savedSystemIds.length) {
    selectedSystems.value = systems.value.filter(item => savedSystemIds.includes(item.id))
    selectedVersions.value = []
    scopeAllSystems.value = false
    scopeAllVersions.value = true
    if (selectedSystems.value.length) await refreshSelectedScope()
    else if (systems.value.length) await selectSystem(systems.value[0])
  } else if (savedVersionIds.length) {
    const versionIds = new Set(savedVersionIds)
    selectedVersions.value = (await loadProjectVersions()).filter(item => versionIds.has(item.id))
    selectedSystems.value = systems.value.filter(item => selectedVersions.value.some(version => version.system_id === item.id))
    scopeAllSystems.value = false
    scopeAllVersions.value = false
    if (selectedVersions.value.length) await refreshSelectedScope()
    else if (systems.value.length) await selectSystem(systems.value[0])
  } else if (savedSystemIds.length) {
    selectedSystems.value = systems.value.filter(item => savedSystemIds.includes(item.id))
    selectedVersions.value = []
    scopeAllSystems.value = false
    scopeAllVersions.value = true
    if (selectedSystems.value.length) await refreshSelectedScope()
    else if (systems.value.length) await selectSystem(systems.value[0])
  } else if (systems.value.length) {
    const preferredSystem = systems.value.find(item => item.id === savedScope.system_id) || systems.value[0]
    await selectSystem(preferredSystem, savedScope.version_id, savedScope.all_versions)
  }
  else {
    selectedSystem.value = null
    selectedVersion.value = null
    selectedSystems.value = []
    selectedVersions.value = []
    scopeAllSystems.value = false
    scopeAllVersions.value = false
    versions.value = []
    await refreshSelectedScope()
  }
}

const refreshSelectedScope = async () => {
  const currentScopeRequestNo = ++scopeRequestNo
  dashboardRequestNo += 1
  if (scopeAllSystems.value) {
    selectedSystems.value = [...systems.value]
  } else if (scopeAllVersions.value) {
    selectedSystems.value = selectedSystems.value.filter(item => systems.value.some(system => system.id === item.id))
  } else {
    selectedSystems.value = systems.value.filter(item => selectedVersions.value.some(version => version.system_id === item.id))
  }
  selectedVersion.value = !scopeAllVersions.value && selectedVersions.value.length === 1 ? selectedVersions.value[0] : null
  selectedSystem.value = !scopeAllSystems.value && selectedSystems.value.length === 1 ? selectedSystems.value[0] : null
  const nextVersions = selectedSystem.value ? await getWorkbenchVersions(selectedSystem.value.id) : []
  if (currentScopeRequestNo !== scopeRequestNo) return
  versions.value = nextVersions
  persistScope()
  scopeRefreshKey.value += 1
  const versionScopeParams = !scopeAllSystems.value && selectedSystems.value.length
    ? { system_ids: selectedSystems.value.map(item => item.id).join(',') }
    : {}
  const versionResult = await getWorkbenchProjectDashboardAssets(projectId.value, {
    asset_type: 'version',
    ...versionScopeParams,
    page: 1,
    page_size: 10,
  })
  if (currentScopeRequestNo !== scopeRequestNo) return
  selectedScopeVersionTotal.value = versionResult?.total || 0
  selectedScopeVersionName.value = selectedScopeVersionTotal.value === 1 ? versionResult?.items?.[0]?.version_no || '' : ''
  await loadDashboardStats()
}

const selectSystem = async (item, preferredVersionId = null, useAllVersions = false) => {
  if (!item) return selectAllScope()
  const requestNo = ++systemRequestNo
  selectedSystem.value = item
  selectedVersion.value = null
  selectedSystems.value = [item]
  selectedVersions.value = []
  scopeAllSystems.value = false
  scopeAllVersions.value = useAllVersions
  versionRequestNo += 1
  const rows = await getWorkbenchVersions(item.id)
  if (requestNo !== systemRequestNo) return
  versions.value = rows
  const preferredVersion = useAllVersions ? null : (rows.find(row => row.id === preferredVersionId) || rows[0])
  if (preferredVersion) await selectVersion(preferredVersion)
  else {
    await refreshSelectedScope()
  }
}

const selectVersion = async (item) => {
  ++versionRequestNo
  selectedVersion.value = item
  selectedVersions.value = item ? [item] : []
  scopeAllVersions.value = false
  await refreshSelectedScope()
}

const selectAllScope = async () => {
  systemRequestNo += 1
  versionRequestNo += 1
  selectedSystem.value = null
  selectedVersion.value = null
  selectedSystems.value = []
  selectedVersions.value = []
  scopeAllSystems.value = true
  scopeAllVersions.value = true
  versions.value = []
  await refreshSelectedScope()
}

const openScopeEditor = () => { scopeDialog.visible = true }

const saveScope = async (nextScope) => {
  scopeAllSystems.value = Boolean(nextScope.allSystems)
  scopeAllVersions.value = nextScope.allVersions
  selectedSystems.value = scopeAllSystems.value
    ? [...systems.value]
    : systems.value.filter(item => (nextScope.systemIds || []).includes(item.id))
  selectedVersions.value = nextScope.allVersions ? [] : [...nextScope.versions]
  await refreshSelectedScope()
}

let applyingRouteScope = false
const applyRouteScope = async () => {
  if (applyingRouteScope || !projectId.value) return
  const requestedSystemId = queryId(route.query.system_id)
  const requestedVersionId = queryId(route.query.version_id)
  if (!requestedSystemId && !requestedVersionId) return

  const versionResult = requestedVersionId
    ? await getWorkbenchProjectDashboardAssets(projectId.value, { asset_type: 'version', version_ids: String(requestedVersionId), page: 1, page_size: 10 })
    : null
  const requestedVersion = versionResult?.items?.find(item => item.id === requestedVersionId)
  const systemId = requestedSystemId || requestedVersion?.system_id
  const requestedSystem = systems.value.find(item => item.id === systemId)
  if (!requestedSystem || (requestedVersion && requestedVersion.system_id !== requestedSystem.id)) return

  applyingRouteScope = true
  try {
    if (!requestedVersion) {
      await selectSystem(requestedSystem)
      return
    }
    const systemVersions = await getWorkbenchVersions(requestedSystem.id)
    const version = systemVersions.find(item => item.id === requestedVersion.id)
    if (!version) return
    selectedSystems.value = [requestedSystem]
    selectedVersions.value = [version]
    scopeAllSystems.value = false
    scopeAllVersions.value = false
    versions.value = systemVersions
    await refreshSelectedScope()
  } finally {
    applyingRouteScope = false
  }
}

const selectSection = (section) => {
  router.push(`/test-workbench/project/${projectId.value}/${section}`)
}

const openCreate = (kind) => {
  createDialog.kind = kind
  createDialog.visible = true
  Object.assign(createForm, { name: '', type: '', description: '' })
}

const submitCreate = async () => {
  createSaving.value = true
  try {
    if (createDialog.kind === 'system') {
      const system = await createWorkbenchSystem({ project_id: projectId.value, name: createForm.name, type: createForm.type, description: createForm.description })
      systems.value = await getWorkbenchSystems(projectId.value)
      if (system?.id) await selectSystem(system)
    }
    if (createDialog.kind === 'version') {
      let version = await createWorkbenchVersion({ project_id: projectId.value, system_id: selectedSystem.value.id, version_no: createForm.name, description: createForm.description })
      if (version?.requires_confirmation) {
        await ElMessageBox.confirm(version.message, '版本号提醒', {
          confirmButtonText: '继续保存', cancelButtonText: '返回修改', type: 'warning',
        })
        version = await createWorkbenchVersion({
          project_id: projectId.value, system_id: selectedSystem.value.id,
          version_no: createForm.name, description: createForm.description, confirm_lower_version: true,
        })
      }
      versions.value = await getWorkbenchVersions(selectedSystem.value.id)
      if (version?.id) await selectVersion(version)
    }
    await loadDashboardStats()
    createDialog.visible = false
  } finally {
    createSaving.value = false
  }
}

const loadExecutionHistory = async (testCaseId) => {
  executionHistory.value = await getWorkbenchTestCaseExecutions(testCaseId) || []
}

const openExecution = async (row) => {
  selectedCase.value = row
  selectedExecution.value = null
  correctingExecutionId.value = null
  Object.assign(executionForm, { result: 'passed', actual_result: '', remark: '', submit_bug: false })
  executionHistory.value = []
  executionDialog.visible = true
}

const startCorrectExecution = (item) => {
  correctingExecutionId.value = item.id
  Object.assign(executionForm, {
    result: ['passed', 'failed'].includes(item.result) ? item.result : 'not_executed',
    actual_result: item.actual_result || '',
    remark: item.remark || '',
    submit_bug: false,
  })
}

const cancelCorrectExecution = () => {
  correctingExecutionId.value = null
  Object.assign(executionForm, { result: 'passed', actual_result: '', remark: '', submit_bug: false })
}

const submitExecution = async () => {
  const { submit_bug: submitBugAfterFailure, ...executionPayload } = executionForm
  let execution
  if (correctingExecutionId.value) {
    execution = await correctWorkbenchExecution(correctingExecutionId.value, executionPayload)
  } else {
    execution = await createWorkbenchExecution({ test_case_id: selectedCase.value.id, ...executionPayload })
  }
  selectedExecution.value = execution
  const needsBug = !correctingExecutionId.value && executionForm.result === 'failed' && submitBugAfterFailure
  correctingExecutionId.value = null
  executionDialog.visible = false
  await loadDashboardStats()
  assetListRefreshKey.value += 1
  if (needsBug) openBug(selectedCase.value, execution)
}

const openBug = (row, execution = null) => {
  selectedCase.value = row
  selectedExecution.value = execution
  const steps = (row.steps_json || []).map(item => typeof item === 'string' ? item : (item.step || item.action || '')).filter(Boolean).join('\n')
  const actualResult = execution?.actual_result || ''
  Object.assign(bugForm, {
    title: `【执行失败】${row.title}`,
    steps,
    actual_result: actualResult,
    expected_result: row.expected_result || '',
    severity: 'minor',
    priority: 'P2',
    assignee_id: null,
    verifier_id: null,
  })
  bugDialog.visible = true
}

const submitBug = async () => {
  await createWorkbenchBug({
    project_id: projectId.value,
    system_id: selectedCase.value?.system_id || selectedSystem.value?.id,
    version_id: selectedCase.value?.version_id || selectedVersion.value?.id,
    requirement_id: selectedCase.value?.requirement_id,
    test_case_id: selectedCase.value?.id,
    execution_id: selectedExecution.value?.id,
    ...bugForm,
  })
  bugDialog.visible = false
  await loadDashboardStats()
  assetListRefreshKey.value += 1
}

const openLegacy = () => {
  Object.assign(legacyForm, { title: '', type: 'bug', description: '', planned_version_id: null })
  legacyDialog.visible = true
}

const submitLegacy = async () => {
  await createWorkbenchLegacyItem({
    project_id: projectId.value,
    system_id: selectedSystem.value.id,
    version_id: selectedVersion.value.id,
    ...legacyForm,
  })
  legacyDialog.visible = false
  await loadDashboardStats()
  assetListRefreshKey.value += 1
}

provide('workbenchContext', {
    dashboardStats,
  selectedProject,
    systems,
  versions,
  selectedSystem,
    selectedVersion,
    scope,
    scopeRefreshKey,
    selectSystem,
    selectVersion,
    selectAllScope,
    refreshScopeOptions: loadSystems,
  openCreate,
  openExecution,
  openBug,
  openLegacy,
  assetListRefreshKey,
  refreshDashboardStats: loadDashboardStats,
})

onMounted(async () => {
  await loadProject()
  await loadSystems()
  await applyRouteScope()
  await loadDashboardStats()
})

watch(() => [route.query.system_id, route.query.version_id], () => {
  applyRouteScope()
})
</script>

<style scoped>
.workbench-page {
  height: calc(100vh - 114px);
  display: grid;
  grid-template-columns: 240px 1fr;
  overflow: hidden;
  background: #f5f7fb;
}

.wb-main {
  display: flex;
  min-width: 0;
  min-height: 0;
  padding: 14px;
  box-sizing: border-box;
  overflow: hidden;
}

.wb-main > * { flex: 1; min-width: 0; min-height: 0; }

@media (max-width: 1600px) {
  .workbench-page { grid-template-columns: 220px minmax(0, 1fr); }
  .wb-main { padding: 12px; }
}
@media (max-width: 1440px) {
  .workbench-page { grid-template-columns: 200px minmax(0, 1fr); }
  .wb-main { padding: 10px; }
}
@media (max-width: 1180px) {
  .workbench-page { grid-template-columns: 190px minmax(0, 1fr); }
  .wb-main { overflow: hidden; }
}
</style>
