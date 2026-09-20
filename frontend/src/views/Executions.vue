<template>
  <div class="executions-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>执行集管理</h3>
        </div>
      </template>
      <div class="list-toolbar-frame">
        <el-form :inline="true" @submit.prevent>
          <el-form-item label="执行集名称">
            <el-input v-model="searchName" placeholder="模糊搜索" clearable style="width:180px" @keyup.enter="page=1;loadExecutions()" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="page=1;loadExecutions()">查询</el-button>
            <el-button @click="searchName='';page=1;loadExecutions()">重置</el-button>
          </el-form-item>
        </el-form>
        <div class="list-toolbar-actions">
          <el-button type="primary" :icon="Plus" @click="handleCreate">新建执行集</el-button>
          <el-button type="default" @click="handleSelectAll">全选</el-button>
          <el-button type="danger" @click="handleBatchDelete">批量删除</el-button>
        </div>
      </div>

      <el-table :data="executionList" v-loading="loading" stripe style="width:100%" :header-cell-style="{whiteSpace:'nowrap'}" @selection-change="handleSelectionChange" ref="execTableRef">
        <template #empty><GlobalEmpty text="暂无数据" /></template>
        <el-table-column type="selection" width="45" />
        <el-table-column label="执行集名称" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="handleEdit(row)">{{ row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="参数集" min-width="90" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link v-if="row.parameter_set_id" type="warning" underline="never" @click="openParamSet(row.parameter_set_id)">
              {{ row.parameter_set_name || paramSets.find(p => p.id === row.parameter_set_id)?.name || '#' + row.parameter_set_id }}
            </el-link>
            <span v-else style="color:#c0c4cc">未选择</span>
          </template>
        </el-table-column>
        <el-table-column label="用例数" width="78" align="center">
          <template #default="{ row }">
            <el-link type="primary" underline="never" @click="handleEdit(row)">{{ row.case_count ?? 0 }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="上次执行" min-width="145" align="center">
          <template #default="{ row }">
            <template v-if="row.last_status">
              <div class="last-run-stats">
                <span class="stat-passed">{{ row.last_passed ?? 0 }}</span>
                <span style="margin:0 4px;color:#c0c4cc">/</span>
                <span class="stat-failed" v-if="row.last_failed">{{ row.last_failed }}</span>
                <span v-else style="color:#c0c4cc">0</span>
                <el-tag :type="row.last_status === 'success' ? 'success' : 'danger'" size="small" effect="plain" style="margin-left:8px">
                  {{ row.last_status === 'success' ? '通过' : '失败' }}
                </el-tag>
              </div>
            </template>
            <span v-else class="text-muted">未执行</span>
          </template>
        </el-table-column>
        <el-table-column label="触发方式" min-width="230" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tooltip :content="getTriggerText(row)" placement="top" :show-after="400">
              <el-tag :type="getTriggerTagType(row)" size="small" class="trigger-tag" @click="handleEdit(row)">
                {{ getTriggerText(row) }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="执行方式" min-width="96" class-name="nowrap-cell" header-class-name="nowrap-cell">
          <template #default="{ row }">
            <el-tag :type="row.execution_mode === 'parallel' ? 'warning' : 'info'" size="small" style="cursor:pointer" @click="handleEdit(row)">{{ row.execution_mode === 'parallel' ? '并行' : '串行' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="150" class-name="nowrap-cell" header-class-name="nowrap-cell">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <div style="white-space:nowrap">
              <el-button link type="success" size="small" @click="handleExecute(row)" :loading="executingId === row.id" :disabled="executingId === row.id || Number(row.case_count ?? 0) === 0">执行</el-button>
              <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-pagination
      v-model:current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="total, sizes, prev, pager, next"
      :page-sizes="[10, 50, 100]"
      @current-change="onPageChange"
      @size-change="onPageSizeChange"
      style="margin-top:20px;justify-content:flex-end;display:flex"
    />

    <!-- 执行集编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="min(800px, calc(100vw - 48px))" @close="resetForm" :close-on-click-modal="false">
      <el-form :model="form" ref="formRef" label-width="110px" :rules="execRules" v-loading="editLoading" class="exec-form">
        <el-form-item label="名称" prop="name" required>
          <el-input v-model="form.name" placeholder="如：回归测试包" size="large" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="可选" size="large" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="运行环境" prop="environment_id" required>
          <el-select v-model="form.environment_id" placeholder="选择环境" style="width:100%" size="large">
            <el-option v-for="env in environments" :key="env.id" :label="env.name + ' (' + env.base_url + ')'" :value="env.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="参数集">
          <el-select v-model="form.parameter_set_id" placeholder="可选" style="width:100%" size="large" clearable>
            <el-option v-for="ps in paramSets" :key="ps.id" :label="ps.name" :value="ps.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="选择用例" prop="selectedCases" :required="!form.id">
          <div style="display:flex;gap:10px;align-items:center">
            <el-button @click="openCaseSelectDialog">选择用例</el-button>
            <span style="color:#909399;font-size:13px">已选 {{ form.selectedCases.length }} 个用例</span>
          </div>
        </el-form-item>

        <!-- <el-divider content-position="left">执行策略</el-divider> -->

        <el-form-item label="失败重试次数">
          <el-input-number v-model="form.retry_count" :min="0" :max="3" />
        </el-form-item>
        <el-form-item label="执行方式">
          <el-radio-group v-model="form.execution_mode">
            <el-radio value="serial">串行</el-radio>
            <el-radio value="parallel">并行</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="是否自动执行">
          <el-radio-group v-model="form.auto_execute">
            <el-radio :value="false">否</el-radio>
            <el-radio :value="true">是</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="form.auto_execute">
          <el-form-item label="执行策略" required>
            <el-alert
              v-if="form.original_schedule_policy_id && form.original_schedule_policy_enabled === false"
              title="当前引用的执行策略已停用，请选择其他启用策略，或改为手动执行。"
              type="warning"
              :closable="false"
              style="margin-bottom:8px"
            />
            <div class="schedule-policy-picker">
              <el-button class="schedule-policy-picker__button" @click="openSchedulePolicyDialog">选择执行策略</el-button>
              <span v-if="selectedSchedulePolicy" class="schedule-policy-picker__selected">
                <span class="schedule-policy-picker__selected-name">{{ selectedSchedulePolicy.name }}</span>
                <el-tag :type="selectedSchedulePolicy.is_enabled ? 'success' : 'info'" size="small">
                  {{ selectedSchedulePolicy.is_enabled ? '启用' : '已停用' }}
                </el-tag>
              </span>
              <span v-else class="text-muted">尚未选择</span>
              <el-button v-if="form.schedule_policy_id" link type="info" @click="clearSchedulePolicy">清除</el-button>
            </div>
          </el-form-item>
        </template>

        <!-- <el-divider content-position="left">通知配置</el-divider> -->

        <el-form-item label="消息发送群" :required="form.auto_execute">
          <el-select v-model="form.notification_config_ids" placeholder="选择通知群" style="width:100%" size="large" multiple clearable>
            <el-option
              v-for="nc in notificationConfigs"
              :key="nc.id"
              :label="nc.group_name || nc.name || nc.channel_type || ('消息群 #' + nc.id)"
              :value="nc.id"
              :disabled="nc.is_active === false"
            />
          </el-select>
          <div v-if="notificationConfigs.length === 0" class="form-hint">暂无消息通知配置，请联系平台管理员</div>
          <div v-else-if="form.auto_execute" class="form-hint">自动执行时至少选择一个有效消息群</div>
        </el-form-item>
        <el-form-item label="消息模板" :required="form.auto_execute">
          <el-select v-model="form.message_template_id" placeholder="选择消息模板" style="width:100%" size="large" clearable>
            <el-option v-for="tpl in messageTemplates" :key="tpl.id" :label="tpl.name" :value="tpl.id" :disabled="tpl.is_active === false" />
          </el-select>
          <div v-if="form.auto_execute" class="form-hint">自动执行时必须选择消息模板</div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- 执行策略选择弹窗：搜索和分页放在选择列表内部 -->
    <el-dialog
      v-model="schedulePolicyDialogVisible"
      title="选择执行策略"
      width="min(760px, calc(100vw - 48px))"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
    >
      <div class="schedule-policy-dialog__toolbar">
        <el-input
          v-model="schedulePolicySearch.name"
          placeholder="按策略名称搜索"
          clearable
          @keyup.enter="searchSchedulePolicies(schedulePolicySearch.name)"
          @clear="searchSchedulePolicies('')"
        />
        <el-button type="primary" @click="searchSchedulePolicies(schedulePolicySearch.name)">查询</el-button>
      </div>
      <div v-loading="schedulePolicyLoading" class="schedule-policy-dialog__body">
        <el-table
          v-if="schedulePolicies.length > 0"
          :data="schedulePolicies"
          row-key="id"
          highlight-current-row
          @row-click="selectSchedulePolicyRow"
        >
          <el-table-column width="58" align="center">
            <template #default="{ row }">
              <el-radio v-model="schedulePolicyDraftId" :value="row.id" :disabled="!row.is_enabled" />
            </template>
          </el-table-column>
          <el-table-column prop="name" label="策略名称" min-width="180" show-overflow-tooltip />
          <el-table-column prop="schedule_text" label="执行规则" min-width="230" show-overflow-tooltip>
            <template #default="{ row }">{{ row.schedule_text || '-' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">{{ row.is_enabled ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <GlobalEmpty
          v-else
          :text="schedulePolicyTotal > 0 ? '暂无可用执行策略，请管理员先启用执行策略' : '暂无匹配的执行策略'"
        />
        <div v-if="schedulePolicyTotal > 0" class="schedule-policy-dialog__pagination">
          <el-pagination
            v-model:current-page="schedulePolicySearch.page"
            v-model:page-size="schedulePolicySearch.page_size"
            small
            layout="total, sizes, prev, pager, next"
            :page-sizes="[10, 50, 100]"
            :total="schedulePolicyTotal"
            @current-change="loadSchedulePolicies"
            @size-change="changeSchedulePolicyPageSize"
          />
        </div>
      </div>
      <template #footer>
        <el-button @click="schedulePolicyDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!schedulePolicyDraftId" @click="confirmSchedulePolicySelection">确定</el-button>
      </template>
    </el-dialog>

    <ExecutionCaseSelectDialog
      v-model="caseSelectDialogVisible"
      :tree-data="treeData"
      :filtered-tree-data="filteredTreeData"
      v-model:search-keyword="caseSearchKeyword"
      v-model:interface-status="interfaceStatusFilter"
      v-model:case-status="caseStatusFilter"
      :tree-loading="treeLoading"
      :tree-key="treeKey"
      :checked-case-ids="checkedCaseIds"
      :default-checked-keys="defaultCheckedKeys"
      :default-expanded-keys="defaultExpandedKeys"
      :allow-empty="Boolean(form.id)"
      @filter="handleCaseTreeFilter"
      @check="checkedCaseIds = $event"
      @confirm="confirmCaseSelection"
      @view-interface="openInterfaceDetail"
      @view-case="openCaseDetail"
    />

    <InterfaceEditDialog
      v-model="interfaceDetailVisible"
      title="编辑接口"
      :model="interfaceDetail || {}"
      :collection-tree="interfaceCollectionTree"
      :environment-services="environmentServices"
      :show-debug="false"
      :show-case-management="false"
      :saving="interfaceDetailSaving"
      @save="handleInterfaceDetailSave"
    />

    <TestCaseEditDialog
      v-model="caseDetailVisible"
      title="编辑用例"
      :model="caseDetail"
      :readonly="false"
      :show-run="false"
      :active-tab="caseDetailTab"
      :show-info="true"
      :saving="caseDetailSaving"
      @save="handleCaseDetailSave"
      @update:active-tab="caseDetailTab = $event"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { formatBeijingMinute } from '@/utils/beijingTime'
import { confirmDelete } from '@/utils/confirmDelete'
import { getExecutionSets, createExecutionSet, updateExecutionSet, deleteExecutionSet, runExecutionSet, getExecutionSet, batchDeleteExecutionSets } from '@/api/executions'
import { getEnvironments } from '@/api/environment'
import { getParameterSets } from '@/api/parameterSet'
import { getCasesByInterface, getTestCase, updateTestCase } from '@/api/testcases'
import { getInterface, updateInterface } from '@/api/interfaces'
import { getCollectionTree } from '@/api/collections'
import { getSchedulePolicies } from '@/api/schedulePolicies'
import { getMessageChannelOptions, getMessageTemplateOptions } from '@/api/messageConfig'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import ExecutionCaseSelectDialog from '@/components/ExecutionCaseSelectDialog.vue'
import InterfaceEditDialog from '@/components/InterfaceEditDialog.vue'
import TestCaseEditDialog from '@/components/TestCaseEditDialog.vue'
import { getEnvironmentServices } from '@/utils/serviceEnvironment'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => route.params.id)
const selectedEnvironment = inject('selectedEnvironment', computed(() => null))
const environmentServices = computed(() => getEnvironmentServices(selectedEnvironment.value))

const execTableRef = ref(null)
const selectedExecSets = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const executionList = ref([])
const searchName = ref('')
const dialogVisible = ref(false)
const dialogTitle = ref('')
const formRef = ref(null)
const submitLoading = ref(false)
const editLoading = ref(false)
const environments = ref([])
const paramSets = ref([])
const notificationConfigs = ref([])
const messageTemplates = ref([])
const schedulePolicies = ref([])
const schedulePolicyTotal = ref(0)
const schedulePolicyEnabledTotal = ref(0)
const schedulePolicyLoading = ref(false)
const schedulePolicyDialogVisible = ref(false)
const executingId = ref(null)
const schedulePolicyDraftId = ref(null)
const selectedSchedulePolicy = ref(null)
const schedulePolicySearch = reactive({ name: '', page: 1, page_size: 10 })

const normalizeSchedulePolicy = (policy = {}) => ({
  ...policy,
  id: policy.id,
  name: policy.name || `策略 #${policy.id}`,
  schedule_text: policy.schedule_text || policy.schedule_policy_text || '',
  is_enabled: policy.is_enabled ?? policy.schedule_policy_enabled !== false,
})

const readNotificationChannelIds = (config = {}) => [...([config.channel_ids, config.notification_config_ids, config.message_channel_ids].find(value => Array.isArray(value) && value.length > 0) || (config.notification_config_id ? [config.notification_config_id] : []))]

const form = reactive({
  id: null, name: '', description: '', environment_id: null, parameter_set_id: null,
  selectedCases: [], retry_count: 0, auto_execute: false, cron_expression: '',
  execution_mode: 'serial', notification_config_ids: [], message_template_id: null, schedule_policy_id: null, original_schedule_policy_id: null, original_schedule_policy_enabled: null,
})

// 选用例（树形）
const caseSelectDialogVisible = ref(false)
const treeData = ref([])
const filteredTreeData = ref([])
const interfaceCollectionTree = ref([])
const caseSearchKeyword = ref('')
const interfaceStatusFilter = ref('')
const caseStatusFilter = ref('')
const treeLoading = ref(false)
const treeKey = ref(0)
const checkedCaseIds = ref([])
const defaultCheckedKeys = ref([])
const defaultExpandedKeys = ref([])
const interfaceDetailVisible = ref(false)
const interfaceDetail = ref(null)
const interfaceDetailSaving = ref(false)
const caseDetailVisible = ref(false)
const caseDetailTab = ref('query')
const caseDetailSaving = ref(false)
const caseDetailInterfaceId = ref(null)
const caseDetail = ref({
  id: null,
  interface_id: null,
  name: '',
  description: '',
  priority: 'high',
  confirm_status: 'pending',
  confirm_status_label: '待确认',
  method: 'GET',
  url: '',
  headers: [],
  query_params: [],
  path_params: [],
  body_type: '',
  body_content: '',
  body_schema_types: {},
  pre_script: '',
  post_script: '',
  script: '',
  assertions: [],
})
const normalizeCaseTree = (nodes = []) => (Array.isArray(nodes) ? nodes : []).map(node => {
  const safeNode = node && typeof node === 'object' ? node : {}
  const rawId = String(safeNode.nodeKey || safeNode.id || '')
  const nodeKey = rawId || `${safeNode.type || 'node'}_${Math.random().toString(36).slice(2)}`
  return {
    ...safeNode,
    nodeKey,
    label: safeNode.label || safeNode.name || '',
    children: normalizeCaseTree(Array.isArray(safeNode.children) ? safeNode.children : []),
  }
})

const collectExpandedKeys = (nodes = []) => {
  const keys = []
  const walk = (items) => {
    items.forEach(item => {
      if (item.children?.length) {
        keys.push(item.nodeKey)
        walk(item.children)
      }
    })
  }
  walk(nodes)
  return keys
}

const filterCaseTree = (nodes, keyword, interfaceStatus = '', caseStatus = '') => {
  return nodes.reduce((result, node) => {
    const selfMatch = !keyword || String(node.label || '').toLowerCase().includes(keyword)
    const interfaceMatches = node.type !== 'interface'
      || !interfaceStatus
      || (interfaceStatus === 'done' ? node.workflow_status === 'done' : node.workflow_status !== 'done')
    const caseMatches = node.type !== 'case'
      || !caseStatus
      || (caseStatus === 'confirmed' ? node.confirm_status === 'confirmed' : node.confirm_status !== 'confirmed')
    if (!interfaceMatches || !caseMatches) return result

    const childKeyword = keyword && selfMatch ? '' : keyword
    const childMatches = filterCaseTree(node.children || [], childKeyword, interfaceStatus, caseStatus)
    if ((node.type === 'case' && selfMatch) || (node.type !== 'case' && (selfMatch || childMatches.length > 0))) {
      if (node.type !== 'case' && !childMatches.length) return result
      result.push({
        ...node,
        children: childMatches,
      })
    }
    return result
  }, [])
}

const filterTreeData = () => {
  const keyword = caseSearchKeyword.value.trim().toLowerCase()
  const interfaceStatus = interfaceStatusFilter.value
  const caseStatus = caseStatusFilter.value
  if (!keyword && !interfaceStatus && !caseStatus) {
    filteredTreeData.value = treeData.value
    return
  }
  filteredTreeData.value = filterCaseTree(treeData.value, keyword, interfaceStatus, caseStatus)
}

const handleCaseTreeFilter = () => {
  filterTreeData()
}

const normalizeCollectionTreeResponse = (value) => {
  if (Array.isArray(value)) return value
  if (Array.isArray(value?.items)) return value.items
  return []
}

const indexCollectionStats = (nodes = [], result = new Map()) => {
  const safeNodes = Array.isArray(nodes) ? nodes : []
  safeNodes.forEach(node => {
    if (!node || typeof node !== 'object') return
    if (node.id !== undefined && node.id !== null) result.set(String(node.id), node)
    indexCollectionStats(Array.isArray(node.children) ? node.children : [], result)
  })
  return result
}

const enrichCaseTreeCollections = (nodes = [], collectionStats = new Map()) => (Array.isArray(nodes) ? nodes : []).map(node => {
  const children = enrichCaseTreeCollections(Array.isArray(node.children) ? node.children : [], collectionStats)
  if (node.type !== 'collection') return { ...node, children }

  const rawId = String(node.id || '').replace(/^col_/, '')
  const statsNode = collectionStats.get(rawId)
  return {
    ...node,
    ...(statsNode ? {
      interface_count: statsNode.interface_count,
      pending_interface_count: statsNode.pending_interface_count,
      done_interface_count: statsNode.done_interface_count,
      interface_status: statsNode.interface_status,
    } : {}),
    children,
  }
})

const execRules = {
  name: [{ required: true, message: '请输入执行集名称', trigger: 'blur' }],
  environment_id: [{ required: true, message: '请配置或者选择运行环境', trigger: 'change' }],
  selectedCases: [{
    validator: (rule, value, callback) => {
      if (form.id || (Array.isArray(value) && value.length > 0)) callback()
      else callback(new Error('请至少选择1个用例'))
    },
    trigger: 'change',
  }],
}

const formatDate = (d) => d ? formatBeijingMinute(d) || '-' : '-'
const getTriggerTagType = (row) => {
  if (!row.schedule_policy_id) return 'info'
  return row.schedule_policy_enabled === false ? 'danger' : 'warning'
}

const getTriggerText = (row) => {
  if (!row.schedule_policy_id) return '手动触发'
  const text = row.schedule_policy_name || row.schedule_policy_text || '自动执行'
  return row.schedule_policy_enabled === false ? `${text}（已停用）` : text
}

const resetForm = () => {
  Object.assign(form, {
    id: null, name: '', description: '', environment_id: selectedEnvironment.value?.id || null,
    parameter_set_id: null,
    selectedCases: [], retry_count: 0, auto_execute: false, cron_expression: '',
    execution_mode: 'serial', notification_config_ids: [], message_template_id: null, schedule_policy_id: null, original_schedule_policy_id: null, original_schedule_policy_enabled: null,
  })
  selectedSchedulePolicy.value = null
  schedulePolicyDraftId.value = null
}

const loadExecutions = async () => {
  loading.value = true
  try {
    const extra = {}
    if (searchName.value) extra.name = searchName.value
    const res = await getExecutionSets(projectId.value, page.value, pageSize.value, extra)
    executionList.value = res.items || res || []
    total.value = res.total || 0
  } catch {}
  finally { loading.value = false }
}

const onPageChange = (val) => {
  page.value = val
  loadExecutions()
}

const onPageSizeChange = (size) => {
  pageSize.value = size
  page.value = 1
  loadExecutions()
}

const loadSchedulePolicies = async () => {
  schedulePolicyLoading.value = true
  try {
    const res = await getSchedulePolicies({
      name: schedulePolicySearch.name.trim() || undefined,
      is_enabled: true,
      page: schedulePolicySearch.page,
      page_size: schedulePolicySearch.page_size,
    })
    schedulePolicies.value = res?.items || []
    schedulePolicyTotal.value = Number(res?.total || schedulePolicies.value.length || 0)
    schedulePolicyEnabledTotal.value = Number(res?.enabled_total ?? schedulePolicies.value.filter(policy => policy.is_enabled).length)
  } catch {
    // 错误已由请求拦截器按后端 message 提示
  } finally {
    schedulePolicyLoading.value = false
  }
}

const keepSelectedSchedulePolicy = (policy) => {
  if (!policy?.id) {
    selectedSchedulePolicy.value = null
    return
  }
  const normalizedPolicy = normalizeSchedulePolicy(policy)
  selectedSchedulePolicy.value = normalizedPolicy
  if (schedulePolicies.value.some(item => item.id === normalizedPolicy.id)) return
  schedulePolicies.value = [normalizedPolicy, ...schedulePolicies.value]
}

const searchSchedulePolicies = (keyword = '') => {
  schedulePolicySearch.name = String(keyword || '').trim()
  schedulePolicySearch.page = 1
  loadSchedulePolicies()
}

const changeSchedulePolicyPageSize = (size) => {
  schedulePolicySearch.page_size = size
  schedulePolicySearch.page = 1
  loadSchedulePolicies()
}

const openSchedulePolicyDialog = () => {
  schedulePolicyDraftId.value = form.schedule_policy_id
  schedulePolicyDialogVisible.value = true
  if (schedulePolicies.value.length === 0 && schedulePolicyTotal.value === 0) loadSchedulePolicies()
}

const selectSchedulePolicyRow = (policy) => {
  if (policy?.is_enabled === false) return
  schedulePolicyDraftId.value = policy.id
}

const confirmSchedulePolicySelection = () => {
  const policy = schedulePolicies.value.find(item => item.id === schedulePolicyDraftId.value) || (
    selectedSchedulePolicy.value?.id === schedulePolicyDraftId.value ? selectedSchedulePolicy.value : null
  )
  if (!policy || policy.is_enabled === false) {
    ElMessage.warning('请选择启用中的执行策略')
    return
  }
  form.schedule_policy_id = policy.id
  selectedSchedulePolicy.value = normalizeSchedulePolicy(policy)
  schedulePolicyDialogVisible.value = false
}

const clearSchedulePolicy = () => {
  form.schedule_policy_id = null
  selectedSchedulePolicy.value = null
  schedulePolicyDraftId.value = null
}

const loadEnvironmentsAndCases = async (selectedChannelIds = [], selectedTemplateId = null) => {
  try {
    schedulePolicySearch.name = ''
    schedulePolicySearch.page = 1
    schedulePolicySearch.page_size = 10
    const [envs, pss, policies, templates, ncs] = await Promise.all([
      getEnvironments(projectId.value),
      getParameterSets(projectId.value),
      getSchedulePolicies({ is_enabled: true, page: 1, page_size: schedulePolicySearch.page_size }),
      getMessageTemplateOptions(selectedTemplateId ? { selected_ids: [selectedTemplateId] } : {}),
      getMessageChannelOptions(selectedChannelIds.length ? { selected_ids: selectedChannelIds } : {}),
    ])
    environments.value = envs?.items || envs || []
    notificationConfigs.value = ncs?.items || ncs || []
    paramSets.value = pss?.items || pss || []
    schedulePolicies.value = policies?.items || []
    schedulePolicyTotal.value = Number(policies?.total || schedulePolicies.value.length || 0)
    schedulePolicyEnabledTotal.value = Number(policies?.enabled_total ?? schedulePolicies.value.filter(policy => policy.is_enabled).length)
    messageTemplates.value = templates?.items || templates || []
  } catch { /* ignore */ }
}

// ---------- 选用例（树形） ----------
const loadCaseTree = async () => {
  treeLoading.value = true
  treeData.value = []
  try {
    const [caseResult, collectionResult] = await Promise.allSettled([
      getCasesByInterface(projectId.value),
      getCollectionTree(projectId.value),
    ])
    if (caseResult.status === 'rejected') throw caseResult.reason

    const collectionTree = collectionResult.status === 'fulfilled'
      ? normalizeCollectionTreeResponse(collectionResult.value)
      : []
    interfaceCollectionTree.value = collectionTree
    const collectionStats = indexCollectionStats(collectionTree)
    const allNodes = enrichCaseTreeCollections(
      normalizeCaseTree(Array.isArray(caseResult.value) ? caseResult.value : []),
      collectionStats,
    )
    treeData.value = allNodes
    filteredTreeData.value = allNodes
    treeKey.value++
    defaultCheckedKeys.value = checkedCaseIds.value.map(id => `case_${id}`)
    defaultExpandedKeys.value = collectExpandedKeys(allNodes)
  } catch { treeData.value = []; filteredTreeData.value = [] }
  finally { treeLoading.value = false }
}

const openCaseSelectDialog = async () => {
  checkedCaseIds.value = [...form.selectedCases]
  caseSearchKeyword.value = ''
  interfaceStatusFilter.value = ''
  caseStatusFilter.value = ''
  caseSelectDialogVisible.value = true
  await loadCaseTree()
}

const readTreeNodeId = (node, prefix) => {
  const raw = String(node?.id || node?.nodeKey || '')
  const marker = `${prefix}_`
  if (!raw.startsWith(marker)) return null
  const id = Number(raw.slice(marker.length))
  return Number.isInteger(id) && id > 0 ? id : null
}

const cloneDetailValue = (value, fallback) => {
  if (value == null) return fallback
  try { return JSON.parse(JSON.stringify(value)) } catch { return fallback }
}

const defaultCaseDetailTab = method => (
  ['POST', 'PUT', 'PATCH'].includes(String(method || '').toUpperCase()) ? 'body' : 'query'
)

const openInterfaceDetail = async node => {
  const interfaceId = readTreeNodeId(node, 'iface')
  if (!interfaceId) return
  try {
    const detail = await getInterface(interfaceId)
    if (!detail) return
    interfaceDetail.value = detail
    interfaceDetailVisible.value = true
  } catch {}
}

const openCaseDetail = async node => {
  const caseId = readTreeNodeId(node, 'case')
  if (!caseId) return
  try {
    const detail = await getTestCase(caseId)
    if (!detail) return
    caseDetail.value = {
      ...detail,
      interface_id: detail.interface_id || null,
      name: detail.name || '',
      description: detail.description || '',
      priority: detail.priority || 'high',
      confirm_status: detail.confirm_status || 'pending',
      confirm_status_label: detail.confirm_status_label || '待确认',
      method: detail.method || 'GET',
      url: detail.url || '',
      headers: cloneDetailValue(detail.headers, []),
      query_params: cloneDetailValue(detail.query_params, []),
      path_params: cloneDetailValue(detail.path_params, []),
      body_type: detail.body_type || '',
      body_content: detail.body_content || '',
      body_schema_types: cloneDetailValue(detail.body_schema_types, {}),
      pre_script: detail.pre_script || '',
      post_script: detail.post_script || '',
      script: detail.script || '',
      assertions: cloneDetailValue(detail.assertions, []),
    }
    caseDetailInterfaceId.value = detail.interface_id || null
    caseDetailTab.value = defaultCaseDetailTab(detail.method)
    caseDetailVisible.value = true
  } catch {}
}

const handleInterfaceDetailSave = async updatedInterface => {
  if (!updatedInterface?.id || interfaceDetailSaving.value) return
  interfaceDetailSaving.value = true
  try {
    const { id, ...payload } = updatedInterface
    await updateInterface(id, payload)
    interfaceDetailVisible.value = false
    if (caseSelectDialogVisible.value) await loadCaseTree()
  } catch {} finally {
    interfaceDetailSaving.value = false
  }
}

const handleCaseDetailSave = async () => {
  const detail = caseDetail.value
  if (!detail?.id || caseDetailSaving.value) return
  if (!String(detail.name || '').trim()) {
    ElMessage.warning('请输入用例名称')
    return
  }
  if (!caseDetailInterfaceId.value) {
    ElMessage.warning('用例所属接口不存在')
    return
  }
  caseDetailSaving.value = true
  try {
    await updateTestCase(detail.id, {
      name: detail.name,
      description: detail.description,
      priority: detail.priority,
      assertions: detail.assertions,
      param_overrides: {
        method: detail.method,
        url: detail.url,
        headers: detail.headers,
        query_params: detail.query_params,
        path_params: detail.path_params,
        body_type: detail.body_type,
        body_content: detail.body_content,
        body_schema_types: detail.body_schema_types,
        pre_script: detail.pre_script,
        post_script: detail.post_script,
      },
      script: detail.script || null,
      confirm_status: detail.confirm_status || 'pending',
    })
    caseDetailVisible.value = false
    if (caseSelectDialogVisible.value) await loadCaseTree()
  } catch {} finally {
    caseDetailSaving.value = false
  }
}

const confirmCaseSelection = (selectedCaseIds = []) => {
  form.selectedCases = Array.isArray(selectedCaseIds) ? selectedCaseIds : []
  if (!form.id && form.selectedCases.length === 0) {
    ElMessage.warning('请至少选择一个用例')
    return
  }
  caseSelectDialogVisible.value = false
}
// ---------- 选用例 End ----------

const handleCreate = async () => {
  resetForm()
  dialogTitle.value = '新建执行集'
  await loadEnvironmentsAndCases()
  if (!form.environment_id && environments.value.length > 0) {
    form.environment_id = environments.value[0]?.id || null
  }
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑执行集'
  editLoading.value = true
  dialogVisible.value = true
  selectedSchedulePolicy.value = null
  schedulePolicyDraftId.value = null

  const nc = row.notification_config || {}
  const selectedChannelIds = readNotificationChannelIds(nc)
  const selectedTemplateId = nc.template_id || nc.message_template_id || null
  Object.assign(form, {
    id: row.id, name: row.name, description: row.description || '',
    environment_id: row.environment_id, parameter_set_id: row.parameter_set_id || null,
    selectedCases: [],
    retry_count: row.retry_count || 0,
    auto_execute: !!row.schedule_policy_id,
    cron_expression: row.cron_expression || '',
    schedule_policy_id: row.schedule_policy_id || null,
    original_schedule_policy_id: row.schedule_policy_id || null,
    original_schedule_policy_enabled: row.schedule_policy_enabled,
    execution_mode: row.execution_mode || 'serial',
    notification_config_ids: selectedChannelIds,
    message_template_id: selectedTemplateId,
  })
  await loadEnvironmentsAndCases(selectedChannelIds, selectedTemplateId)
  keepSelectedSchedulePolicy({
    id: row.schedule_policy_id,
    name: row.schedule_policy_name,
    schedule_policy_text: row.schedule_policy_text,
    schedule_policy_enabled: row.schedule_policy_enabled,
  })

  try {
    const detail = await getExecutionSet(row.id)
    form.selectedCases = (detail.execution_items || []).map(i => i.test_case_id)
  } catch {
    // 错误已由请求拦截器按后端 message 提示
  } finally {
    editLoading.value = false
  }
}

const handleDelete = async (row) => {
  const ok = await confirmDelete(row.name, '执行集')
  if (!ok) return
  await deleteExecutionSet(row.id)
  // Toast由后端返回的message自动显示
  loadExecutions()
}

const handleSelectionChange = (rows) => {
  selectedExecSets.value = rows
}

const handleSelectAll = () => {
  const table = execTableRef.value
  if (!table) return
  if (selectedExecSets.value.length === executionList.value.length) {
    table.clearSelection()
  } else {
    executionList.value.forEach(row => table.toggleRowSelection(row, true))
  }
}

const handleBatchDelete = async () => {
  if (selectedExecSets.value.length === 0) {
    ElMessage.warning('请选择要删除的执行集')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将批量删除 ${selectedExecSets.value.length} 个执行集，此操作不可恢复，确认删除？`,
      '批量删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  try {
    const res = await batchDeleteExecutionSets(selectedExecSets.value.map(r => r.id))
    // Toast由后端返回的message自动显示
    selectedExecSets.value = []
    loadExecutions()
  } catch { /* 错误已在拦截器提示 */ }
}

const handleExecute = (row) => {
  if (executingId.value === row.id) return
  executingId.value = row.id
  ElMessageBox.confirm(
    `确定立即执行"${row.name}"？执行完成后可前往报告页面查看结果。`,
    '执行确认',
    { type: 'info', confirmButtonText: '立即执行', cancelButtonText: '取消' }
  )
    .then(async () => {
      try {
        const res = await runExecutionSet(row.id)
        const reportId = res?.report_id
        ElNotification({
          title: '执行已触发',
          message: reportId
            ? `"${row.name}" 已开始后台执行，报告正在生成，请稍后查看。`
            : `"${row.name}" 已开始后台执行，执行完成后可查看测试报告。`,
          type: 'success',
          duration: 6000,
        })
        setTimeout(() => loadExecutions(), 2000)
      } catch {}
    })
    .catch(() => {})
    .finally(() => { executingId.value = null })
}

const handleSubmit = async () => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch { return }

  if (!form.id && form.selectedCases.length === 0) {
    ElMessage.warning('请至少选择1个用例')
    return
  }
  if (form.id && form.selectedCases.length === 0 && form.auto_execute) {
    ElMessage.warning('清空用例前请先关闭自动执行')
    return
  }
  if (form.auto_execute && !form.schedule_policy_id) {
    ElMessage.warning('请选择执行策略')
    return
  }
  const hasChannels = form.notification_config_ids.length > 0
  const hasTemplate = !!form.message_template_id
  if (hasChannels !== hasTemplate) {
    ElMessage.warning('消息群和消息模板必须同时配置')
    return
  }
  if (form.auto_execute && (!hasChannels || !hasTemplate)) {
    ElMessage.warning('自动执行必须配置消息群和消息模板')
    return
  }

  submitLoading.value = true
  try {
    const data = {
      project_id: parseInt(projectId.value),
      name: form.name,
      description: form.description || null,
      environment_id: form.environment_id,
      parameter_set_id: form.parameter_set_id || null,
      schedule_policy_id: form.auto_execute ? form.schedule_policy_id : null,
      retry_count: form.retry_count,
      cron_expression: null,
      is_enabled: form.auto_execute,
      execution_mode: form.execution_mode || 'serial',
      notification_config: {
        channel_ids: form.notification_config_ids,
        template_id: form.message_template_id || null,
      },
      execution_items: form.selectedCases.map((caseId, i) => ({
        test_case_id: caseId, order: i + 1,
      })),
    }

    if (form.id) {
      await updateExecutionSet(form.id, data)
    } else {
      await createExecutionSet(data)
    }
    dialogVisible.value = false
    loadExecutions()
  } catch {
    // 错误已在请求拦截器中提示，此处忽略
  } finally {
    submitLoading.value = false
  }
}

function openParamSet(psId) {
  router.push(`/project/${projectId.value}/parameter-sets/${psId}`)
}

onMounted(() => { loadExecutions() })
</script>
<style scoped>
.executions-container { height: 100%; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-header h3 { margin: 0; font-size: 20px; font-weight: 600; color: #1a1a1a; }

/* 统一操作列背景色 */
:deep(.el-table__fixed-right) {
  box-shadow: none !important;
}
:deep(.el-table__fixed-right-patch) {
  background: transparent !important;
}
:deep(.el-table__fixed-right .el-table__row) {
  background: inherit !important;
}
:deep(.el-table__fixed-right .el-table__row:hover) {
  background: inherit !important;
}
.cron-text { font-family: monospace; color: #409eff; font-size: 13px; }
.trigger-tag {
  max-width: 100%;
  cursor: pointer;
}
.trigger-tag :deep(.el-tag__content) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nowrap-cell {
  white-space: nowrap !important;
}
.nowrap-cell :deep(.cell) {
  white-space: nowrap !important;
}
.last-run-stats { display: flex; align-items: center; justify-content: center; font-size: 13px; }
.stat-passed { color: #67c23a; font-weight: 600; }
.stat-failed { color: #f56c6c; font-weight: 600; }
.text-muted { color: #c0c4cc; font-size: 13px; }
.action-buttons { display: flex; gap: 4px; align-items: center; justify-content: flex-start; }
.empty-hint { padding: 40px; text-align: center; color: #909399; }
.exec-form :deep(.el-form-item__label) { font-size: 14px; }
.exec-form :deep(.el-input__inner) { font-size: 14px; }
.exec-form :deep(.el-radio__label) { font-size: 14px; }
.schedule-policy-picker { display: flex; width: 100%; gap: 10px; align-items: center; min-width: 0; }
.schedule-policy-picker__button { flex: none; }
.schedule-policy-picker__selected { display: flex; flex: 1; min-width: 0; gap: 8px; align-items: center; overflow: hidden; }
.schedule-policy-picker__selected-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.form-hint { margin-top: 6px; color: #909399; font-size: 13px; line-height: 1.5; }
.schedule-policy-dialog__toolbar { display: flex; gap: 12px; margin-bottom: 16px; }
.schedule-policy-dialog__toolbar .el-input { flex: 1; }
.schedule-policy-dialog__body { min-height: 280px; }
.schedule-policy-dialog__pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
:deep(.el-dialog) { display: flex; flex-direction: column; max-height: calc(100vh - 48px); }
:deep(.el-dialog__body) { flex: 1; min-height: 0; overflow-y: auto; overflow-x: hidden; }

/* 移动端适配 */
@media (max-width: 768px) {
  .el-row { flex-direction: column !important; }
  .el-row .el-col { max-width: 100% !important; flex: 0 0 100% !important; margin-bottom: 12px; }
  .el-dialog { width: 95vw !important; max-width: 95vw !important; }
  .el-table { font-size: 13px; overflow-x: auto; display: block; }
  .el-pagination { justify-content: center !important; }
  .schedule-policy-dialog__toolbar { flex-wrap: wrap; }
  .schedule-policy-dialog__toolbar .el-input { flex-basis: 100%; }
  .schedule-policy-picker { flex-wrap: wrap; }
  .card-header, .list-header, .tree-header { flex-direction: column; align-items: flex-start; gap: 8px; }
  .header-actions, .tree-header-actions { flex-wrap: wrap; }
}
</style>
