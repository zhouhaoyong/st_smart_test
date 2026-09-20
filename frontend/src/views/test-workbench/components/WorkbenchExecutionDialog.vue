<template>
  <el-dialog v-model="dialog.visible" :title="dialogTitle" width="980px" top="7vh" append-to-body class="execution-dialog">
    <el-tabs v-model="activeTab" class="execution-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="用例详情" name="detail">
        <div class="case-detail-layout">
          <el-descriptions v-if="!isFormMode" :column="2" border class="case-summary">
            <el-descriptions-item label="用例编号">{{ testCase?.case_no || '—' }}</el-descriptions-item>
            <el-descriptions-item label="执行状态"><el-tag :type="resultTagType(testCase?.execution_status)">{{ resultLabel(testCase?.execution_status) }}</el-tag></el-descriptions-item>
            <el-descriptions-item label="用例标题" :span="2">{{ testCase?.title || '—' }}</el-descriptions-item>
            <el-descriptions-item label="关联需求">{{ testCase?.requirement_title || '—' }}</el-descriptions-item>
            <el-descriptions-item label="优先级">{{ testCase?.priority || 'P2' }}</el-descriptions-item>
            <el-descriptions-item label="场景">{{ testCase?.scenario || '—' }}</el-descriptions-item>
            <el-descriptions-item label="用例类型">{{ testCase?.case_type || '—' }}</el-descriptions-item>
          </el-descriptions>

          <el-form v-else :model="editForm" label-position="top" class="case-fields-form">
            <div class="case-fields-grid">
              <el-form-item v-if="!isCreate" label="用例编号"><el-input :model-value="testCase?.case_no || '—'" disabled /></el-form-item>
              <el-form-item v-if="!isCreate" label="执行状态"><el-tag :type="resultTagType(testCase?.execution_status)">{{ resultLabel(testCase?.execution_status) }}</el-tag></el-form-item>
              <el-form-item label="用例标题" class="case-fields-grid__full"><el-input v-model="editForm.title" maxlength="200" placeholder="请输入用例标题" /></el-form-item>
              <el-form-item v-if="!isCreate" label="所属系统"><el-input :model-value="testCase?.system_name || '—'" disabled /></el-form-item>
              <el-form-item v-if="!isCreate" label="所属版本"><el-input :model-value="testCase?.version_no || '—'" disabled /></el-form-item>
              <el-form-item label="关联需求"><el-select v-model="editForm.requirement_id" clearable filterable remote :remote-method="searchRequirements" placeholder="可选，关联后可追溯测试覆盖" style="width: 100%"><el-option v-for="requirement in requirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item>
              <el-form-item label="优先级"><el-select v-model="editForm.priority" style="width: 100%"><el-option v-for="level in priorityOptions" :key="level" :label="level" :value="level" /></el-select></el-form-item>
              <el-form-item label="场景"><el-input v-model="editForm.scenario" placeholder="选填" /></el-form-item>
              <el-form-item label="用例类型"><el-select v-model="editForm.case_type" clearable placeholder="请选择用例类型" style="width: 100%"><el-option v-for="type in caseTypeOptions" :key="type" :label="type" :value="type" /></el-select></el-form-item>
            </div>
          </el-form>

          <div class="case-content-grid">
            <section class="case-content-block" :class="{ 'is-editable': isFormMode }">
              <strong>前置条件</strong>
              <p v-if="!isFormMode">{{ testCase?.precondition || '无' }}</p>
              <el-input v-else v-model="editForm.precondition" type="textarea" :rows="3" resize="none" placeholder="选填" />
            </section>
            <section class="case-content-block" :class="{ 'is-editable': isFormMode }">
              <strong>预期结果</strong>
              <p v-if="!isFormMode">{{ testCase?.expected_result || '无' }}</p>
              <el-input v-else v-model="editForm.expected_result" type="textarea" :rows="3" resize="none" placeholder="选填" />
            </section>
            <section class="case-content-block" :class="{ 'is-editable': isFormMode }">
              <strong>测试数据</strong>
              <pre v-if="!isFormMode">{{ formatJson(testCase?.test_data || {}) }}</pre>
              <el-input v-else v-model="editForm.test_data_text" type="textarea" :rows="3" resize="none" placeholder='JSON 格式，如 {"账号": "test"}；无则填 {}' />
            </section>
            <section class="case-content-block" :class="{ 'is-editable': isFormMode }">
              <strong>操作步骤</strong>
              <ol v-if="!isFormMode"><li v-for="(step, index) in caseSteps" :key="index">{{ step }}</li></ol>
              <el-input v-else v-model="editForm.steps_text" type="textarea" :rows="3" resize="none" placeholder="每行一步" />
            </section>
          </div>

          <el-form v-if="!isFormMode" label-position="top" class="execution-result-form">
            <el-form-item label="实际结果"><el-input v-model="form.actual_result" type="textarea" :rows="4" resize="none" placeholder="请记录本次实际执行结果" /></el-form-item>
            <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="4" resize="none" placeholder="选填" /></el-form-item>
          </el-form>

        </div>
      </el-tab-pane>

      <el-tab-pane v-if="!isCreate" label="执行记录" name="history">
        <div v-if="history.length" class="execution-history">
          <div v-for="(item, index) in history" :key="item.id" class="execution-history__item">
            <div class="execution-history__main">
              <el-tag size="small" :type="resultTagType(item.result)">{{ resultLabel(item.result) }}</el-tag>
              <span class="execution-history__time">{{ formatExecutionTime(item.executed_at) }}</span>
              <span v-if="item.executor" class="execution-history__by">{{ item.executor.real_name || item.executor.nick_name }}</span>
              <el-button v-if="index === 0 && !isFormMode" link type="primary" @click="correct(item)">更正</el-button>
            </div>
            <div v-if="item.actual_result" class="execution-history__detail">实际结果：{{ item.actual_result }}</div>
            <div v-if="item.remark" class="execution-history__detail">备注：{{ item.remark }}</div>
          </div>
        </div>
        <el-empty v-else description="暂无执行记录" :image-size="64" />
      </el-tab-pane>
    </el-tabs>
    <template #footer>
      <div class="execution-dialog-actions">
        <template v-if="isFormMode">
          <el-button @click="dialog.visible = false">取消</el-button>
          <el-button type="primary" :loading="editSaving" @click="save">保存</el-button>
        </template>
        <template v-else>
          <el-button v-if="correctingId" @click="emit('cancel-correct')">取消更正</el-button>
          <el-button @click="dialog.visible = false">关闭</el-button>
          <template v-if="activeTab === 'detail'">
            <span v-if="correctingId" class="execution-result-label">保存更正为</span>
            <el-button type="success" @click="submitResult('passed')">通过</el-button>
            <el-button type="danger" @click="submitResult('failed')">失败</el-button>
            <el-button type="info" @click="submitResult('not_executed')">未执行</el-button>
          </template>
        </template>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, inject, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createWorkbenchTestCase, getWorkbenchProjectDashboardAssets, updateWorkbenchTestCase } from '@/api/testWorkbench'
import { formatBeijingTime } from '@/utils/beijingTime'

const props = defineProps({
  dialog: { type: Object, required: true },
  form: { type: Object, required: true },
  testCase: { type: Object, default: null },
  history: { type: Array, default: () => [] },
  correctingId: { type: [Number, String], default: null },
  mode: { type: String, default: 'execute' },
  projectId: { type: Number, default: null },
})
const emit = defineEmits(['correct', 'cancel-correct', 'submit', 'load-history', 'saved'])
const { scope } = inject('workbenchContext')
const activeTab = ref('detail')
const priorityOptions = ['P0', 'P1', 'P2', 'P3']
const caseTypeOptions = ['功能测试', '非功能测试']
const requirements = ref([])
const editSaving = ref(false)
const editForm = reactive({ title: '', requirement_id: undefined, priority: 'P2', scenario: '', case_type: '', precondition: '', expected_result: '', steps_text: '', test_data_text: '{}' })

const isCreate = computed(() => props.mode === 'create')
const isFormMode = computed(() => props.mode === 'edit' || props.mode === 'create')
const dialogTitle = computed(() => {
  if (props.mode === 'edit') return '编辑测试用例'
  if (props.mode === 'create') return '新建测试用例'
  return props.correctingId ? '更正执行结果' : '执行测试用例'
})
const caseSteps = computed(() => (props.testCase?.steps_json || props.testCase?.steps || []).map(step => typeof step === 'string' ? step : step?.step || step?.description || '').filter(Boolean))

const handleTabChange = tab => { if (tab === 'history') emit('load-history') }
const correct = item => { activeTab.value = 'detail'; emit('correct', item) }
const submitResult = async result => {
  props.form.result = result
  // 更正模式或非失败结果：直接记录。
  if (props.correctingId || result !== 'failed') {
    props.form.submit_bug = false
    emit('submit')
    return
  }
  // 失败：弹独立确认框询问是否提交 Bug，执行弹窗保持打开不关闭。
  try {
    await ElMessageBox.confirm('本次执行将记录为失败，是否同时提交 Bug？', '标记为失败', {
      confirmButtonText: '提交 Bug', cancelButtonText: '仅记录失败',
      type: 'warning', distinguishCancelAndClose: true, appendToBody: true,
    })
    props.form.submit_bug = true
  } catch (action) {
    if (action !== 'cancel') return // 点关闭/ESC：取消本次操作，不记录
    props.form.submit_bug = false
  }
  emit('submit')
}

const resetEditForm = () => {
  const tc = props.testCase
  Object.assign(editForm, {
    title: tc?.title || '',
    requirement_id: tc?.requirement_id || undefined,
    priority: tc?.priority || 'P2',
    scenario: tc?.scenario || '',
    case_type: tc?.case_type || '',
    precondition: tc?.precondition || '',
    expected_result: tc?.expected_result || '',
    steps_text: (tc?.steps_json || tc?.steps || []).map(step => typeof step === 'string' ? step : step?.step || step?.description || '').filter(Boolean).join('\n'),
    test_data_text: formatJson(tc?.test_data || {}),
  })
}
const loadRequirementOptions = async keyword => {
  if (!props.projectId) return
  const systemId = props.mode === 'create' ? scope.value.system_id : props.testCase?.system_id
  const versionId = props.mode === 'create' ? scope.value.version_id : props.testCase?.version_id
  const result = await getWorkbenchProjectDashboardAssets(props.projectId, {
    asset_type: 'requirement', system_id: systemId || undefined, version_id: versionId || undefined,
    title: keyword?.trim() || undefined, page: 1, page_size: 100,
  })
  requirements.value = result?.items || []
  const linkedId = props.testCase?.requirement_id
  if (linkedId && !requirements.value.some(item => item.id === linkedId)) {
    requirements.value.unshift({ id: linkedId, title: props.testCase?.requirement_title || `需求 #${linkedId}` })
  }
}
const searchRequirements = keyword => loadRequirementOptions(keyword)
const structuredSteps = () => editForm.steps_text.split('\n').map(item => item.trim()).filter(Boolean).map(step => ({ step }))
const save = async () => {
  if (!editForm.title.trim()) { ElMessage.warning('请填写用例标题'); return }
  let testData
  try { testData = JSON.parse(editForm.test_data_text || '{}') } catch { ElMessage.error('测试数据格式不正确，请输入合法 JSON'); return }
  if (testData === null || typeof testData !== 'object' || Array.isArray(testData)) { ElMessage.error('测试数据需为 JSON 对象，如 {}'); return }
  if (isCreate.value && (!scope.value.system_id || !scope.value.version_id)) { ElMessage.warning('请先在左侧选择所属系统和版本后再新建用例'); return }
  const payload = {
    requirement_id: editForm.requirement_id ?? null,
    title: editForm.title.trim(), scenario: editForm.scenario, case_type: editForm.case_type,
    precondition: editForm.precondition, steps_json: structuredSteps(), test_data: testData,
    priority: editForm.priority, expected_result: editForm.expected_result,
  }
  editSaving.value = true
  try {
    if (isCreate.value) {
      await createWorkbenchTestCase({ project_id: props.projectId, system_id: scope.value.system_id, version_id: scope.value.version_id, ...payload })
    } else {
      await updateWorkbenchTestCase(props.testCase.id, payload)
    }
    props.dialog.visible = false
    emit('saved')
  } finally { editSaving.value = false }
}

watch(() => props.dialog.visible, visible => {
  if (!visible) return
  activeTab.value = 'detail'
  if (isFormMode.value) { resetEditForm(); loadRequirementOptions() }
})

const resultLabels = { passed: '通过', failed: '失败', not_executed: '未执行' }
const resultLabel = value => resultLabels[value] || '未执行'
const resultTagType = value => ({ passed: 'success', failed: 'danger', not_executed: 'info' }[value] || 'info')
const formatExecutionTime = value => formatBeijingTime(value) || '—'
const formatJson = value => { try { return JSON.stringify(value || {}, null, 2) } catch { return '—' } }
</script>

<style scoped>
.execution-tabs :deep(.el-tabs__header) { margin-bottom: 16px; }
.case-detail-layout { display: flex; flex-direction: column; gap: 12px; max-height: min(66vh, 640px); overflow: auto; padding-right: 4px; }
.case-summary { flex: none; }
.case-fields-form { flex: none; }
.case-fields-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 14px; }
.case-fields-grid :deep(.el-form-item) { margin-bottom: 12px; }
.case-fields-grid :deep(.el-form-item__label) { padding-bottom: 4px; line-height: 1.4; }
.case-fields-grid__full { grid-column: 1 / -1; }
.case-content-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.case-content-block { min-width: 0; height: 112px; display: flex; flex-direction: column; padding: 12px 14px; background: var(--el-fill-color-lighter); border: 1px solid var(--el-border-color-lighter); border-radius: 6px; }
.case-content-block strong { flex: none; display: block; margin-bottom: 7px; color: var(--el-text-color-primary); font-size: 13px; }
.case-content-block p, .case-content-block pre, .case-content-block ol { flex: 1; min-height: 0; overflow: auto; margin: 0; color: var(--el-text-color-regular); font-size: 13px; line-height: 1.75; white-space: pre-wrap; word-break: break-word; }
.case-content-block pre { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.case-content-block ol { padding-left: 20px; }
.case-content-block.is-editable { height: auto; padding: 0; background: none; border: none; }
.case-content-block.is-editable strong { margin-bottom: 6px; font-size: 13px; color: var(--el-text-color-regular); }
.execution-result-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.execution-result-form :deep(.el-form-item) { margin-bottom: 0; }
.execution-dialog-actions { display: flex; align-items: center; justify-content: flex-end; gap: 10px; }
.execution-dialog-actions :deep(.el-button + .el-button) { margin-left: 0; }
.execution-result-label { margin-right: 4px; color: var(--el-text-color-secondary); font-size: 13px; }
.execution-history { max-height: min(62vh, 620px); overflow: auto; }
.execution-history__item { padding: 12px 0; border-bottom: 1px dashed var(--el-border-color-lighter); }
.execution-history__main { display: flex; align-items: center; gap: 10px; }
.execution-history__time, .execution-history__by { color: var(--el-text-color-secondary); font-size: 12px; }
.execution-history__detail { margin-top: 7px; color: var(--el-text-color-regular); font-size: 13px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
</style>
