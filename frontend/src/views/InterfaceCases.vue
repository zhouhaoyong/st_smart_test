<template>
  <div class="cases-layout">
    <!-- 左侧 -->
    <aside class="cases-sidebar">
      <div class="sidebar-header">
        <CollectionSingleSelect
          v-model="selectedColId"
          :collection-tree="collections"
          :loading="colsLoading"
          :clearable="false"
          display-mode="cascader"
          :show-all-levels="false"
          placeholder="选择接口集"
          @change="onColChange"
        />
      </div>
      <div class="sidebar-list" v-loading="ifsLoading">
        <div
          v-for="iface in interfaces"
          :key="iface.id"
          class="sidebar-iface"
          :class="{
            active: currentIfaceId === iface.id,
            'is-done': iface.workflow_status === 'done',
            'is-pending': iface.workflow_status !== 'done',
          }"
          @click="switchInterface(iface)"
        >
          <span
            class="iface-method"
            :class="'method-' + (iface.method || 'get').toLowerCase()"
            :title="iface.method || 'GET'"
          >{{ methodBadgeLabel(iface.method) }}</span>
          <div class="iface-info">
            <span class="iface-name">
              <span
                class="iface-name-text"
                title="查看接口详情"
                @click.stop="openIfaceDetail(iface.id)"
              >{{ iface.name }}</span>
            </span>
            <span class="iface-url" :title="iface.url || '暂无地址'">{{ iface.url || '—' }}</span>
          </div>
          <div class="iface-side-meta">
            <button
              type="button"
              class="iface-status-trigger"
              :title="`点击修改接口状态：${iface.workflow_status === 'done' ? '已处理' : '待处理'}`"
              :aria-label="`修改接口状态：${iface.workflow_status === 'done' ? '已处理' : '待处理'}`"
              @click.stop="openWorkflowStatusDialog(iface)"
            >
              <el-icon :size="13" aria-hidden="true"><Stamp /></el-icon>
            </button>
            <CaseCountStatusBadge
              :count="iface.test_case_count"
              :pending-count="iface.pending_test_case_count"
            />
          </div>
        </div>
        <GlobalEmpty v-if="!ifsLoading && interfaces.length === 0" text="暂无数据" />
      </div>
    </aside>

    <!-- 右侧 -->
    <main class="cases-main">
      <div class="main-header">
        <div class="main-title">
          <span class="title-label" style="cursor:pointer" @click="openIfaceDetail()">{{ currentIface?.name || '选择接口' }}</span>
          <!-- 方法用徽章、地址用底色块，和左侧接口列表、下方用例卡片保持一致 -->
          <span v-if="currentIface" class="title-endpoint" @click="openIfaceDetail()">
            <span class="method-badge" :class="'m-' + (currentIface.method || 'get').toLowerCase()">{{ (currentIface.method || 'GET').toUpperCase() }}</span>
            <span class="title-url" :title="currentIface.url || '暂无地址'">{{ currentIface.url || '—' }}</span>
          </span>
          <button
            v-if="currentIface"
            type="button"
            class="title-status-trigger"
            :title="`点击修改接口状态：${currentIface.workflow_status === 'done' ? '已处理' : '待处理'}`"
            :aria-label="`修改当前接口状态：${currentIface.workflow_status === 'done' ? '已处理' : '待处理'}`"
            @click.stop="openWorkflowStatusDialog(currentIface)"
          >
            <el-tag :type="currentIface.workflow_status === 'done' ? 'success' : 'warning'" size="small">
              {{ currentIface.workflow_status === 'done' ? '已处理' : '待处理' }}
            </el-tag>
          </button>
        </div>
        <div v-if="currentIfaceId" class="main-header-actions">
          <span class="case-summary">共 {{ cases.length }} 个用例 · 待确认 {{ pendingCaseCount }} 个</span>
          <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新增用例</el-button>
          <el-button type="primary" plain @click="openInterfaceCaseGeneration">AI生成用例</el-button>
          <el-button
            type="success"
            plain
            :loading="batchConfirming"
            :disabled="!currentIfaceId || pendingCaseCount === 0"
            @click="handleBatchConfirm"
          >批量确认</el-button>
          <el-button
            type="danger"
            plain
            :loading="batchDeleting"
            :disabled="casesLoading || cases.length === 0"
            @click="handleBatchDelete"
          ><el-icon><Delete /></el-icon>用例删除</el-button>
        </div>
      </div>

      <div
        class="cards-grid"
        :class="{ 'is-empty': !casesLoading && cases.length === 0 }"
        v-loading="casesLoading"
      >
        <GlobalEmpty v-if="!casesLoading && cases.length === 0 && currentIfaceId" text="暂无数据" />
        <GlobalEmpty v-if="!currentIfaceId" text="请选择接口" />
        <el-card v-for="tc in cases" :key="tc.id" class="case-card"
          :class="confirmStatusClass(tc.confirm_status)"
          shadow="hover"
          @click="openEdit(tc)">
          <div class="card-head">
            <el-tag :type="priorityTag(tc.priority)" :class="priorityTagClass(tc.priority)" size="small">{{ priorityLabel(tc.priority) }}</el-tag>
            <span class="card-name">{{ tc.name }}</span>
            <el-tag :type="tc.confirm_status === 'confirmed' ? 'success' : 'warning'" size="small">
              {{ tc.confirm_status_label || (tc.confirm_status === 'confirmed' ? '已确认' : '待确认') }}
            </el-tag>
          </div>
          <div class="card-url">{{ tc.url || '-' }}</div>
          <div class="card-meta">
            <span class="assertion-badge-icon" aria-hidden="true"><el-icon :size="9"><Check /></el-icon></span>
            <span>{{ tc.assertions?.length || 0 }} 个断言</span>
          </div>
          <div class="card-times">
            <span>创建时间：{{ formatCaseTime(tc.created_at) }}</span>
            <span>修改时间：{{ formatCaseTime(tc.updated_at) }}</span>
          </div>
          <div class="card-creator">
            <span class="card-creator-avatar" :style="tc.created_by_avatar ? {} : { background: creatorAvatarColor(tc.created_by) }">
              <img v-if="tc.created_by_avatar" :src="tc.created_by_avatar" alt="创建人头像" />
              <span v-else>{{ creatorInitial(tc.created_by_name) }}</span>
            </span>
            <span class="card-creator-name">{{ tc.created_by_name || '—' }}</span>
          </div>
          <div class="card-actions">
            <el-button size="small" @click.stop="runCase(tc)"><el-icon><VideoPlay /></el-icon>运行</el-button>
            <el-button size="small" @click.stop="openEdit(tc)"><el-icon><Edit /></el-icon></el-button>
            <el-button size="small" @click.stop="handleCopy(tc)"><el-icon><CopyDocument /></el-icon></el-button>
            <el-button size="small" type="danger" title="用例删除" aria-label="用例删除" @click.stop="handleDelete(tc)"><el-icon><Delete /></el-icon></el-button>
          </div>
        </el-card>
      </div>
    </main>

    <!-- 用例编辑弹窗：与 AI 导入预览共用同一套字段和参数配置 -->
    <TestCaseEditDialog
      v-model="showEdit"
      :title="isNew ? '新增用例' : '编辑用例'"
      :model="form"
      :active-tab="editTab"
      :saving="saving"
      :run-loading="runLoading"
      :response-sample-loader="loadResponseSampleForAssertion"
      @update:active-tab="editTab = $event"
      @run="runFromEdit"
      @save="handleSave"
    />
    <!-- 接口编辑弹窗：与接口管理页复用同一套完整编辑能力 -->
    <InterfaceEditDialog
      v-model="showIfaceDetail"
      title="编辑接口"
      :model="ifaceForm"
      :collection-tree="interfaceCollectionTree"
      :environment-services="environmentServices"
      :show-case-management="false"
      :saving="ifaceSaving"
      @save="saveIface"
      @debug-interface="debugIface"
    />
    <InterfaceWorkflowStatusDialog
      v-model="workflowStatusDialogVisible"
      :status="workflowStatusDialog.status"
      :saving="workflowStatusSaving"
      @save="saveWorkflowStatus"
    />

    <!-- AI 生成用例：复用接口管理页流程，但范围固定为当前接口 -->
    <BatchInterfaceCaseGenerationDialog
      v-model="interfaceCaseGenerationVisible"
      :project-id="projectId"
      :interfaces="currentInterfaceList"
      :interface-ids="currentInterfaceIds"
      :collection-tree="interfaceCollectionTree"
      fixed-scope
      @done="onInterfaceCaseGenerationDone"
    />

    <!-- 运行结果 -->
    <DebugPanel
      v-model="showRun"
      title="运行结果"
      :loading="runLoading"
      :error="runError"
      :steps="runSteps"
      :status-code="0"
      :duration="0"
      method=""
      request-url=""
      full-url=""
      :req-headers="{}"
      req-body=""
    />

    <!-- 接口调试（与接口管理页同一套调试逻辑与展示） -->
    <DebugPanel
      v-model="debugDialogVisible"
      title="接口调试"
      :method="debugMethod"
      :request-url="debugRequestUrl"
      :full-url="debugFullUrl"
      :req-headers="debugReqHeaders"
      :req-proxy="debugReqProxy"
      :req-service="debugReqService"
      :req-body="debugRequestBody"
      :req-params="debugReqParams"
      :req-path-params="debugReqPathParams"
      :loading="debugLoading"
      :response="debugResponse"
      :error="debugError"
      :status-code="debugStatusCode"
      :duration="debugDuration"
      :resp-headers="debugRespHeaders"
      :logs="debugLogs"
      @send="sendDebugRequest"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import CaseCountStatusBadge from '@/components/CaseCountStatusBadge.vue'
import { Plus, Edit, Delete, VideoPlay, CopyDocument, Check, Stamp } from '@element-plus/icons-vue'
import DebugPanel from '@/components/DebugPanel.vue'
import InterfaceEditDialog from '@/components/InterfaceEditDialog.vue'
import InterfaceWorkflowStatusDialog from '@/components/InterfaceWorkflowStatusDialog.vue'
import TestCaseEditDialog from '@/components/TestCaseEditDialog.vue'
import BatchInterfaceCaseGenerationDialog from '@/components/BatchInterfaceCaseGenerationDialog.vue'
import CollectionSingleSelect from '@/components/CollectionSingleSelect.vue'
import { getCollectionTree } from '@/api/collections'
import { getInterfaces, getInterface, updateInterface } from '@/api/interfaces'
import { getTestCases, getTestCase, createTestCase, updateTestCase, copyTestCase, deleteTestCase, batchDeleteTestCasesByInterface, batchConfirmTestCases } from '@/api/testcases'
import { runTestCase } from '@/api/executor'
import { useInterfaceDebug } from '@/composables/useInterfaceDebug'
import { useUserStore } from '@/stores/user'
import { normalizeExecutionStep, pickResponseBodyText } from '@/utils/executionResult'
import { getEnvironmentServices } from '@/utils/serviceEnvironment'
import { formatBeijingTime } from '@/utils/beijingTime'
import { findCollectionPath } from '@/utils/interfaceCollections'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const projectId = computed(() => route.params.id)
const currentIfaceId = ref(Number(route.params.iid))
const currentIface = ref(null)
const currentInterfaceList = computed(() => currentIface.value ? [currentIface.value] : [])
const currentInterfaceIds = computed(() => (
  Number.isInteger(currentIfaceId.value) && currentIfaceId.value > 0 ? [currentIfaceId.value] : []
))
const selectedEnvironment = inject('selectedEnvironment', computed(() => null))

// Left sidebar
const collections = ref([])
const selectedColId = ref(null)
const interfaces = ref([])
const colsLoading = ref(false)
const ifsLoading = ref(false)
const interfacesRequestId = ref(0)
const caseCountByIface = ref({})

// Right cases
const cases = ref([])
const casesLoading = ref(false)
const routeCaseOpened = ref(false)
const batchConfirming = ref(false)
const batchDeleting = ref(false)
const interfaceCaseGenerationVisible = ref(false)
const pendingCaseCount = computed(() => cases.value.filter(tc => tc.confirm_status !== 'confirmed').length)

// Edit
const showEdit = ref(false)
const isNew = ref(true)
const saving = ref(false)
const editTab = ref('basic')
const form = ref({
  id: null,
  name: '', description: '', priority: 'high',
  created_by: null, updated_by: null,
  created_by_name: '', created_by_avatar: '', updated_by_name: '', updated_by_avatar: '',
  created_at: null, updated_at: null,
  confirm_status: 'pending', confirm_status_label: '待确认', confirm_reason: null, confirm_reason_label: null,
  method: 'GET', url: '', headers: [], query_params: [], path_params: [],
  body_type: '', body_content: '', body_schema_types: {},
  pre_script: '', post_script: '', script: '',
  assertions: [{ type: 'jsonpath', expression: '$.code', operator: 'eq', expected: '200', enabled: true }]
})
const editingId = ref(null)
const formatCaseTime = (value) => value ? formatBeijingTime(value) : '-'

function emptyForm() {
  return {
    id: null,
    name: '', description: '', priority: 'high',
    created_by: null, updated_by: null,
    created_by_name: '', created_by_avatar: '', updated_by_name: '', updated_by_avatar: '',
    created_at: null, updated_at: null,
    confirm_status: 'pending', confirm_status_label: '待确认', confirm_reason: null, confirm_reason_label: null,
    method: 'GET', url: '', headers: [], query_params: [], path_params: [],
    body_type: '', body_content: '', body_schema_types: {},
    pre_script: '', post_script: '', script: '',
    assertions: [{ type: 'jsonpath', expression: '$.code', operator: 'eq', expected: '200', enabled: true }]
  }
}

// Run
const showRun = ref(false)
const runLoading = ref(false)
const runError = ref(null)
const runSteps = ref([])
const selectedParameterSet = inject('selectedParameterSet', computed(() => null))

// 接口调试：与接口管理页共用同一套调试状态与请求逻辑
const {
  debugDialogVisible,
  debugLoading,
  debugMethod,
  debugRequestUrl,
  debugFullUrl,
  debugReqHeaders,
  debugReqProxy,
  debugReqService,
  debugReqParams,
  debugReqPathParams,
  debugRequestBody,
  debugResponse,
  debugRespHeaders,
  debugError,
  debugStatusCode,
  debugDuration,
  debugLogs,
  sendDebugRequest,
  openDebug,
} = useInterfaceDebug({ environment: selectedEnvironment, parameterSet: selectedParameterSet })

// Interface edit dialog (same as Interfaces.vue, without "用例管理" button)
const showIfaceDetail = ref(false)
const ifaceSaving = ref(false)
const workflowStatusDialogVisible = ref(false)
const workflowStatusSaving = ref(false)
const workflowStatusDialog = ref({ interfaceId: null, status: 'pending' })
const ifaceForm = ref({
  id: null, name: '', method: 'GET', url: '', description: '', collection_id: null,
  service_key: null,
  tags: [],
  created_by: null, updated_by: null,
  created_by_name: '', created_by_avatar: '', updated_by_name: '', updated_by_avatar: '',
  created_at: null, updated_at: null,
  workflow_status: 'pending', workflow_status_label: '待处理', pending_reason: null, pending_reason_label: null,
  headers: [], query_params: [], path_params: [],
  body_type: '', body_content: '', body_schema_types: {}, pre_script: '', post_script: '',
})
const interfaceCollectionTree = ref([])
const environmentServices = computed(() => getEnvironmentServices(selectedEnvironment.value))

async function openIfaceDetail(ifaceId) {
  const targetId = ifaceId || currentIfaceId.value
  if (!targetId) return
  try {
    const res = await getInterface(targetId)
    Object.assign(ifaceForm.value, {
      id: res.id, name: res.name, method: res.method, url: res.url || '',
      description: res.description || '', collection_id: res.collection_id,
      service_key: res.service_key || null,
      tags: Array.isArray(res.tags) ? [...res.tags] : [],
      created_by: res.created_by, updated_by: res.updated_by,
      created_by_name: res.created_by_name || '', created_by_avatar: res.created_by_avatar || '',
      updated_by_name: res.updated_by_name || '', updated_by_avatar: res.updated_by_avatar || '',
      created_at: res.created_at, updated_at: res.updated_at,
      workflow_status: res.workflow_status || 'pending', workflow_status_label: res.workflow_status_label || '待处理',
      pending_reason: res.pending_reason || null, pending_reason_label: res.pending_reason_label || null,
      headers: res.headers?.length ? [...res.headers] : [],
      query_params: res.query_params?.length ? [...res.query_params] : [],
      path_params: res.path_params?.length ? [...res.path_params] : [],
      body_type: res.body_type || '', body_content: res.body_content || '',
      body_schema_types: res.body_schema_types && typeof res.body_schema_types === 'object' ? { ...res.body_schema_types } : {},
      pre_script: res.pre_script || '', post_script: res.post_script || '',
    })
    const tree = await getCollectionTree(projectId.value)
    interfaceCollectionTree.value = tree || []
    showIfaceDetail.value = true
  } catch {}
}

async function saveIface(updatedIface) {
  // 弹窗可能打开的是左侧列表里非当前选中的接口，必须按弹窗里的接口保存
  const editingIfaceId = updatedIface?.id
  if (!editingIfaceId || ifaceSaving.value) return
  ifaceSaving.value = true
  try {
    const { id, ...payload } = updatedIface
    await updateInterface(id, payload)
    showIfaceDetail.value = false
    if (currentIfaceId.value === editingIfaceId) {
      currentIface.value = {
        ...currentIface.value,
        name: updatedIface.name,
        method: updatedIface.method,
        url: updatedIface.url,
        collection_id: updatedIface.collection_id,
      }
    }
    if (selectedColId.value && updatedIface.collection_id !== selectedColId.value) {
      selectedColId.value = updatedIface.collection_id
      await loadInterfaces(selectedColId.value)
    } else if (selectedColId.value) {
      // 名称/方法/URL 变了，左侧列表要跟着刷新
      await loadInterfaces(selectedColId.value)
    }
    await loadCollections()
  } catch {} finally { ifaceSaving.value = false }
}

function debugIface(iface = ifaceForm.value) {
  // 调试弹窗叠加在接口详情之上：详情保持打开，关掉调试后可继续编辑未保存的内容
  openDebug({
    id: iface.id || currentIfaceId.value,
    method: iface.method,
    url: iface.url,
    headers: iface.headers || [],
    query_params: iface.query_params || [],
    path_params: iface.path_params || [],
    body_type: iface.body_type || '',
    body_content: iface.body_content || '',
    pre_script: iface.pre_script || '',
    post_script: iface.post_script || '',
    service_key: iface.service_key || null,
  })
}

// 徽章固定宽度需要限长：只缩写超长的两个，其余保留全称，保证接口名左边缘对齐
const METHOD_BADGE_LABELS = { DELETE: 'DEL', OPTIONS: 'OPT' }
function methodBadgeLabel(method) {
  const m = (method || 'GET').toUpperCase()
  return METHOD_BADGE_LABELS[m] || m
}

function defaultTab(method) {
  const m = (method || 'GET').toUpperCase()
  return (m === 'POST' || m === 'PUT' || m === 'PATCH') ? 'body' : 'query'
}
const normalizePriority = priority => ['high', 'medium', 'low'].includes(priority) ? priority : 'medium'
function confirmStatusClass(status) {
  return status === 'confirmed' ? 'is-confirmed' : 'is-pending'
}
function priorityTag(priority) {
  const p = normalizePriority(priority)
  return p === 'high' ? 'danger' : p === 'low' ? 'info' : 'warning'
}
function priorityTagClass(priority) { return `priority-tag-${normalizePriority(priority)}` }
function priorityLabel(priority) {
  const p = normalizePriority(priority)
  return p === 'high' ? '高' : p === 'low' ? '低' : '中'
}
const creatorAvatarColors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#f5222d', '#faad14']
function creatorAvatarColor(id) { return creatorAvatarColors[(id || 0) % creatorAvatarColors.length] }
function creatorInitial(name) { return (name || '?').trim().charAt(0) || '?' }

// 按项目记住上次选择的接口集，刷新后仍停留在原来的接口集下
const collectionMemoryKey = () => `interface_cases_collection_${projectId.value}`
function readRememberedCollectionId() {
  try {
    const value = Number(localStorage.getItem(collectionMemoryKey()))
    return value > 0 ? value : null
  } catch { return null }
}
function rememberCollectionId(colId) {
  try {
    if (colId) localStorage.setItem(collectionMemoryKey(), String(colId))
    else localStorage.removeItem(collectionMemoryKey())
  } catch {}
}

onMounted(async () => {
  if (currentIfaceId.value) {
    // 先找到当前接口所属的集合，再加载
    try {
      const iface = await getInterface(currentIfaceId.value)
      currentIface.value = iface
      const colId = iface.collection_id
      if (colId) selectedColId.value = colId
    } catch {
      // 接口已被删除或无权访问：回到空状态，改用记住的接口集
      currentIfaceId.value = null
      currentIface.value = null
    }
  }
  if (!selectedColId.value) selectedColId.value = readRememberedCollectionId()
  await loadCollections()
  // 记住的接口集可能已被删除，此时清掉记忆并留空
  if (selectedColId.value && !findCollectionPath(collections.value, selectedColId.value).length) {
    selectedColId.value = null
    rememberCollectionId(null)
  }
  if (selectedColId.value) {
    rememberCollectionId(selectedColId.value)
    await loadInterfaces(selectedColId.value)
  }
  if (currentIfaceId.value) loadCases()
})

async function loadCollections() {
  colsLoading.value = true
  try {
    const tree = await getCollectionTree(projectId.value)
    collections.value = tree || []
    interfaceCollectionTree.value = tree || []
  } catch {
    collections.value = []
    interfaceCollectionTree.value = []
  }
  finally { colsLoading.value = false }
}

async function loadInterfaces(colId) {
  if (!colId) return
  const requestId = ++interfacesRequestId.value
  ifsLoading.value = true
  try {
    const res = await getInterfaces(colId, projectId.value, 1, 100)
    if (requestId !== interfacesRequestId.value) return
    interfaces.value = Array.isArray(res?.items) ? res.items : (Array.isArray(res) ? res : [])
    // 后端接口列表已批量返回用例数，避免为每个接口重复请求用例列表。
    for (const iface of interfaces.value) {
      caseCountByIface.value[iface.id] = Number(iface.test_case_count) || 0
    }
    // Set selected collection
    if (currentIfaceId.value) {
      const cur = interfaces.value.find(i => i.id === currentIfaceId.value)
      if (cur) {
        currentIface.value = cur
        if (!selectedColId.value) selectedColId.value = cur.collection_id
      }
    }
  } catch {
    if (requestId === interfacesRequestId.value) interfaces.value = []
  }
  finally {
    if (requestId === interfacesRequestId.value) ifsLoading.value = false
  }
}

function buildCaseRunOverrides(overrides) {
  const fields = [
    'method', 'url', 'headers', 'query_params', 'path_params',
    'body_content', 'body_schema_types', 'body_type', 'pre_script', 'post_script',
  ]
  return fields.reduce((result, field) => {
    if (Object.prototype.hasOwnProperty.call(overrides, field)) {
      result[field] = overrides[field]
    }
    return result
  }, {})
}

async function onColChange(colId) {
  selectedColId.value = colId
  rememberCollectionId(colId)
  currentIfaceId.value = null
  currentIface.value = null
  cases.value = []
  routeCaseOpened.value = false
  await loadInterfaces(colId)
  const firstInterface = interfaces.value[0]
  if (firstInterface) {
    switchInterface(firstInterface)
  } else {
    currentIfaceId.value = null
    currentIface.value = null
    cases.value = []
    casesLoading.value = false
  }
}

function switchInterface(iface) {
  currentIfaceId.value = iface.id
  currentIface.value = iface
  rememberCollectionId(selectedColId.value)
  // 同步地址栏，刷新后仍停留在当前接口；用 replace 是为了不往浏览器返回栈里堆记录
  if (Number(route.params.iid) !== iface.id) {
    router.replace({ name: 'InterfaceCases', params: { id: projectId.value, iid: iface.id } })
  }
  loadCases(iface.id)
}

async function loadCases(interfaceId = currentIfaceId.value) {
  if (!interfaceId) return
  casesLoading.value = true
  try {
    const res = await getTestCases(interfaceId)
    if (interfaceId !== currentIfaceId.value) return
    cases.value = Array.isArray(res) ? res : []
    const currentCaseCount = cases.value.length
    const pendingCaseCount = cases.value.filter(tc => tc.confirm_status !== 'confirmed').length
    caseCountByIface.value[interfaceId] = currentCaseCount
    const current = interfaces.value.find(iface => iface.id === interfaceId)
    if (current) {
      current.test_case_count = currentCaseCount
      current.pending_test_case_count = pendingCaseCount
    }
    openRouteCase()
  } catch {
    if (interfaceId === currentIfaceId.value) cases.value = []
  } finally {
    if (interfaceId === currentIfaceId.value) casesLoading.value = false
  }
}

function openWorkflowStatusDialog(iface) {
  if (!iface?.id) return
  workflowStatusDialog.value = {
    interfaceId: iface.id,
    status: iface.workflow_status || 'pending',
  }
  workflowStatusDialogVisible.value = true
}

async function saveWorkflowStatus(workflowStatus) {
  const interfaceId = workflowStatusDialog.value.interfaceId
  if (!interfaceId || workflowStatusSaving.value) return
  workflowStatusSaving.value = true
  try {
    await updateInterface(interfaceId, { workflow_status: workflowStatus })
    const statusLabel = workflowStatus === 'done' ? '已处理' : '待处理'
    const statusPatch = {
      workflow_status: workflowStatus,
      workflow_status_label: statusLabel,
    }
    interfaces.value = interfaces.value.map(iface => (
      iface.id === interfaceId ? { ...iface, ...statusPatch } : iface
    ))
    if (currentIface.value?.id === interfaceId) {
      currentIface.value = { ...currentIface.value, ...statusPatch }
    }
    if (ifaceForm.value.id === interfaceId) Object.assign(ifaceForm.value, statusPatch)
    await loadCollections()
    workflowStatusDialogVisible.value = false
  } catch {
    // 错误已由请求拦截器提示，保留弹窗便于重试
  } finally {
    workflowStatusSaving.value = false
  }
}

function openInterfaceCaseGeneration() {
  if (!projectId.value) {
    ElMessage.warning('缺少项目信息')
    return
  }
  if (!currentIfaceId.value) {
    ElMessage.warning('请先选择接口')
    return
  }
  interfaceCaseGenerationVisible.value = true
}

async function onInterfaceCaseGenerationDone() {
  await Promise.all([
    loadCases(),
    selectedColId.value ? loadInterfaces(selectedColId.value) : Promise.resolve(),
  ])
}

async function openRouteCase() {
  const routeCaseId = Number(route.query.tc)
  if (!routeCaseId || routeCaseOpened.value) return
  const target = cases.value.find(tc => tc.id === routeCaseId)
  if (!target) return
  const opened = await openEdit(target)
  if (!opened) return
  routeCaseOpened.value = true
  router.replace({ query: {} })
}

async function openCreate() {
  isNew.value = true
  editingId.value = null
  const base = emptyForm()
  // 从当前接口加载完整数据
  if (currentIfaceId.value) {
    try {
      const iface = await getInterface(currentIfaceId.value)
      base.method = iface.method || 'GET'
      base.url = iface.url || ''
      base.headers = (iface.headers || []).length ? JSON.parse(JSON.stringify(iface.headers)) : []
      base.query_params = (iface.query_params || []).length ? JSON.parse(JSON.stringify(iface.query_params)) : []
      base.path_params = (iface.path_params || []).length ? JSON.parse(JSON.stringify(iface.path_params)) : []
      base.body_type = iface.body_type || ''
      base.body_content = iface.body_content || ''
      base.body_schema_types = iface.body_schema_types || {}
      base.pre_script = iface.pre_script || ''
      base.post_script = iface.post_script || ''
    } catch {}
  }
  form.value = base
  editTab.value = defaultTab(form.value.method)
  showEdit.value = true
}

async function openEdit(tc) {
  let detail
  try {
    detail = await getTestCase(tc.id)
  } catch {
    return false
  }
  if (!detail) return false
  isNew.value = false
  editingId.value = detail.id
  editTab.value = defaultTab(detail.method)
  form.value = {
    id: detail.id,
    name: detail.name,
    description: detail.description || '',
    priority: detail.priority,
    created_by: detail.created_by, updated_by: detail.updated_by,
    created_by_name: detail.created_by_name || '', created_by_avatar: detail.created_by_avatar || '',
    updated_by_name: detail.updated_by_name || '', updated_by_avatar: detail.updated_by_avatar || '',
      created_at: detail.created_at, updated_at: detail.updated_at,
      confirm_status: detail.confirm_status || 'pending',
      confirm_status_label: detail.confirm_status_label || '待确认',
      confirm_reason: detail.confirm_reason || null,
      confirm_reason_label: detail.confirm_reason_label || null,
    method: detail.method || 'GET',
    url: detail.url || '',
    headers: detail.headers?.length ? JSON.parse(JSON.stringify(detail.headers)) : [],
    query_params: detail.query_params?.length ? JSON.parse(JSON.stringify(detail.query_params)) : [],
    path_params: detail.path_params?.length ? JSON.parse(JSON.stringify(detail.path_params)) : [],
    body_type: detail.body_type || '',
    body_content: detail.body_content || '',
    body_schema_types: detail.body_schema_types ? JSON.parse(JSON.stringify(detail.body_schema_types)) : {},
    pre_script: detail.pre_script || '',
    post_script: detail.post_script || '',
    script: detail.script || '',
    assertions: detail.assertions?.length ? JSON.parse(JSON.stringify(detail.assertions)) : [],
  }
  showEdit.value = true
  return true
}

async function handleSave() {
  if (!form.value.name.trim()) { ElMessage.warning('请输入用例名称'); return }
  saving.value = true
  try {
    const payload = {
      name: form.value.name, description: form.value.description,
      priority: form.value.priority, owner: userStore.userInfo?.real_name || '',
      project_id: Number(projectId.value), interface_id: currentIfaceId.value,
      assertions: form.value.assertions,
      param_overrides: {
        method: form.value.method,
        url: form.value.url,
        headers: form.value.headers,
        query_params: form.value.query_params,
        path_params: form.value.path_params,
        body_type: form.value.body_type,
        body_content: form.value.body_content,
        body_schema_types: form.value.body_schema_types,
        pre_script: form.value.pre_script,
        post_script: form.value.post_script,
      },
      script: form.value.script || null,
      confirm_status: form.value.confirm_status || 'pending',
    }
    if (isNew.value) {
      await createTestCase(payload)
    } else {
      await updateTestCase(editingId.value, payload)
    }
    showEdit.value = false
    await loadCases()
  } catch {} finally { saving.value = false }
}

// 编辑中的用例按当前表单内容运行，运行与字段选取共用同一份入参
function buildEditRunPayload() {
  return {
    environment_id: selectedEnvironment.value.id,
    parameter_set_id: selectedParameterSet.value?.id || null,
    interface_id: currentIfaceId.value,
    test_case_name: form.value.name || null,
    param_overrides: {
      method: form.value.method, url: form.value.url,
      headers: (form.value.headers || []).filter(h => h.key),
      query_params: (form.value.query_params || []).filter(q => q.key),
      path_params: form.value.path_params || [],
      body_content: form.value.body_content || '',
      body_type: form.value.body_type || '',
      pre_script: form.value.pre_script || '',
      post_script: form.value.post_script || '',
    },
    script: form.value.script || null,
    assertions: form.value.assertions || [],
  }
}

async function runFromEdit() {
  if (runLoading.value) return
  const env = selectedEnvironment.value
  if (!env?.id) { ElMessage.warning('请先在左侧选择运行环境'); return }
  showRun.value = true; runLoading.value = true; runError.value = null; runSteps.value = []
  try {
    const result = await runTestCase(buildEditRunPayload())
    runSteps.value = (result.steps || []).map(s => normalizeExecutionStep(s, form.value.name))
  } catch (e) { runError.value = e?.data?.message || e?.message || '运行失败' }
  finally { runLoading.value = false }
}

// 断言字段选取：现场跑一次，只取响应体文本，不打开运行结果弹窗
async function loadResponseSampleForAssertion({ signal } = {}) {
  if (!selectedEnvironment.value?.id) {
    ElMessage.warning('请先在左侧选择运行环境')
    return ''
  }
  const result = await runTestCase(buildEditRunPayload(), {
    signal,
    skipSuccessToast: true,
    skipErrorToast: true,
  })
  const step = (result.steps || [])[0]
  const text = pickResponseBodyText(step?.response)
  if (!text) ElMessage.warning(step?.msg || '本次请求没有返回可解析的响应内容')
  return text
}

async function handleCopy(tc) {
  try {
    await copyTestCase(tc.id)
    await loadCases()
  } catch {}
}

async function handleBatchConfirm() {
  const pendingCount = pendingCaseCount.value
  if (!currentIfaceId.value || pendingCount === 0 || batchConfirming.value) return
  try {
    await ElMessageBox.confirm(
      `当前接口共有 ${cases.value.length} 个用例，其中 ${pendingCount} 个待确认。确认后，这 ${pendingCount} 个用例将变为“已确认”状态。`,
      '批量确认',
      {
        type: 'warning',
        confirmButtonText: `确认 ${pendingCount} 个用例`,
        cancelButtonText: '取消',
      },
    )
    batchConfirming.value = true
    await batchConfirmTestCases(currentIfaceId.value)
    await loadCases()
  } catch {} finally {
    batchConfirming.value = false
  }
}

async function handleBatchDelete() {
  const caseCount = cases.value.length
  if (!currentIfaceId.value || caseCount === 0 || batchDeleting.value) return
  try {
    await ElMessageBox.confirm(
      `是否确认删除当前接口下的${caseCount}条用例？`,
      '用例删除',
      {
        type: 'warning',
        confirmButtonText: '确认删除',
        cancelButtonText: '我再想想',
      },
    )
    batchDeleting.value = true
    await batchDeleteTestCasesByInterface(projectId.value, currentIfaceId.value)
    await loadCases()
  } catch {} finally {
    batchDeleting.value = false
  }
}

async function handleDelete(tc) {
  try {
    await ElMessageBox.confirm(
      `确认删除用例「${tc.name}」？对应执行集中的该用例也将被删除。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除' }
    )
    await deleteTestCase(tc.id)
    loadCases()
    caseCountByIface.value[currentIfaceId.value] = Math.max(0, (caseCountByIface.value[currentIfaceId.value] || 1) - 1)
  } catch {}
}

async function runCase(tc) {
  if (runLoading.value) return
  const env = selectedEnvironment.value
  if (!env?.id) { ElMessage.warning('请先在左侧选择运行环境'); return }
  showRun.value = true
  runLoading.value = true
  runError.value = null
  runSteps.value = []
  try {
    const ifaceId = tc.interface_id || currentIfaceId.value
    const overrides = tc.param_overrides || {}
    const pathParams = overrides.path_params
    const paramOverrides = buildCaseRunOverrides(overrides)
    if (Array.isArray(pathParams)) paramOverrides.path_params = pathParams
    const result = await runTestCase({
      environment_id: env.id,
      parameter_set_id: selectedParameterSet.value?.id || null,
      interface_id: ifaceId,
      test_case_name: tc.name || null,
      param_overrides: paramOverrides,
      assertions: tc.assertions || [],
      script: tc.script || null,
    })
    runSteps.value = (result.steps || []).map(s => normalizeExecutionStep(s, tc.name))
  } catch (e) {
    runError.value = e?.data?.message || e?.message || '运行失败'
  } finally { runLoading.value = false }
}

// 地址栏接口变化（外部跳转、浏览器前进后退）时同步页面；
// 页面内切换接口已经提前更新了当前接口，这里判重避免重复请求用例
watch(() => route.params.iid, (v) => {
  const nextId = Number(v)
  if (!nextId || nextId === currentIfaceId.value) return
  currentIfaceId.value = nextId
  const known = interfaces.value.find(i => i.id === nextId)
  if (known) currentIface.value = known
  loadCases()
})
</script>

<style scoped>
.cases-layout { display: flex; min-width: 0; min-height: 0; height: 100%; gap: 12px; }
.cases-sidebar { width: clamp(240px, 18vw, 300px); min-height: 0; border: 1px solid #e8edf3; border-radius: 10px; display: flex; flex-direction: column; flex-shrink: 0; overflow: hidden; background: #fafafa; }
.sidebar-header { padding: 14px; }
.sidebar-list { flex: 1; overflow-y: auto; padding: 0 8px 8px; }
.sidebar-list,
.cards-grid {
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  scrollbar-color: #aeb8c4 #f7f9fc;
}
.sidebar-list::-webkit-scrollbar,
.cards-grid::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.sidebar-list::-webkit-scrollbar-track,
.cards-grid::-webkit-scrollbar-track {
  background: #f7f9fc;
  border-radius: 4px;
}
.sidebar-list::-webkit-scrollbar-thumb,
.cards-grid::-webkit-scrollbar-thumb {
  background: #aeb8c4;
  border: 2px solid #f7f9fc;
  border-radius: 4px;
}
.sidebar-list::-webkit-scrollbar-thumb:hover,
.cards-grid::-webkit-scrollbar-thumb:hover {
  background: #8996a5;
}
.sidebar-iface { display: flex; align-items: flex-start; gap: 8px; padding: 10px 12px; border-radius: 8px; cursor: pointer; font-size: 14px; margin-bottom: 3px; box-shadow: inset 0 -1px 0 rgba(148, 163, 184, 0.2); }
.sidebar-iface:hover { background: #f0f0f0; }
.sidebar-iface.active { background: #e6f4ff; color: #1677ff; box-shadow: inset 0 -1px 0 rgba(64, 158, 255, 0.28); }
.sidebar-iface.is-pending:not(.active) { background: linear-gradient(135deg, #fffaf0 0%, #fff3d9 100%); }
.sidebar-iface.is-done:not(.active) { background: linear-gradient(135deg, #f5fcf1 0%, #e4f4dc 100%); }
.sidebar-iface.is-pending:not(.active):hover { background: linear-gradient(135deg, #fff5df 0%, #ffecc7 100%); }
.sidebar-iface.is-done:not(.active):hover { background: linear-gradient(135deg, #ecf8e7 0%, #d9efcf 100%); }
.iface-method { margin-top: 2px; font-size: 11px; font-weight: 700; padding: 2px 0; border-radius: 3px; flex-shrink: 0; color: #fff; width: 44px; text-align: center; }
.method-get { background: #52c41a; }
.method-post { background: #1677ff; }
.method-put { background: #fa8c16; }
.method-delete { background: #f5222d; }
.method-patch { background: #722ed1; }
.iface-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.iface-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 18px; }
/* 仅名称文字宽度内是「打开接口详情」，行内其余留白仍为切换接口 */
.iface-name-text { cursor: pointer; }
.iface-name-text:hover { color: #1677ff; text-decoration: underline; text-underline-offset: 2px; }
.iface-url { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; line-height: 16px; color: #909399; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.iface-side-meta { display: inline-flex; align-items: center; gap: 6px; flex: 0 0 auto; height: 20px; margin-top: 1px; }
.iface-status-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 18px;
  width: 18px;
  min-width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  border-radius: 4px;
  color: #8c96a3;
  background: transparent;
  line-height: 1;
  cursor: pointer;
}
.iface-status-trigger:hover { color: #1677ff; background: #edf5ff; }
.sidebar-iface.active .iface-status-trigger { color: #409eff; }
.sidebar-iface.is-done .iface-status-trigger {
  color: #52c41a;
  background: rgba(82, 196, 26, 0.1);
}
.sidebar-iface.is-done .iface-status-trigger:hover {
  color: #389e0d;
  background: rgba(82, 196, 26, 0.18);
}
.iface-side-meta :deep(.case-count-status) { height: 20px; line-height: 18px; padding: 0 6px; }
.title-status-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 60px;
  width: 60px;
  min-width: 60px;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}
.title-status-trigger .el-tag { width: 60px; box-sizing: border-box; justify-content: center; }
.title-status-trigger:hover .el-tag { filter: brightness(0.97); }

.cases-main { display: flex; flex: 1; flex-direction: column; min-width: 0; min-height: 0; overflow: hidden; padding: 16px 20px; border: 1px solid #e8edf3; border-radius: 10px; background: #fff; }
.main-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 16px; }
.main-header-actions { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.case-summary { color: #909399; font-size: 13px; white-space: nowrap; }
/* 标题行混排了大号文字和徽章、地址块，基线对齐会让徽章偏下，改成居中 */
.main-title { display: flex; align-items: center; gap: 12px; min-width: 0; overflow: hidden; }
.title-label { min-width: 0; max-width: min(280px, 28vw); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 18px; font-weight: 700; flex: 0 1 auto; }
.title-endpoint {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1 1 auto;
  cursor: pointer;
}
.title-endpoint:hover .title-url { color: #1677ff; text-decoration: underline; text-underline-offset: 2px; }
/* 地址带底色块，长地址在标题行内省略，不把「新增用例」按钮挤出去 */
.title-url {
  flex: 1 1 auto;
  min-width: 0;
  max-width: 520px;
  padding: 2px 8px;
  border: 1px solid #e8edf3;
  border-radius: 6px;
  background: #f5f7fa;
  color: #5a6472;
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.title-status-trigger { flex-basis: 60px; }
.cards-grid { display: grid; flex: 1; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); grid-auto-rows: max-content; gap: 16px; min-height: 0; overflow-y: auto; overflow-x: hidden; align-content: start; }
.cards-grid.is-empty { display: flex; align-items: center; justify-content: center; }
.cards-grid.is-empty :deep(.global-empty) { width: 100%; }
.cards-grid.is-empty :deep(.el-empty) { min-height: 0; }
.case-card { border-radius: 10px; cursor: pointer; transition: box-shadow .2s, transform .15s; }
.case-card:hover { transform: translateY(-2px); }
.case-card :deep(.el-card__body) { padding: 18px 20px; }
.card-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.case-card :deep(.priority-tag-high) {
  --el-tag-bg-color: #f5222d;
  --el-tag-border-color: #f5222d;
  --el-tag-text-color: #fff;
}
.case-card :deep(.priority-tag-medium) {
  --el-tag-bg-color: #52c41a;
  --el-tag-border-color: #52c41a;
  --el-tag-text-color: #fff;
}
.case-card :deep(.priority-tag-low) {
  --el-tag-bg-color: #1677ff;
  --el-tag-border-color: #1677ff;
  --el-tag-text-color: #fff;
}
.case-card :deep(.priority-tag-high),
.case-card :deep(.priority-tag-medium),
.case-card :deep(.priority-tag-low) {
  box-sizing: border-box;
  min-width: 38px;
  justify-content: center;
  border-radius: 3px;
  font-weight: 700;
}
.case-card.is-pending { background: linear-gradient(135deg, #fffaf0 0%, #fff3d9 100%); }
.case-card.is-confirmed { background: linear-gradient(135deg, #f5fcf1 0%, #e4f4dc 100%); }
.card-name { font-weight: 700; font-size: 16px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.method-badge { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 3px; color: #fff; flex-shrink: 0; }
.m-get { background: #52c41a; } .m-post { background: #1677ff; } .m-put { background: #fa8c16; }
.m-delete { background: #f5222d; } .m-patch { background: #722ed1; }
.card-url { margin-bottom: 8px; font-size: 13px; color: #555; font-family: monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-desc { font-size: 13px; color: #999; margin-bottom: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-height: 18px; }
.card-meta { font-size: 13px; color: #909399; margin-bottom: 12px; display: flex; align-items: center; gap: 4px; }
.assertion-badge-icon {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex: 0 0 16px;
  color: #929aa3;
}
.assertion-badge-icon::before,
.assertion-badge-icon::after {
  content: '';
  position: absolute;
  inset: 1px;
  clip-path: polygon(50% 0%, 65% 7%, 82% 4%, 89% 20%, 100% 33%, 94% 50%, 100% 66%, 88% 80%, 82% 96%, 65% 92%, 50% 100%, 35% 92%, 18% 96%, 11% 80%, 0% 66%, 6% 50%, 0% 33%, 11% 20%, 18% 4%, 35% 7%);
}
.assertion-badge-icon::before { background: currentColor; }
.assertion-badge-icon::after { inset: 3px; background: rgba(255, 255, 255, 0.72); }
.assertion-badge-icon :deep(.el-icon) { position: relative; z-index: 1; }
.card-creator { display: flex; align-items: center; gap: 7px; min-width: 0; margin-bottom: 10px; font-size: 12px; color: #606266; }
.card-creator-avatar { width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center; flex: 0 0 22px; overflow: hidden; border-radius: 50%; color: #fff; font-size: 11px; font-weight: 600; }
.card-creator-avatar img { width: 100%; height: 100%; object-fit: cover; }
.card-creator-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-times { display: grid; gap: 4px; margin-bottom: 12px; font-size: 12px; color: #909399; line-height: 1.4; }
.card-actions { display: flex; gap: 4px; padding-top: 12px; flex-wrap: wrap; }
.card-actions .el-button { padding: 5px 12px; font-size: 12px; }

@media (max-width: 1440px) {
  .cases-main { padding: 14px 16px; }
  .cards-grid { grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 12px; }
}

.kv-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.case-edit-dialog :deep(.el-tabs__content) { max-height: 55vh; overflow-y: auto; }
.iface-dialog :deep(.el-tabs__content) { max-height: 50vh; overflow-y: auto; }
.interface-workflow-info { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; color: #606266; font-size: 13px; }
.interface-workflow-info span:first-child { color: #303133; font-weight: 600; }

</style>

<style>
/* 全局最大化样式（dialog 被 teleport 到 body，scoped 样式不生效） */
.el-dialog.case-edit-dialog.smart-dialog.maximized,
.el-dialog.iface-dialog.smart-dialog.maximized {
  width: 100vw !important;
  max-width: 100vw !important;
  height: 100vh !important;
  max-height: 100vh !important;
  margin: 0 !important;
  border-radius: 0 !important;
  display: flex !important;
  flex-direction: column !important;
}
.el-dialog.case-edit-dialog.smart-dialog.maximized .el-dialog__body,
.el-dialog.iface-dialog.smart-dialog.maximized .el-dialog__body {
  flex: 1 !important;
  max-height: none !important;
  min-height: 0 !important;
  overflow-y: auto !important;
}
</style>
