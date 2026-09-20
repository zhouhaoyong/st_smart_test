<template>
  <div class="asset-list-page" :class="{ 'tc-page': assetType === 'test_case' }">
    <div v-if="assetType === 'test_case'" class="case-tabs-row">
      <el-tabs v-model="confirmTab" class="confirm-tabs" @tab-change="handleConfirmTab">
        <el-tab-pane label="待确认" name="draft" />
        <el-tab-pane label="已确认" name="confirmed" />
        <el-tab-pane label="全部" name="all" />
      </el-tabs>
    </div>

    <div class="list-toolbar" :class="{ 'compact-toolbar': ['system', 'version', 'legacy_item'].includes(assetType), 'dense-toolbar': ['test_case', 'bug'].includes(assetType), 'all-cases-toolbar': assetType === 'test_case' && confirmTab === 'all' }">
      <el-form :inline="true" :model="filters" @submit.prevent>
        <template v-if="assetType === 'test_case'">
          <el-form-item label="用例标题"><el-input v-model="filters.title" clearable placeholder="请输入用例标题" style="width: 140px" @keyup.enter="handleQuery" /></el-form-item>
          <el-form-item label="优先级"><el-select v-model="filters.priority" clearable placeholder="全部优先级" style="width: 100px"><el-option v-for="item in ['P0', 'P1', 'P2', 'P3']" :key="item" :label="item" :value="item" /></el-select></el-form-item>
          <el-form-item label="类型"><el-select v-model="filters.case_type" clearable placeholder="全部类型" style="width: 110px"><el-option v-for="item in caseTypeOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item>
          <el-form-item label="来源"><el-select v-model="filters.source" clearable placeholder="全部来源" style="width: 125px"><el-option v-for="item in caseSourceOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item v-if="confirmTab === 'all'" label="确认状态"><el-select v-model="filters.confirm_status" clearable placeholder="全部确认状态" style="width: 110px"><el-option label="待确认" value="draft" /><el-option label="已确认" value="confirmed" /></el-select></el-form-item>
          <el-form-item v-if="confirmTab !== 'draft'" label="执行状态"><el-select v-model="filters.status" clearable placeholder="全部执行状态" style="width: 120px"><el-option v-for="item in caseExecutionOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item label="创建时间"><el-date-picker v-model="filters.created_dates" type="daterange" value-format="YYYY-MM-DD" format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 190px" /></el-form-item>
        </template>
        <template v-else-if="assetType === 'system'">
          <el-form-item label="系统名称"><el-input v-model="filters.name" clearable placeholder="请输入系统名称" style="width: 180px" @keyup.enter="handleQuery" /></el-form-item>
          <el-form-item label="系统类型"><el-input v-model="filters.item_type" clearable placeholder="请输入系统类型" style="width: 160px" @keyup.enter="handleQuery" /></el-form-item>
          <el-form-item label="创建时间"><el-date-picker v-model="filters.created_dates" type="daterange" value-format="YYYY-MM-DD" format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 240px" /></el-form-item>
        </template>
        <template v-else-if="assetType === 'version'">
          <el-form-item label="版本号"><el-input v-model="filters.version_no" clearable placeholder="请输入版本号" style="width: 160px" @keyup.enter="handleQuery" /></el-form-item>
          <el-form-item v-if="assetType === 'version'" label="系统"><el-select v-model="filters.system_id" clearable placeholder="全部系统" style="width: 150px" @change="handleSystemChange"><el-option v-for="system in systems" :key="system.id" :label="system.name" :value="system.id" /></el-select></el-form-item>
          <el-form-item label="当前阶段"><el-input v-model="filters.current_stage" clearable placeholder="请输入当前阶段" style="width: 160px" @keyup.enter="handleQuery" /></el-form-item>
          <el-form-item label="创建时间"><el-date-picker v-model="filters.created_dates" type="daterange" value-format="YYYY-MM-DD" format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 240px" /></el-form-item>
        </template>
        <template v-else-if="assetType === 'bug'">
          <el-form-item label="Bug 标题"><el-input v-model="filters.title" clearable placeholder="请输入 Bug 标题" style="width: 180px" @keyup.enter="handleQuery" /></el-form-item>
          <el-form-item label="严重级别"><el-select v-model="filters.severity" clearable placeholder="全部严重级别" style="width: 124px"><el-option label="严重" value="critical" /><el-option label="主要" value="major" /><el-option label="一般" value="minor" /></el-select></el-form-item>
          <el-form-item label="状态"><el-select v-model="filters.status" clearable placeholder="全部状态" style="width: 110px"><el-option v-for="status in config.statuses" :key="status.value" :label="status.label" :value="status.value" /></el-select></el-form-item>
          <el-form-item label="指派人"><el-select v-model="filters.assignee_id" clearable filterable placeholder="全部指派人" style="width: 120px"><el-option v-for="user in users" :key="user.id" :label="user.real_name || user.username" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="创建时间"><el-date-picker v-model="filters.created_dates" type="daterange" value-format="YYYY-MM-DD" format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 240px" /></el-form-item>
        </template>
        <template v-else>
          <el-form-item label="遗留项标题"><el-input v-model="filters.title" clearable placeholder="请输入遗留项标题" style="width: 180px" @keyup.enter="handleQuery" /></el-form-item>
          <el-form-item label="类型"><el-input v-model="filters.item_type" clearable placeholder="请输入类型" style="width: 140px" @keyup.enter="handleQuery" /></el-form-item>
          <el-form-item label="状态"><el-select v-model="filters.status" clearable placeholder="全部状态" style="width: 130px"><el-option v-for="status in config.statuses" :key="status.value" :label="status.label" :value="status.value" /></el-select></el-form-item>
          <el-form-item label="创建时间"><el-date-picker v-model="filters.created_dates" type="daterange" value-format="YYYY-MM-DD" format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 240px" /></el-form-item>
        </template>
        <el-form-item class="query-actions">
          <el-button :type="assetType === 'test_case' ? 'primary' : undefined" @click="handleQuery">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
          <template v-if="assetType === 'test_case'">
            <el-button v-if="confirmTab !== 'confirmed'" type="primary" plain :disabled="!selectedDraftCases.length" @click="batchConfirmCases">{{ withCount('批量确认', selectedDraftCases.length) }}</el-button>
            <el-button v-if="confirmTab === 'draft'" type="primary" plain :disabled="!total" @click="confirmAllCurrentCases">{{ withCount('全部确认', total) }}</el-button>
            <el-button v-if="confirmTab === 'draft'" type="danger" plain :disabled="!selectedRows.length" @click="batchDeleteCases">{{ withCount('批量删除', selectedRows.length) }}</el-button>
            <el-button v-if="confirmTab !== 'draft'" type="warning" plain :disabled="!selectedConfirmedCases.length" @click="batchCancelConfirmCases">{{ withCount('批量取消确认', selectedConfirmedCases.length) }}</el-button>
            <el-button v-if="confirmTab === 'confirmed'" type="primary" plain :disabled="!selectedConfirmedCases.length" @click="openBatchExecution">{{ withCount('批量执行', selectedConfirmedCases.length) }}</el-button>
            <el-button type="danger" plain :disabled="!total" @click="deleteAllCurrentCases">{{ withCount('全部删除', total) }}</el-button>
            <el-button v-if="confirmTab !== 'confirmed'" @click="generateDialog.visible = true">AI 生成用例</el-button>
          </template>
          <el-button v-if="assetType === 'bug'" type="danger" plain :disabled="!selectedRows.length" @click="batchDeleteBugs">{{ withCount('批量删除', selectedRows.length) }}</el-button>
          <el-button v-if="assetType !== 'test_case' || confirmTab !== 'confirmed'" type="primary" @click="openCreate">新建{{ config.name }}</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="table-wrap">
      <el-table v-loading="loading" :data="items" height="100%" row-key="id" class="asset-list-table" :style="{ width: '100%' }" @selection-change="handleSelectionChange">
        <template #empty><GlobalEmpty v-if="!loading" text="暂无数据" /></template>
        <el-table-column v-if="['test_case', 'bug'].includes(assetType)" type="selection" width="46" :selectable="assetType === 'test_case' ? isCaseSelectable : undefined" />
        <el-table-column v-for="column in config.columns" :key="column.prop" :prop="column.prop" :label="column.label" :min-width="column.minWidth" :width="column.width" show-overflow-tooltip>
          <template #default="{ row }">
            <el-button v-if="isEditablePrimaryColumn(column)" link type="primary" class="editable-primary-field" :title="formatCell(row, column)" @click="openEdit(row)">{{ formatCell(row, column) }}</el-button>
            <el-tag v-else-if="column.format === 'execution_tag'" size="small" effect="light" :type="executionTagType(row.execution_status)">{{ formatCell(row, column) }}</el-tag>
            <template v-else>{{ formatCell(row, column) }}</template>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="operationColumnWidth" fixed="right" align="center">
          <template #default="{ row }">
            <div class="table-actions">
              <template v-if="assetType === 'test_case'">
                <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
                <el-button v-if="confirmTab === 'draft'" link type="primary" @click="confirmCase(row)">确认</el-button>
                <el-button v-if="confirmTab === 'confirmed'" link type="primary" @click="openSingleExecution(row)">执行</el-button>
                <el-button link type="danger" @click="remove(row)">删除</el-button>
              </template>
              <el-button v-if="assetType === 'bug' && row.status !== 'legacy'" link type="primary" @click="openAssign(row)">指派</el-button>
              <el-button v-if="assetType === 'bug' && row.status === 'pending'" link type="warning" @click="openResolve(row)">解决</el-button>
              <el-button v-if="assetType === 'bug' && row.status === 'resolved'" link type="success" @click="openVerify(row)">验证</el-button>
             <el-button v-if="assetType === 'bug'" link @click="openTransitions(row)">流转</el-button>
              <el-button v-if="assetType === 'bug' && row.status !== 'legacy'" link type="warning" @click="transferToLegacy(row)">转为遗留项</el-button>
              <template v-if="assetType !== 'test_case'"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-button link type="danger" @click="remove(row)">删除</el-button></template>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="list-pagination"><el-pagination v-model:current-page="filters.page" v-model:page-size="filters.page_size" :total="total" :page-sizes="[10, 50, 100]" layout="total, sizes, prev, pager, next" @current-change="loadAssets" @size-change="handleSizeChange" /></div>
    <WorkbenchAssetFormDialog v-model="formDialog.visible" :project-id="projectId" :asset-type="assetType" :item="formDialog.item" @saved="handleSaved" />
    <TestCaseGenerateDialog v-if="assetType === 'test_case'" v-model="generateDialog.visible" :project-id="projectId" @saved="handleSaved" />
    <WorkbenchExecutionDialog
      v-if="assetType === 'test_case'"
      :dialog="singleExecutionDialog"
      :form="singleExecutionForm"
      :test-case="singleExecutionDialog.testCase"
      :history="executionHistory"
      :correcting-id="correctingExecutionId"
      :mode="singleExecutionDialog.mode"
      :project-id="projectId"
      @load-history="loadExecutionHistory"
      @correct="correctExecution"
      @cancel-correct="cancelCorrectExecution"
      @submit="submitSingleExecution"
      @saved="handleSaved"
    />
    <WorkbenchBugDialog
      v-if="assetType === 'test_case'"
      :dialog="submitBugDialog"
      :form="submitBugForm"
      :test-case="submitBugDialog.testCase"
      :project-id="projectId"
      @submit="submitExecutionBug"
    />
    <el-dialog v-model="batchExecutionDialog.visible" title="批量执行" width="460px" append-to-body>
      <div class="batch-execution-content">
        <p class="batch-execution-hint">将为已选 {{ selectedConfirmedCases.length }} 条已确认用例记录相同的执行结果。</p>
        <el-radio-group v-model="batchExecutionDialog.result" class="batch-execution-options">
          <el-radio-button label="passed">通过</el-radio-button>
          <el-radio-button label="failed">失败</el-radio-button>
          <el-radio-button label="not_executed">未执行</el-radio-button>
        </el-radio-group>
      </div>
      <template #footer><div class="batch-execution-actions"><el-button @click="batchExecutionDialog.visible = false">取消</el-button><el-button type="primary" :loading="batchExecutionDialog.loading" @click="submitBatchExecution">确认执行</el-button></div></template>
    </el-dialog>
    <!-- Bug 指派 -->
    <el-dialog v-model="assignDialog.visible" title="指派" width="460px" append-to-body>
      <el-form label-width="88px">
        <el-form-item label="Bug"><span>{{ assignDialog.bug?.title }}</span></el-form-item>
        <el-form-item label="指派人" required>
          <el-select v-model="assignDialog.assignee_id" filterable placeholder="请选择指派人" style="width: 100%">
            <el-option v-for="user in users" :key="user.id" :label="user.real_name || user.username" :value="user.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="assignDialog.remark" type="textarea" :rows="2" placeholder="选填" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="assignDialog.visible = false">取消</el-button><el-button type="primary" :loading="assignDialog.loading" @click="submitAssign">确认指派</el-button></template>
    </el-dialog>

    <!-- Bug 解决 -->
    <el-dialog v-model="resolveDialog.visible" title="解决 Bug" width="480px" append-to-body>
      <el-form label-width="88px">
        <el-form-item label="Bug"><span>{{ resolveDialog.bug?.title }}</span></el-form-item>
        <el-form-item label="解决方案" required><el-input v-model="resolveDialog.resolution" type="textarea" :rows="4" placeholder="请描述修复方案 / 处理说明" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="resolveDialog.visible = false">取消</el-button><el-button type="primary" :loading="resolveDialog.loading" @click="submitResolve">标记已解决</el-button></template>
    </el-dialog>

    <!-- Bug 验证 -->
    <el-dialog v-model="verifyDialog.visible" title="验证 Bug" width="480px" append-to-body>
      <el-form label-width="88px">
        <el-form-item label="Bug"><span>{{ verifyDialog.bug?.title }}</span></el-form-item>
        <el-form-item label="验证结果">
          <el-radio-group v-model="verifyDialog.result">
            <el-radio label="pass">通过（关闭）</el-radio>
            <el-radio label="fail">不通过（退回）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="验证结论"><el-input v-model="verifyDialog.verify_conclusion" type="textarea" :rows="3" placeholder="选填" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="verifyDialog.visible = false">取消</el-button><el-button type="primary" :loading="verifyDialog.loading" @click="submitVerify">提交验证</el-button></template>
    </el-dialog>

    <!-- Bug 流转记录 -->
    <el-dialog v-model="transitionDialog.visible" title="流转记录" width="520px" append-to-body>
      <div v-loading="transitionDialog.loading" style="min-height: 80px">
        <el-empty v-if="!transitionDialog.loading && !transitionDialog.records.length" description="暂无流转记录" :image-size="60" />
        <el-timeline v-else>
          <el-timeline-item v-for="record in transitionDialog.records" :key="record.id" :timestamp="formatBeijingTime(record.operated_at) || '—'">
            <strong>{{ actionLabels[record.action] || record.action }}</strong>
            <span v-if="record.from_status || record.to_status">：{{ statusText(record.from_status) }} → {{ statusText(record.to_status) }}</span>
            <div v-if="record.remark" class="transition-remark">{{ record.remark }}</div>
          </el-timeline-item>
        </el-timeline>
      </div>
    </el-dialog>

  </div>
</template>

<script setup>
import { computed, inject, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'
import {
  deleteWorkbenchBug, batchDeleteWorkbenchBugs, deleteWorkbenchLegacyItem, deleteWorkbenchRequirement, deleteWorkbenchSystem, deleteWorkbenchTestCase, deleteWorkbenchVersion,
  getWorkbenchProjectDashboardAssets,
  confirmWorkbenchTestCase, batchConfirmWorkbenchTestCases, batchCancelConfirmWorkbenchTestCases, batchDeleteWorkbenchTestCases, batchExecuteWorkbenchTestCases,
  createWorkbenchExecution, getWorkbenchTestCaseExecutions, correctWorkbenchExecution, createWorkbenchBug,
  assignWorkbenchBug, resolveWorkbenchBug, verifyWorkbenchBug, transferWorkbenchBugToLegacy, getWorkbenchBugTransitions, getWorkbenchProjectUsers,
} from '@/api/testWorkbench'
import WorkbenchAssetFormDialog from '@/views/test-workbench/components/WorkbenchAssetFormDialog.vue'
import TestCaseGenerateDialog from '@/views/test-workbench/components/TestCaseGenerateDialog.vue'
import WorkbenchExecutionDialog from '@/views/test-workbench/components/WorkbenchExecutionDialog.vue'
import WorkbenchBugDialog from '@/views/test-workbench/components/WorkbenchBugDialog.vue'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import { formatBeijingTime } from '@/utils/beijingTime'

const props = defineProps({ assetType: { type: String, required: true } })
const route = useRoute()
const projectId = computed(() => Number(route.params.id))
const { assetListRefreshKey, refreshDashboardStats, scope, scopeRefreshKey, selectSystem, selectVersion, selectAllScope, refreshScopeOptions } = inject('workbenchContext')
const configs = {
  system: { name: '系统', columns: [{ prop: 'name', label: '系统名称', width: 220 }, { prop: 'type', label: '系统类型', width: 150 }, { prop: 'description', label: '描述', minWidth: 160 }, { prop: 'created_at', label: '创建时间', width: 170, format: 'time' }, { prop: 'creator_name', label: '创建人', width: 100 }] },
  version: { name: '版本', columns: [{ prop: 'version_no', label: '版本号', width: 140 }, { prop: 'system_name', label: '所属系统', width: 130 }, { prop: 'current_stage', label: '当前阶段', width: 120 }, { prop: 'plan_release_date', label: '计划发布日期', width: 140 }, { prop: 'actual_release_date', label: '实际发布日期', width: 140 }, { prop: 'description', label: '描述', minWidth: 140 }, { prop: 'created_at', label: '创建时间', width: 170, format: 'time' }, { prop: 'creator_name', label: '创建人', width: 100 }] },
  requirement: { name: '需求', statuses: [{ label: '待确认', value: 'draft' }, { label: '已确认', value: 'confirmed' }], columns: [{ prop: 'title', label: '需求标题', minWidth: 220 }, { prop: 'system_name', label: '所属系统', width: 130 }, { prop: 'version_no', label: '所属版本', width: 130 }, { prop: 'confirm_status', label: '状态', width: 110, format: 'status' }, { prop: 'updated_at', label: '更新时间', width: 170, format: 'time' }] },
  test_case: { name: '测试用例', statuses: [{ label: '未执行', value: 'not_executed' }, { label: '通过', value: 'passed' }, { label: '失败', value: 'failed' }], columns: [{ prop: 'case_no', label: '用例编号', width: 170 }, { prop: 'title', label: '用例标题', minWidth: 240 }, { prop: 'case_type', label: '用例类型', width: 110 }, { prop: 'priority', label: '优先级', width: 80, format: 'priority' }, { prop: 'system_name', label: '所属系统', width: 120 }, { prop: 'version_no', label: '所属版本', width: 120 }, { prop: 'execution_status', label: '执行状态', width: 100, format: 'execution_tag' }, { prop: 'creator_name', label: '创建人', width: 100 }] },
  bug: { name: 'Bug', statuses: [{ label: '待解决', value: 'pending' }, { label: '已解决', value: 'resolved' }, { label: '已验证关闭', value: 'closed' }, { label: '遗留', value: 'legacy' }], columns: [{ prop: 'title', label: 'Bug 标题', minWidth: 220 }, { prop: 'system_name', label: '所属系统', width: 140 }, { prop: 'version_no', label: '所属版本', width: 130 }, { prop: 'severity', label: '严重级别', width: 100, format: 'severity' }, { prop: 'priority', label: '优先级', width: 90, format: 'priority' }, { prop: 'assignee_id', label: '指派人', width: 130, format: 'assignee' }, { prop: 'status', label: '状态', width: 110, format: 'status' }, { prop: 'creator_name', label: '创建人', width: 120 }] },
  legacy_item: { name: '遗留项', statuses: [{ label: '待处理', value: 'pending' }, { label: '已处理', value: 'done' }], columns: [{ prop: 'title', label: '遗留项标题', minWidth: 220 }, { prop: 'requirement_title', label: '关联需求', width: 200 }, { prop: 'system_name', label: '所属系统', width: 140 }, { prop: 'version_no', label: '所属版本', width: 140 }, { prop: 'planned_version_no', label: '计划处理版本', width: 150 }, { prop: 'type', label: '类型', width: 120 }, { prop: 'status', label: '状态', width: 120, format: 'status' }] },
}
const config = computed(() => configs[props.assetType])
const needsVersion = computed(() => ['requirement', 'test_case', 'bug', 'legacy_item'].includes(props.assetType))
const queryId = value => {
  const id = Number(value)
  return Number.isInteger(id) && id > 0 ? id : undefined
}
const filters = reactive({
  name: '', version_no: '', case_no: '', title: '', source: '', priority: '', case_type: '', item_type: '', current_stage: '', severity: '', assignee_id: undefined, created_dates: [],
  system_id: props.assetType === 'version' ? queryId(route.query.system_id) : undefined,
  version_id: undefined,
  status: '', confirm_status: props.assetType === 'test_case' ? 'draft' : undefined, page: 1, page_size: 10,
})
const confirmTab = ref('draft')
const caseSourceOptions = [
  { label: '人工创建', value: 'manual' },
  { label: 'AI 生成（原始需求）', value: 'ai_requirement' },
  { label: 'AI 生成（AI补全需求）', value: 'ai_completed' },
  { label: 'AI 生成（AI合并需求）', value: 'ai_merged' },
]
// 执行状态只保留未执行、通过、失败三态。
const caseExecutionOptions = [
  { label: '未执行', value: 'not_executed' },
  { label: '通过', value: 'passed' },
  { label: '失败', value: 'failed' },
]
const caseTypeOptions = ['功能测试', '非功能测试']
const selectedRows = ref([])
const generateDialog = reactive({ visible: false })
const systems = ref([])
const versions = ref([])
const items = ref([])
const total = ref(0)
const loading = ref(false)
const formDialog = reactive({ visible: false, item: null })
const batchExecutionDialog = reactive({ visible: false, result: 'passed', loading: false })
const singleExecutionDialog = reactive({ visible: false, testCase: null, loading: false, mode: 'execute' })
const singleExecutionForm = reactive({ result: 'passed', actual_result: '', remark: '', submit_bug: false })
const executionHistory = ref([])
const correctingExecutionId = ref(null)
const submitBugDialog = reactive({ visible: false, testCase: null, execution: null, loading: false })
const submitBugForm = reactive({ title: '', steps: '', actual_result: '', expected_result: '', severity: 'major', priority: 'P2', assignee_id: null })
let requestNo = 0
const filteredVersions = computed(() => filters.system_id ? versions.value.filter((item) => item.system_id === filters.system_id) : versions.value)
const operationColumnWidth = computed(() => props.assetType === 'bug' ? 360 : props.assetType === 'test_case' ? 160 : 140)
const editablePrimaryField = computed(() => ({
  system: 'name',
  version: 'version_no',
  requirement: 'title',
  test_case: 'title',
  bug: 'title',
}[props.assetType]))
const isEditablePrimaryColumn = column => column.prop === editablePrimaryField.value

const users = ref([])
const userName = id => users.value.find((item) => item.id === id)?.real_name || users.value.find((item) => item.id === id)?.username || '—'
const loadUsers = async () => {
  if (props.assetType !== 'bug') return
  try {
    users.value = await getWorkbenchProjectUsers(projectId.value) || []
  } catch (error) { /* 忽略用户加载失败，指派时可重试 */ }
}
const formatCell = (row, column) => {
  const rawValue = row[column.prop]
  const value = props.assetType === 'test_case' && column.prop === 'execution_status' && ['blocked', 'not_tested'].includes(rawValue)
    ? 'not_executed'
    : rawValue
  if (column.format === 'assignee') return value ? userName(value) : '未指派'
  if (column.format === 'severity') return ({ critical: '严重', major: '主要', minor: '一般' }[value] || '一般')
  if (column.format === 'priority') return ['P0', 'P1', 'P2', 'P3'].includes(value) ? value : 'P2'
  if (column.format === 'execution_tag') return ({ passed: '通过', failed: '失败', not_executed: '未执行' }[value] || '未执行')
  if (!value) return '—'
  if (column.format === 'time') return formatBeijingTime(value) || '—'
  if (column.format === 'status') return config.value.statuses?.find((item) => item.value === value)?.label || value
  if (column.format === 'confirm') return value === 'confirmed' ? '已确认' : '待确认'
  if (column.format === 'source') {
    if (value !== 'ai_generated') return '人工创建'
    if (String(row.source_ref || '').startsWith('merged_requirement:')) return 'AI 生成（AI合并需求）'
    if (String(row.source_ref || '').startsWith('completed_requirement:')) return 'AI 生成（AI补全需求）'
    return 'AI 生成（原始需求）'
  }
  return value
}
const withCount = (label, count) => count > 0 ? `${label}（${count}）` : label
const executionTagType = value => ({ passed: 'success', failed: 'danger', not_executed: 'info', blocked: 'info', not_tested: 'info' }[value] || 'info')
const loadAssets = async () => {
  const currentRequestNo = ++requestNo
  loading.value = true
  try {
    const isProjectLevel = ['system', 'version'].includes(props.assetType)
    const { created_dates, ...queryFilters } = filters
    const [created_from, created_to] = created_dates || []
    const result = await getWorkbenchProjectDashboardAssets(projectId.value, {
      asset_type: props.assetType,
      ...queryFilters,
      created_from,
      created_to,
      ...(isProjectLevel ? {} : scope.value),
      system_id: props.assetType === 'system' ? undefined : filters.system_id,
      version_id: isProjectLevel ? undefined : filters.version_id,
    })
    if (currentRequestNo !== requestNo) return
    items.value = result?.items || []
    total.value = result?.total || 0
    systems.value = result?.systems || []
    versions.value = result?.versions || []
  } finally {
    if (currentRequestNo === requestNo) loading.value = false
  }
}
const handleQuery = () => { filters.page = 1; loadAssets() }
const handleSizeChange = () => { filters.page = 1; loadAssets() }
const resetFilters = () => {
  Object.assign(filters, {
    name: '', version_no: '', case_no: '', title: '', source: '', priority: '', case_type: '', item_type: '', current_stage: '', severity: '', assignee_id: undefined, created_dates: [], status: '',
    confirm_status: props.assetType === 'test_case' ? (confirmTab.value === 'all' ? undefined : confirmTab.value) : undefined,
    page: 1, page_size: 10,
  })
  loadAssets()
}
const handleConfirmTab = () => {
  filters.confirm_status = confirmTab.value === 'all' ? undefined : confirmTab.value
  filters.status = ''
  selectedRows.value = []
  filters.page = 1
  loadAssets()
}
const handleSelectionChange = rows => { selectedRows.value = rows }
const selectedDraftCases = computed(() => selectedRows.value.filter(row => row.confirm_status === 'draft'))
const selectedConfirmedCases = computed(() => selectedRows.value.filter(row => row.confirm_status === 'confirmed'))
const isCaseSelectable = row => confirmTab.value === 'all' || row.confirm_status === confirmTab.value
const batchScopePayload = () => ({
  project_id: projectId.value,
  system_ids: scope.value.system_ids ? scope.value.system_ids.split(',').map(Number) : [],
  version_id: scope.value.version_id,
  version_ids: scope.value.version_ids ? scope.value.version_ids.split(',').map(Number) : [],
})
const currentListDeletePayload = () => {
  const [created_from, created_to] = filters.created_dates || []
  return {
    ...batchScopePayload(),
    delete_all_in_scope: true,
    confirm_status: filters.confirm_status || undefined,
    case_no: filters.case_no || undefined,
    title: filters.title || undefined,
    source: filters.source || undefined,
    priority: filters.priority || undefined,
    case_type: filters.case_type || undefined,
    status: filters.status || undefined,
    created_from,
    created_to,
  }
}
const handleSystemChange = () => {
  if (['system', 'version'].includes(props.assetType)) {
    if (filters.version_id && !filteredVersions.value.some(item => item.id === filters.version_id)) filters.version_id = undefined
    return
  }
  if (!filters.system_id) return selectAllScope()
  const system = systems.value.find(item => item.id === filters.system_id)
  if (system) selectSystem(system)
}
const confirmCase = async (row) => {
  await ElMessageBox.confirm('确认测试用例“' + row.title + '”吗？', '确认用例', { type: 'warning' })
  await confirmWorkbenchTestCase(row.id)
  await Promise.all([loadAssets(), refreshDashboardStats?.()])
}
const batchConfirmCases = async () => {
  await ElMessageBox.confirm(`确认所选 ${selectedDraftCases.value.length} 条测试用例吗？`, '批量确认', { type: 'warning' })
  await batchConfirmWorkbenchTestCases({ ...batchScopePayload(), ids: selectedDraftCases.value.map(row => row.id) })
  selectedRows.value = []
  await Promise.all([loadAssets(), refreshDashboardStats?.()])
}
const batchCancelConfirmCases = async () => {
  await ElMessageBox.confirm(`取消确认所选 ${selectedConfirmedCases.value.length} 条测试用例吗？执行记录会保留。`, '批量取消确认', { type: 'warning' })
  await batchCancelConfirmWorkbenchTestCases({ ...batchScopePayload(), ids: selectedConfirmedCases.value.map(row => row.id) })
  selectedRows.value = []
  await Promise.all([loadAssets(), refreshDashboardStats?.()])
}
const confirmAllCurrentCases = async () => {
  await ElMessageBox.confirm(`确认当前列表中符合筛选条件的全部 ${total.value} 条待确认测试用例吗？确认范围以当前项目、系统、版本和查询条件为准。`, '全部确认', { type: 'warning' })
  const [created_from, created_to] = filters.created_dates || []
  await batchConfirmWorkbenchTestCases({
    ...batchScopePayload(),
    confirm_all_in_scope: true,
    confirm_status: 'draft',
    case_no: filters.case_no || undefined,
    title: filters.title || undefined,
    source: filters.source || undefined,
    priority: filters.priority || undefined,
    case_type: filters.case_type || undefined,
    created_from,
    created_to,
  })
  await Promise.all([loadAssets(), refreshDashboardStats?.()])
}
const batchDeleteCases = async () => {
  await ElMessageBox.confirm(`确认删除所选 ${selectedRows.value.length} 条测试用例吗？`, '批量删除', { type: 'warning' })
  await batchDeleteWorkbenchTestCases({ ...batchScopePayload(), ids: selectedRows.value.map(row => row.id) })
  selectedRows.value = []
  await Promise.all([loadAssets(), refreshDashboardStats?.()])
}
const batchDeleteBugs = async () => {
  await ElMessageBox.confirm(`确认删除所选 ${selectedRows.value.length} 条 Bug 吗？`, '批量删除', { type: 'warning' })
  await batchDeleteWorkbenchBugs({ ...batchScopePayload(), ids: selectedRows.value.map(row => row.id) })
  selectedRows.value = []
  await Promise.all([loadAssets(), refreshDashboardStats?.()])
}
const openBatchExecution = () => {
  if (!selectedConfirmedCases.value.length) return
  batchExecutionDialog.result = 'passed'
  batchExecutionDialog.visible = true
}
const openSingleExecution = row => {
  singleExecutionDialog.testCase = row
  singleExecutionDialog.mode = 'execute'
  singleExecutionDialog.visible = true
  correctingExecutionId.value = null
  Object.assign(singleExecutionForm, { result: 'passed', actual_result: '', remark: '', submit_bug: false })
  loadExecutionHistory()
}
// 用例的新建与编辑复用执行弹窗，仅底部按钮与字段是否可编辑不同。
const openCaseForm = row => {
  singleExecutionDialog.testCase = row
  singleExecutionDialog.mode = row ? 'edit' : 'create'
  singleExecutionDialog.visible = true
  correctingExecutionId.value = null
  executionHistory.value = []
  if (row) loadExecutionHistory()
}
const loadExecutionHistory = async () => {
  const testCaseId = singleExecutionDialog.testCase?.id
  if (!testCaseId) return
  executionHistory.value = await getWorkbenchTestCaseExecutions(testCaseId) || []
}
const correctExecution = record => {
  correctingExecutionId.value = record.id
  Object.assign(singleExecutionForm, {
    result: record.result || 'not_executed',
    actual_result: record.actual_result || '',
    remark: record.remark || '',
    submit_bug: false,
  })
}
const cancelCorrectExecution = () => {
  correctingExecutionId.value = null
  Object.assign(singleExecutionForm, { result: 'passed', actual_result: '', remark: '', submit_bug: false })
}
const executionStepsText = testCase => (testCase?.steps_json || testCase?.steps || [])
  .map((step, index) => `${index + 1}. ${typeof step === 'string' ? step : step?.step || step?.description || ''}`.trim())
  .filter(Boolean)
  .join('\n')
const openExecutionBug = execution => {
  const testCase = singleExecutionDialog.testCase
  submitBugDialog.testCase = testCase
  submitBugDialog.execution = execution
  Object.assign(submitBugForm, {
    title: `【执行失败】${testCase?.title || '测试用例'}`,
    steps: executionStepsText(testCase),
    actual_result: execution?.actual_result || singleExecutionForm.actual_result || '',
    expected_result: testCase?.expected_result || '',
    severity: 'major',
    priority: testCase?.priority || 'P2',
    assignee_id: null,
  })
  submitBugDialog.visible = true
}
const submitSingleExecution = async () => {
  const testCase = singleExecutionDialog.testCase
  if (!testCase) return
  singleExecutionDialog.loading = true
  try {
    const payload = {
      result: singleExecutionForm.result,
      actual_result: singleExecutionForm.actual_result || null,
      remark: singleExecutionForm.remark || null,
    }
    const execution = correctingExecutionId.value
      ? await correctWorkbenchExecution(correctingExecutionId.value, payload)
      : await createWorkbenchExecution({ test_case_id: testCase.id, ...payload })
    const shouldSubmitBug = !correctingExecutionId.value && singleExecutionForm.result === 'failed' && singleExecutionForm.submit_bug
    correctingExecutionId.value = null
    // 执行/更正成功后同步弹窗顶部的执行状态（最新一条执行结果即当前用例执行状态）。
    if (testCase) testCase.execution_status = singleExecutionForm.result
    await Promise.all([loadExecutionHistory(), loadAssets(), refreshDashboardStats?.()])
    // 保持用例执行弹窗打开，Bug 表单在其上层弹出。
    if (shouldSubmitBug) openExecutionBug(execution)
  } finally { singleExecutionDialog.loading = false }
}
const submitExecutionBug = async () => {
  const testCase = submitBugDialog.testCase
  if (!testCase || !submitBugForm.title.trim()) { ElMessage.warning('请填写 Bug 标题'); return }
  submitBugDialog.loading = true
  try {
    await createWorkbenchBug({
      project_id: projectId.value,
      system_id: testCase.system_id,
      version_id: testCase.version_id,
      requirement_id: testCase.requirement_id || null,
      merged_requirement_id: testCase.merged_requirement_id || null,
      test_case_id: testCase.id,
      execution_id: submitBugDialog.execution?.id || null,
      title: submitBugForm.title.trim(),
      steps: submitBugForm.steps || null,
      actual_result: submitBugForm.actual_result || null,
      expected_result: submitBugForm.expected_result || null,
      severity: submitBugForm.severity,
      priority: submitBugForm.priority,
      assignee_id: submitBugForm.assignee_id || null,
    })
    submitBugDialog.visible = false
    await Promise.all([loadAssets(), refreshDashboardStats?.()])
  } finally { submitBugDialog.loading = false }
}
const submitBatchExecution = async () => {
  batchExecutionDialog.loading = true
  try {
    await batchExecuteWorkbenchTestCases({ ...batchScopePayload(), ids: selectedConfirmedCases.value.map(row => row.id), result: batchExecutionDialog.result })
    batchExecutionDialog.visible = false
    selectedRows.value = []
    await Promise.all([loadAssets(), refreshDashboardStats?.()])
  } finally { batchExecutionDialog.loading = false }
}
const deleteAllCurrentCases = async () => {
  await ElMessageBox.confirm(`确认删除当前列表中的全部 ${total.value} 条测试用例吗？删除范围以当前项目、系统、版本、页签和查询条件为准。`, '全部删除', { type: 'warning' })
  await batchDeleteWorkbenchTestCases(currentListDeletePayload())
  await Promise.all([loadAssets(), refreshDashboardStats?.()])
}
const handleVersionChange = () => {
  const version = filteredVersions.value.find(item => item.id === filters.version_id)
  if (version) selectVersion(version)
}
const openCreate = () => {
  if (props.assetType === 'test_case') { openCaseForm(null); return }
  formDialog.item = null; formDialog.visible = true
}
const openEdit = (row) => {
  if (props.assetType === 'test_case') { openCaseForm(row); return }
  formDialog.item = row; formDialog.visible = true
}
const remove = async (row) => {
  await ElMessageBox.confirm(`确认删除${config.value.name}“${row.name || row.version_no || row.title}”吗？`, '删除确认', { type: 'warning' })
  const handlers = { system: deleteWorkbenchSystem, version: deleteWorkbenchVersion, requirement: deleteWorkbenchRequirement, test_case: deleteWorkbenchTestCase, bug: deleteWorkbenchBug, legacy_item: deleteWorkbenchLegacyItem }
  await handlers[props.assetType](row.id)
  if (items.value.length === 1 && filters.page > 1) filters.page -= 1
  await Promise.all([
    loadAssets(),
    refreshDashboardStats?.(),
    ['system', 'version'].includes(props.assetType) ? refreshScopeOptions?.() : undefined,
  ])
}
const handleSaved = async () => { await Promise.all([loadAssets(), refreshDashboardStats?.(), refreshScopeOptions?.()]) }

// ---------- Bug 流程 ----------
const assignDialog = reactive({ visible: false, bug: null, assignee_id: null, remark: '', loading: false })
const resolveDialog = reactive({ visible: false, bug: null, resolution: '', loading: false })
const verifyDialog = reactive({ visible: false, bug: null, result: 'pass', verify_conclusion: '', loading: false })
const transitionDialog = reactive({ visible: false, bug: null, records: [], loading: false })
const actionLabels = { submit: '提单', assign: '指派', resolve: '解决', verify: '验证', reactivate: '重新激活', transfer_to_legacy: '转为遗留项' }
const statusText = value => config.value.statuses?.find((item) => item.value === value)?.label || value

const openAssign = row => { assignDialog.bug = row; assignDialog.assignee_id = row.assignee_id || null; assignDialog.remark = ''; assignDialog.visible = true }
const submitAssign = async () => {
  if (!assignDialog.assignee_id) { ElMessage.warning('请选择指派人'); return }
  assignDialog.loading = true
  try {
    await assignWorkbenchBug(assignDialog.bug.id, { assignee_id: assignDialog.assignee_id, remark: assignDialog.remark || null })
    assignDialog.visible = false
    await Promise.all([loadAssets(), refreshDashboardStats?.()])
  } finally { assignDialog.loading = false }
}

const openResolve = row => { resolveDialog.bug = row; resolveDialog.resolution = row.resolution || ''; resolveDialog.visible = true }
const submitResolve = async () => {
  if (!resolveDialog.resolution.trim()) { ElMessage.warning('请填写解决方案'); return }
  resolveDialog.loading = true
  try {
    await resolveWorkbenchBug(resolveDialog.bug.id, { resolution: resolveDialog.resolution.trim() })
    resolveDialog.visible = false
    await Promise.all([loadAssets(), refreshDashboardStats?.()])
  } finally { resolveDialog.loading = false }
}

const openVerify = row => { verifyDialog.bug = row; verifyDialog.result = 'pass'; verifyDialog.verify_conclusion = ''; verifyDialog.visible = true }
const submitVerify = async () => {
  verifyDialog.loading = true
  try {
    await verifyWorkbenchBug(verifyDialog.bug.id, { result: verifyDialog.result, verify_conclusion: verifyDialog.verify_conclusion || null })
    verifyDialog.visible = false
    await Promise.all([loadAssets(), refreshDashboardStats?.()])
  } finally { verifyDialog.loading = false }
}

const transferToLegacy = async row => {
  try {
    await ElMessageBox.confirm(
      `确认将 Bug“${row.title}”转为遗留项吗？原 Bug 会保留流转记录，并从未关闭 Bug 统计中移除。`,
      '转为遗留项',
      { type: 'warning', confirmButtonText: '确认转为遗留项', cancelButtonText: '取消' },
    )
    await transferWorkbenchBugToLegacy(row.id)
    await Promise.all([loadAssets(), refreshDashboardStats?.()])
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') throw error
  }
}

const openTransitions = async row => {
  transitionDialog.bug = row; transitionDialog.records = []; transitionDialog.visible = true; transitionDialog.loading = true
  try {
    const result = await getWorkbenchBugTransitions(row.id)
    transitionDialog.records = result || []
  } finally { transitionDialog.loading = false }
}

loadAssets()
loadUsers()
watch(assetListRefreshKey, loadAssets)
watch(scopeRefreshKey, () => {
  if (['system', 'version'].includes(props.assetType)) return
  filters.page = 1
  loadAssets()
})
</script>

<style scoped>
.asset-list-page { display: flex; flex: 1; flex-direction: column; min-height: 0; }
/* 筛选区统一卡片化：柔和背景 + 圆角边框，内部表单项自动换行 */
.list-toolbar {
  flex-shrink: 0;
  padding: 12px 16px 12px;
  margin-bottom: 16px;
  background: #f8fafc;
  border: 1px solid #edf1f6;
  border-radius: 10px;
}
.list-toolbar :deep(.el-form) { width: 100%; display: flex; flex-wrap: wrap; align-items: center; row-gap: 12px; column-gap: 10px; }
.list-toolbar :deep(.el-form-item) { margin-bottom: 0; }
/* 操作区独立成行，按钮可换行但按钮文字始终保持单行 */
.list-toolbar :deep(.query-actions) { display: flex; flex: 0 0 auto; width: auto; margin-right: 0; min-width: 0; }
.dense-toolbar :deep(.query-actions) { display: flex; flex: 0 0 100%; width: 100%; margin-right: 0; }
.list-toolbar :deep(.query-actions > .el-form-item__content) { display: flex; flex-wrap: wrap; gap: 10px 12px; margin-left: 0 !important; min-width: 0; }
.query-actions :deep(.el-button) { flex: 0 0 auto; margin: 0; white-space: nowrap; }
.query-actions :deep(.el-button + .el-button) { margin-left: 0; }
.all-cases-toolbar :deep(.el-form) { display: flex; flex-wrap: wrap; align-items: center; row-gap: 12px; column-gap: 10px; }
.all-cases-toolbar :deep(.el-form-item) { margin-right: 0; }
.compact-toolbar :deep(.el-form) { display: flex; flex-wrap: wrap; align-items: center; }
.compact-toolbar :deep(.el-form-item) { margin-right: 14px; margin-bottom: 0; }
.case-tabs-row { display: flex; align-items: center; gap: 16px; min-height: 42px; flex-shrink: 0; }
.confirm-tabs { flex: 1; min-width: 0; }
.confirm-tabs :deep(.el-tabs__header) { margin-bottom: 0; }
.confirm-tabs :deep(.el-tabs__content) { display: none; }
.execution-filter { display: flex; align-items: center; gap: 10px; padding-bottom: 2px; color: #606266; font-size: 13px; white-space: nowrap; }
.table-wrap { position: relative; flex: 1; min-height: 0; overflow: hidden; }
.asset-list-table :deep(.el-table__header .cell),
.asset-list-table :deep(.el-table__body .cell) { white-space: nowrap; }
.asset-list-table :deep(.el-table__body .cell) { overflow: hidden; text-overflow: ellipsis; }
.editable-primary-field { display: inline-block; max-width: 100%; overflow: hidden; padding: 0; text-align: left; text-overflow: ellipsis; vertical-align: baseline; white-space: nowrap; }
.list-pagination { display: flex; justify-content: flex-end; padding-top: 14px; flex-shrink: 0; }
.transition-remark { margin-top: 4px; color: #606266; font-size: 13px; }
.table-actions { display: flex; align-items: center; justify-content: center; gap: 8px; white-space: nowrap; }
.table-actions :deep(.el-button + .el-button) { margin-left: 0; }
.case-detail-section { margin-top: 16px; }
.case-detail-section > strong { color: #303133; font-size: 14px; }
.case-detail-section p { margin: 8px 0 0; color: #606266; line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.case-detail-section pre { max-height: 180px; overflow: auto; padding: 10px 12px; margin: 8px 0 0; background: #f5f7fa; border-radius: 4px; color: #606266; font: 13px/1.6 monospace; white-space: pre-wrap; word-break: break-word; }
.case-detail-section ol { margin: 8px 0 0; padding-left: 22px; color: #606266; line-height: 1.7; }
.summary-title { margin: 18px 0 8px; font-size: 14px; }
.summary-markdown { max-height: 320px; overflow: auto; padding: 12px; margin: 0; background: #f5f7fa; border-radius: 4px; white-space: pre-wrap; word-break: break-word; font-size: 13px; line-height: 1.6; }
.batch-execution-content { padding: 4px 0 8px; }
.batch-execution-hint { margin: 0; color: #606266; line-height: 1.7; }
.batch-execution-options { display: flex; margin-top: 18px; }
.batch-execution-actions { display: flex; justify-content: flex-end; gap: 10px; }
.batch-execution-actions :deep(.el-button + .el-button) { margin-left: 0; }

/* ===== 用例管理页面样式优化（仅作用于 test_case） ===== */
.list-toolbar :deep(.el-form-item__label) { color: #606266; font-weight: 500; }

/* Tab 行：底部分隔线 + 更清晰的字重，收纳右侧执行状态控件 */
.tc-page .case-tabs-row {
  align-items: center;
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 8px;
  margin-bottom: 16px;
}
.tc-page .confirm-tabs :deep(.el-tabs__header) { margin-bottom: 0; }
.tc-page .confirm-tabs :deep(.el-tabs__nav-wrap)::after { display: none; }
.tc-page .confirm-tabs :deep(.el-tabs__item) {
  height: 34px;
  line-height: 34px;
  font-size: 14px;
  font-weight: 500;
  color: #606266;
}
.tc-page .confirm-tabs :deep(.el-tabs__item.is-active) { color: #409eff; font-weight: 600; }

/* 执行状态：由零散单选变为一体化分段控件 */
.tc-page .execution-filter {
  gap: 8px;
  height: 34px;
  padding: 0 6px 0 12px;
  background: #f4f6fa;
  border: 1px solid #edf1f6;
  border-radius: 8px;
  color: #606266;
  font-weight: 500;
}
.tc-page .execution-filter :deep(.el-radio-button__inner) {
  border: none;
  background: transparent;
  box-shadow: none;
  color: #606266;
  padding: 5px 14px;
  border-radius: 6px;
  font-weight: 500;
  transition: background 0.2s, color 0.2s;
}
.tc-page .execution-filter :deep(.el-radio-button__inner:hover) { color: #409eff; }
.tc-page .execution-filter :deep(.el-radio-button.is-active .el-radio-button__inner) {
  background: #409eff;
  color: #fff;
  box-shadow: none;
}

/* 表格：表头浅底加粗、行悬浮高亮、圆角包裹 */
.tc-page .table-wrap :deep(.el-table) { border-radius: 10px; }
.tc-page .table-wrap :deep(.el-table th.el-table__cell) {
  background: #f7f9fc;
  color: #303133;
  font-weight: 600;
}
.tc-page .table-wrap :deep(.el-table__body tr:hover > td.el-table__cell) { background: #f2f8ff; }
.tc-page .table-wrap :deep(.el-table .cell) { line-height: 22px; }
/* 紧凑桌面端（1366~1600）：收窄筛选控件宽度与间距，让筛选项尽量单行、整体不超过两行 */
@media (max-width: 1600px) {
  .list-toolbar :deep(.el-form) { column-gap: 8px; row-gap: 10px; }
  .list-toolbar :deep(.el-form-item__label) { padding-right: 6px; }
  .list-toolbar :deep(.el-form-item .el-input),
  .list-toolbar :deep(.el-form-item .el-select) { max-width: 128px !important; }
  .list-toolbar :deep(.el-form-item .el-date-editor) { max-width: 210px !important; }
}
@media (max-width: 1440px) {
  .list-toolbar :deep(.el-form) { column-gap: 6px; }
  .list-toolbar :deep(.el-form-item .el-input),
  .list-toolbar :deep(.el-form-item .el-select) { max-width: 116px !important; }
  .list-toolbar :deep(.el-form-item .el-date-editor) { max-width: 200px !important; }
}
</style>
