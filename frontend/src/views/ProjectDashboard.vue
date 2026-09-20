<template>
  <div class="dashboard-page">
    <div class="dashboard-header">
      <h2>数据看板</h2>
      <el-button v-if="canClearProjectData" type="danger" plain :loading="clearing" @click="handleClearProjectData">清空项目数据</el-button>
    </div>
    <div class="stat-grid">
      <div class="stat-card stat-card--env clickable" @click="goEnv">
        <div class="stat-label">环境数量</div>
        <div class="stat-row">
          <div class="stat-icon"><el-icon :size="24"><Setting /></el-icon></div>
          <div class="stat-value">{{ stats.environment_count }}</div>
        </div>
      </div>
      <div class="stat-card stat-card--iface clickable" @click="goInterface">
        <div class="stat-label">接口数量</div>
        <div class="stat-row">
          <div class="stat-icon"><el-icon :size="24"><Link /></el-icon></div>
          <div class="stat-value">{{ stats.interface_count }}</div>
        </div>
      </div>
      <div class="stat-card stat-card--case clickable" @click="goTestCase">
        <div class="stat-label">用例数量</div>
        <div class="stat-row">
          <div class="stat-icon"><el-icon :size="24"><Document /></el-icon></div>
          <div class="stat-value">{{ stats.test_case_count }}</div>
        </div>
      </div>
      <div class="stat-card stat-card--exec clickable" @click="goExecution">
        <div class="stat-label">执行集数量</div>
        <div class="stat-row">
          <div class="stat-icon"><el-icon :size="24"><VideoPlay /></el-icon></div>
          <div class="stat-value">{{ stats.execution_set_count }}</div>
        </div>
      </div>
      <div class="stat-card stat-card--iface-rate clickable" @click="goInterface">
        <div class="stat-label">接口处理率</div>
        <div class="stat-row">
          <div class="stat-icon"><el-icon :size="24"><CircleCheck /></el-icon></div>
          <div class="stat-value">{{ stats.interface_process_rate }}%</div>
        </div>
        <div class="stat-breakdown" @click.stop>
          <el-link type="primary" underline="never" @click="goInterfaceByWorkflowStatus('done')">
            已处理 {{ stats.interface_done_count }}
          </el-link>
          <span>/</span>
          <el-link type="primary" underline="never" @click="goInterfaceByWorkflowStatus('pending')">
            待处理 {{ stats.interface_pending_count }}
          </el-link>
        </div>
      </div>
      <div class="stat-card stat-card--case-rate">
        <div class="stat-label">用例确认率</div>
        <div class="stat-row">
          <div class="stat-icon"><el-icon :size="24"><DocumentChecked /></el-icon></div>
          <div class="stat-value">{{ stats.test_case_confirm_rate }}%</div>
        </div>
        <div class="stat-breakdown">
          <span>已确认 {{ stats.test_case_confirmed_count }}</span>
          <span>/</span>
          <span>待确认 {{ stats.test_case_pending_count }}</span>
        </div>
      </div>
      <div class="stat-card stat-card--contrib clickable" @click="caseDialogVisible = true">
        <div class="stat-label">用例贡献人数</div>
        <div class="stat-row">
          <div class="stat-icon"><el-icon :size="24"><User /></el-icon></div>
          <div class="stat-value">{{ stats.case_contributions?.length || 0 }}</div>
        </div>
        <div class="stat-hint">点击查看详情</div>
      </div>
      <div class="stat-card stat-card--iface-contrib clickable" @click="ifaceDialogVisible = true">
        <div class="stat-label">接口贡献人数</div>
        <div class="stat-row">
          <div class="stat-icon"><el-icon :size="24"><Edit /></el-icon></div>
          <div class="stat-value">{{ stats.iface_contributions?.length || 0 }}</div>
        </div>
        <div class="stat-hint">点击查看详情</div>
      </div>
    </div>

    <el-dialog v-model="caseDialogVisible" title="用例贡献排行" width="480px" destroy-on-close>
      <el-table v-if="stats.case_contributions?.length" :data="stats.case_contributions" stripe>
        <el-table-column prop="name" label="创建人" min-width="120" show-overflow-tooltip />
        <el-table-column prop="count" label="用例数" width="100" align="center" />
      </el-table>
      <GlobalEmpty v-else text="暂无数据" />
    </el-dialog>

    <el-dialog v-model="ifaceDialogVisible" title="接口贡献排行" width="480px" destroy-on-close>
      <el-table v-if="stats.iface_contributions?.length" :data="stats.iface_contributions" stripe>
        <el-table-column prop="name" label="创建人" min-width="120" show-overflow-tooltip />
        <el-table-column prop="count" label="接口数" width="100" align="center" />
      </el-table>
      <GlobalEmpty v-else text="暂无数据" />
    </el-dialog>

    <el-dialog
      v-model="cleanupDialog.visible"
      title="清空项目数据"
      width="min(860px, calc(100vw - 48px))"
      class="cleanup-dialog"
      :close-on-click-modal="false"
      :close-on-press-escape="!cleanupBusy"
      :show-close="!cleanupBusy"
      :before-close="beforeCloseCleanupDialog"
      @closed="resetCleanupDialog"
    >
      <el-steps :active="cleanupDialog.step" simple finish-status="success" class="wizard-steps-green">
        <el-step title="选择数据" />
        <el-step title="确认清理" />
      </el-steps>

      <section v-if="cleanupDialog.step === 0" class="cleanup-dialog-content">
        <p class="cleanup-dialog__hint">请选择需要清理的数据模块，确认后会写入审计记录。已删除数据无法在本页面恢复。</p>
        <div class="cleanup-selection-bar">
          <el-checkbox v-model="allCleanupTypesSelected" :disabled="cleanupDialog.loading">全部数据</el-checkbox>
          <span>已选 {{ cleanupDialog.assetTypes.length }}/{{ cleanupTypes.length }} 个数据模块</span>
        </div>
        <el-table v-loading="cleanupDialog.loading" :data="cleanupOptions" class="cleanup-table" height="310">
          <el-table-column width="56" align="center">
            <template #default="{ row }">
              <el-checkbox
                :model-value="cleanupDialog.assetTypes.includes(row.value)"
                :disabled="isCleanupTypeDisabled(row.value)"
                @change="toggleCleanupType(row.value, $event)"
              />
            </template>
          </el-table-column>
          <el-table-column prop="label" label="数据模块" min-width="220" />
          <el-table-column label="待清理数量" min-width="360">
            <template #default="{ row }">{{ row.count }} 个<span v-if="row.suffix" class="cleanup-table__suffix">（{{ row.suffix }}）</span></template>
          </el-table-column>
        </el-table>
      </section>

      <section v-else class="cleanup-dialog-content">
        <el-alert title="这是危险操作。确认后将删除以下数据，且无法在本页面恢复。" type="error" :closable="false" show-icon />
        <p class="cleanup-dialog__hint">清理范围：当前 API 测试项目</p>
        <el-table :data="selectedCleanupOptions" class="cleanup-table" height="250">
          <el-table-column prop="label" label="数据模块" min-width="220" />
          <el-table-column label="待清理数量" min-width="360">
            <template #default="{ row }">{{ row.count }} 个<span v-if="row.suffix" class="cleanup-table__suffix">（{{ row.suffix }}）</span></template>
          </el-table-column>
        </el-table>
      </section>

      <template #footer>
        <el-button :disabled="cleanupBusy" @click="cleanupDialog.visible = false">取消</el-button>
        <el-button v-if="cleanupDialog.step > 0" :disabled="cleanupBusy" @click="cleanupDialog.step -= 1">上一步</el-button>
        <el-button v-if="cleanupDialog.step === 0" type="primary" :loading="cleanupDialog.loading" :disabled="cleanupBusy || !canContinueCleanup" @click="goToNextCleanupStep">下一步</el-button>
        <el-button v-else type="danger" :loading="clearing" :disabled="cleanupBusy" @click="confirmClearProjectData">确认清空</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Setting, Link, Document, VideoPlay, User, Edit, CircleCheck, DocumentChecked } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { clearProjectBusinessData, getProject, getProjectBusinessCleanupSummary, getProjectDashboard } from '@/api/project'
import { useUserStore } from '@/stores/user'
import GlobalEmpty from '@/components/GlobalEmpty.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const projectId = computed(() => route.params.id)

const project = reactive({ owner_id: null, is_public: false })

const stats = reactive({
  environment_count: 0, interface_count: 0, test_case_count: 0,
  execution_set_count: 0,
  interface_done_count: 0, interface_pending_count: 0, interface_process_rate: 0,
  test_case_confirmed_count: 0, test_case_pending_count: 0, test_case_confirm_rate: 0,
  case_contributions: [], iface_contributions: [],
})
const caseDialogVisible = ref(false)
const ifaceDialogVisible = ref(false)
const clearing = ref(false)
const cleanupTypes = ['environment', 'interface', 'test_case', 'parameter_set', 'execution_set', 'report']
const cleanupDialog = reactive({ visible: false, step: 0, loading: false, assetTypes: [], summary: {} })
const cleanupBusy = computed(() => cleanupDialog.loading || clearing.value)
let cleanupRequestNo = 0

const canClearProjectData = computed(() => {
  const user = userStore.userInfo
  return Boolean(user && (
    user.is_superuser
    || project.owner_id === user.id
    && !project.is_public
  ))
})

const cleanupOptions = computed(() => [
  { value: 'environment', label: '环境', count: cleanupDialog.summary.environment_count || 0 },
  {
    value: 'interface',
    label: '接口',
    count: cleanupDialog.summary.interface_count || 0,
    suffix: `含 ${cleanupDialog.summary.interface_collection_count || 0} 个接口集、${cleanupDialog.summary.interface_case_count || 0} 个关联用例`,
  },
  {
    value: 'test_case',
    label: '用例',
    count: cleanupDialog.summary.test_case_count || 0,
    suffix: `其中 ${cleanupDialog.summary.test_case_execution_item_count || 0} 个用例已加入执行集`,
  },
  {
    value: 'parameter_set',
    label: '参数集',
    count: cleanupDialog.summary.parameter_set_count || 0,
    suffix: `含 ${cleanupDialog.summary.parameter_item_count || 0} 个参数项`,
  },
  {
    value: 'execution_set',
    label: '执行集',
    count: cleanupDialog.summary.execution_set_count || 0,
    suffix: `含 ${cleanupDialog.summary.execution_set_item_count || 0} 个执行项，解除 ${cleanupDialog.summary.execution_set_report_reference_count || 0} 条报告关联`,
  },
  {
    value: 'report',
    label: '测试报告',
    count: cleanupDialog.summary.report_count || 0,
    suffix: `含 ${cleanupDialog.summary.report_detail_count || 0} 条明细、${cleanupDialog.summary.report_send_log_count || 0} 条发送记录`,
  },
])
const allCleanupTypesSelected = computed({
  get: () => cleanupDialog.assetTypes.length === cleanupTypes.length,
  set: value => { cleanupDialog.assetTypes = value ? [...cleanupTypes] : [] },
})
const selectedCleanupOptions = computed(() => cleanupOptions.value.filter(item => cleanupDialog.assetTypes.includes(item.value)))
const canContinueCleanup = computed(() => cleanupDialog.assetTypes.length > 0)
const isCleanupTypeDisabled = assetType => (
  cleanupDialog.loading
  || (assetType === 'test_case' && cleanupDialog.assetTypes.includes('interface'))
)

const goEnv = () => router.push(`/project/${projectId.value}/environments`)
const goInterface = () => router.push(`/project/${projectId.value}/interfaces`)
const goTestCase = () => router.push(`/project/${projectId.value}/interfaces`)
const goExecution = () => router.push(`/project/${projectId.value}/executions`)
const goInterfaceByWorkflowStatus = workflowStatus => router.push({
  path: `/project/${projectId.value}/interfaces`,
  query: { workflow_status: workflowStatus },
})

const loadDashboard = async () => {
  try {
    const res = await getProjectDashboard(projectId.value)
    Object.assign(stats, res || {})
  } catch { /* ignore */ }
}

const loadProject = async () => {
  try {
    const res = await getProject(projectId.value)
    Object.assign(project, res || {})
  } catch { /* ignore */ }
}

const loadCleanupSummary = async () => {
  const requestNo = ++cleanupRequestNo
  cleanupDialog.loading = true
  try {
    const summary = await getProjectBusinessCleanupSummary(projectId.value)
    if (requestNo === cleanupRequestNo && cleanupDialog.visible) cleanupDialog.summary = summary || {}
  } finally {
    if (requestNo === cleanupRequestNo) cleanupDialog.loading = false
  }
}

const handleClearProjectData = () => {
  cleanupRequestNo += 1
  cleanupDialog.step = 0
  cleanupDialog.assetTypes = [...cleanupTypes]
  cleanupDialog.summary = {}
  cleanupDialog.visible = true
  loadCleanupSummary()
}

const toggleCleanupType = (assetType, checked) => {
  const selected = new Set(cleanupDialog.assetTypes)
  if (checked) selected.add(assetType)
  else selected.delete(assetType)
  if (assetType === 'interface') {
    if (checked) selected.add('test_case')
    else selected.delete('test_case')
  }
  cleanupDialog.assetTypes = cleanupTypes.filter(item => selected.has(item))
}

const goToNextCleanupStep = () => {
  cleanupDialog.step = 1
}

const formatCleanupResult = summary => {
  const deletedCaseCount = Number(summary?.test_case_count || 0) || Number(summary?.interface_case_count || 0)
  const items = [
    ['环境', summary?.environment_count],
    ['接口', summary?.interface_count],
    ['用例', deletedCaseCount],
    ['参数集', summary?.parameter_set_count],
    ['执行集', summary?.execution_set_count],
    ['测试报告', summary?.report_count],
  ].filter(([, count]) => Number(count) > 0).map(([label, count]) => `${label} ${count} 个`)
  return items.length ? `项目数据已清理：${items.join('、')}` : '项目数据已清理，没有可清理数据'
}

const beforeCloseCleanupDialog = done => {
  if (!cleanupBusy.value) done()
}

const resetCleanupDialog = () => {
  cleanupRequestNo += 1
  cleanupDialog.step = 0
  cleanupDialog.loading = false
  cleanupDialog.assetTypes = []
  cleanupDialog.summary = {}
}

const confirmClearProjectData = async () => {
  clearing.value = true
  try {
    const result = await clearProjectBusinessData(projectId.value, { asset_types: cleanupDialog.assetTypes })
    cleanupDialog.visible = false
    ElMessage.success(formatCleanupResult(result))
    await loadDashboard()
  } finally {
    clearing.value = false
  }
}

onMounted(async () => {
  if (!userStore.userInfo) await userStore.getUserInfo()
  await Promise.all([loadProject(), loadDashboard()])
})
</script>

<style scoped>
.dashboard-page { padding: 0; }
.dashboard-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 0 0 24px; }
.dashboard-header h2 { margin: 0; font-size: 22px; font-weight: 700; }

/* 4 列网格 */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

/* 卡片通用 */
.stat-card {
  position: relative; overflow: hidden;
  border-radius: 14px; padding: 24px 28px 22px;
  display: flex; flex-direction: column;
  justify-content: center;
  min-height: 152px;
  transition: transform .2s, box-shadow .2s;
}
.stat-card::after {
  content: ''; position: absolute; right: -30px; top: -30px;
  width: 120px; height: 120px; border-radius: 50%;
  background: rgba(255,255,255,.4); pointer-events: none;
}
.stat-card.clickable { cursor: pointer; }
.stat-card.clickable:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,.14); }

/* 标签 */
.stat-label {
  font-size: 13px; z-index: 1;
  margin-bottom: 14px;
  opacity: 0.85;
}

/* 图标+数字 横行 */
.stat-row {
  display: flex; align-items: center; gap: 10px;
  z-index: 1;
}

/* 图标 */
.stat-icon {
  width: 44px; height: 44px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(255,255,255,.55);
  color: inherit;
  flex-shrink: 0;
}

/* 数值 */
.stat-value {
  font-size: 40px; font-weight: 800; line-height: 1;
  z-index: 1;
}

.stat-breakdown {
  display: flex; align-items: center; gap: 5px;
  margin-top: 12px; font-size: 12px; line-height: 18px;
  color: inherit; opacity: .82; z-index: 1;
}
.stat-breakdown .el-link { color: inherit; font-size: inherit; }
.stat-breakdown .el-link:hover { opacity: .72; }

/* 底部提示 */
.stat-hint {
  font-size: 12px; margin-top: 12px; z-index: 1;
  opacity: 0.7;
}

/* === 6 种配色 === */
.stat-card--env {
  background: linear-gradient(135deg, rgba(230,244,255,.55) 0%, rgba(145,202,255,.45) 100%);
  border: 1px solid rgba(22,119,255,.15);
  color: #0958d9;
  backdrop-filter: blur(8px);
}
.stat-card--iface {
  background: linear-gradient(135deg, rgba(255,241,240,.55) 0%, rgba(255,163,158,.45) 100%);
  border: 1px solid rgba(245,108,108,.15);
  color: #a8071a;
  backdrop-filter: blur(8px);
}
.stat-card--case {
  background: linear-gradient(135deg, rgba(246,255,237,.55) 0%, rgba(183,235,143,.45) 100%);
  border: 1px solid rgba(82,196,26,.15);
  color: #237804;
  backdrop-filter: blur(8px);
}
.stat-card--exec {
  background: linear-gradient(135deg, rgba(255,247,230,.55) 0%, rgba(255,213,145,.45) 100%);
  border: 1px solid rgba(230,162,60,.15);
  color: #ad4e00;
  backdrop-filter: blur(8px);
}
.stat-card--iface-rate {
  background: linear-gradient(135deg, rgba(230,247,255,.68) 0%, rgba(145,213,255,.5) 100%);
  border: 1px solid rgba(24,144,255,.16);
  color: #096dd9;
  backdrop-filter: blur(8px);
}
.stat-card--case-rate {
  background: linear-gradient(135deg, rgba(246,255,237,.72) 0%, rgba(183,235,143,.5) 100%);
  border: 1px solid rgba(82,196,26,.16);
  color: #389e0d;
  backdrop-filter: blur(8px);
}
.stat-card--contrib {
  background: linear-gradient(135deg, rgba(249,240,255,.55) 0%, rgba(211,173,247,.45) 100%);
  border: 1px solid rgba(114,46,209,.15);
  color: #531dab;
  backdrop-filter: blur(8px);
}
.stat-card--iface-contrib {
  background: linear-gradient(135deg, rgba(230,255,251,.55) 0%, rgba(135,232,222,.45) 100%);
  border: 1px solid rgba(0,109,117,.15);
  color: #006d75;
  backdrop-filter: blur(8px);
}

/* 弹窗 */
:deep(.el-dialog) { display: flex; flex-direction: column; max-height: min(90vh, 750px); }
:deep(.el-dialog__body) { flex: 1; overflow-y: auto; padding: 20px 28px; }
.cleanup-dialog-content { display: flex; flex-direction: column; gap: 14px; padding-top: 20px; }
.cleanup-dialog__hint { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; line-height: 20px; }
.cleanup-selection-bar { display: flex; align-items: center; justify-content: space-between; min-height: 34px; color: var(--el-text-color-regular); font-size: 13px; }
.cleanup-table :deep(.el-table__cell) { padding: 9px 0; }
.cleanup-table :deep(.el-table__header .cell), .cleanup-table :deep(.el-table__body .cell) { white-space: nowrap; }
.cleanup-table :deep(.el-table__body .cell) { overflow: hidden; text-overflow: ellipsis; }
.cleanup-table__suffix { color: var(--el-text-color-secondary); }

/* 响应式 */
@media (max-width: 1024px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); gap: 16px; }
  .stat-card { padding: 24px 20px 20px; min-height: 140px; }
  .stat-value { font-size: 32px; }
}
@media (max-width: 768px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .stat-card { padding: 20px 16px 18px; min-height: 100px; }
  .stat-value { font-size: 28px; }
  .stat-icon { width: 36px; height: 36px; border-radius: 10px; }
  :deep(.el-dialog) { width: 95vw !important; max-width: 95vw !important; }
  :deep(.el-table) { font-size: 13px; overflow-x: auto; display: block; }
}
@media (max-width: 480px) {
  .stat-grid { grid-template-columns: 1fr; gap: 10px; }
  .stat-card { padding: 16px 14px 14px; min-height: 80px; }
  .stat-value { font-size: 24px; }
}
</style>
