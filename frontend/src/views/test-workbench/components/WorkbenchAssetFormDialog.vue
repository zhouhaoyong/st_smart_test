<template>
  <el-dialog v-model="visible" :title="`${item ? '编辑' : '新建'}${config.name}`" :width="assetType === 'bug' ? '980px' : assetType === 'legacy_item' ? '760px' : '620px'" top="7vh" destroy-on-close>
    <template v-if="assetType === 'bug'">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="bug-editor-form">
        <div class="bug-editor-grid">
          <el-form-item label="Bug 标题" prop="title" class="bug-editor-grid__full"><el-input v-model="form.title" /></el-form-item>
          <el-form-item label="所属系统" prop="system_id">
          <el-select v-model="form.system_id" :disabled="!!item" clearable placeholder="请选择所属系统" style="width: 100%" @change="handleSystemChange"><el-option v-for="system in systems" :key="system.id" :label="system.name" :value="system.id" /></el-select>
          </el-form-item>
          <el-form-item label="所属版本" prop="version_id">
          <el-select v-model="form.version_id" :disabled="!!item" clearable placeholder="请选择所属版本" style="width: 100%" @change="handleVersionChange"><el-option v-for="version in filteredVersions" :key="version.id" :label="version.version_no" :value="version.id" /></el-select>
          </el-form-item>
          <el-form-item label="关联需求">
            <el-select v-model="form.requirement_id" clearable filterable remote :remote-method="searchRequirements" placeholder="选填，可关联需求" style="width: 100%"><el-option v-for="requirement in filteredRequirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select>
          </el-form-item>
          <el-form-item label="关联用例">
            <el-select v-model="form.test_case_id" clearable filterable remote :remote-method="searchTestCases" placeholder="选填，可关联测试用例" style="width: 100%"><el-option v-for="testCase in filteredTestCases" :key="testCase.id" :label="`${testCase.case_no || '未编号'} · ${testCase.title}`" :value="testCase.id" /></el-select>
          </el-form-item>
          <el-form-item label="严重级别"><el-select v-model="form.severity" style="width: 100%"><el-option label="严重" value="critical" /><el-option label="主要" value="major" /><el-option label="一般" value="minor" /></el-select></el-form-item>
          <el-form-item label="优先级"><el-select v-model="form.priority" style="width: 100%"><el-option label="P0" value="P0" /><el-option label="P1" value="P1" /><el-option label="P2" value="P2" /><el-option label="P3" value="P3" /></el-select></el-form-item>
          <el-form-item label="指派人">
            <el-select v-model="form.assignee_id" clearable filterable placeholder="选填，暂不指派" style="width: 100%"><el-option v-for="user in users" :key="user.id" :label="user.real_name || user.username" :value="user.id" /></el-select>
          </el-form-item>
          <el-form-item v-if="item" label="验证人">
            <el-select v-model="form.verifier_id" clearable filterable placeholder="默认 Bug 发起人" style="width: 100%"><el-option v-for="user in users" :key="user.id" :label="user.real_name || user.username" :value="user.id" /></el-select>
          </el-form-item>
          <el-form-item v-if="item" label="状态"><el-tag>{{ bugStatusLabel }}</el-tag></el-form-item>
          <el-form-item label="复现步骤" class="bug-editor-grid__full"><el-input v-model="form.steps" type="textarea" :rows="4" /></el-form-item>
          <el-form-item label="实际结果" class="bug-editor-grid__full"><el-input v-model="form.actual_result" type="textarea" :rows="3" /></el-form-item>
          <el-form-item label="预期结果" class="bug-editor-grid__full"><el-input v-model="form.expected_result" type="textarea" :rows="3" /></el-form-item>
        </div>
      </el-form>
    </template>

    <el-form v-else ref="formRef" :model="form" :rules="rules" :label-width="['version', 'legacy_item'].includes(assetType) ? '120px' : '92px'" :class="{ 'version-form': assetType === 'version', 'legacy-item-form': assetType === 'legacy_item' }">
      <template v-if="assetType === 'system'">
        <el-form-item label="系统名称" prop="name"><el-input v-model="form.name" maxlength="100" show-word-limit /></el-form-item>
        <el-form-item label="系统类型">
          <el-select v-model="form.type" filterable allow-create default-first-option clearable placeholder="请选择或输入系统类型" style="width: 100%">
            <el-option v-for="type in systemTypeOptions" :key="type" :label="type" :value="type" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      </template>

      <template v-else>
        <el-form-item label="所属系统" prop="system_id">
          <el-select v-model="form.system_id" :disabled="!!item" clearable placeholder="请选择所属系统" style="width: 100%" @change="handleSystemChange">
            <el-option v-for="system in systems" :key="system.id" :label="system.name" :value="system.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="needsVersion" label="所属版本" prop="version_id">
          <el-select v-model="form.version_id" :disabled="!!item" clearable placeholder="请选择所属版本" style="width: 100%" @change="handleVersionChange">
            <el-option v-for="version in filteredVersions" :key="version.id" :label="version.version_no" :value="version.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="needsRequirementLink" label="关联需求">
          <el-select v-model="form.requirement_id" clearable filterable remote :remote-method="searchRequirements" placeholder="可选，关联后可追溯测试覆盖" style="width: 100%">
            <el-option v-for="requirement in filteredRequirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="needsTestCaseLink" label="关联用例">
          <el-select v-model="form.test_case_id" clearable filterable remote :remote-method="searchTestCases" placeholder="可选，可关联测试用例" style="width: 100%">
            <el-option v-for="testCase in filteredTestCases" :key="testCase.id" :label="`${testCase.case_no || '未编号'} · ${testCase.title}`" :value="testCase.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="assetType === 'legacy_item'" label="关联 Bug">
          <el-select v-model="form.bug_id" clearable filterable remote :remote-method="searchBugs" placeholder="可选，可关联 Bug" style="width: 100%">
            <el-option v-for="bug in filteredBugs" :key="bug.id" :label="bug.title" :value="bug.id" />
          </el-select>
        </el-form-item>
      </template>

      <template v-if="assetType === 'version'">
        <el-form-item label="版本号" prop="version_no"><el-input v-model="form.version_no" /></el-form-item>
        <el-form-item label="计划发布日期"><el-date-picker v-model="form.plan_release_date" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" :editable="false" clearable placeholder="请选择计划发布日期" style="width: 100%" /></el-form-item>
        <el-form-item label="实际发布日期"><el-date-picker v-model="form.actual_release_date" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" :editable="false" clearable placeholder="请选择实际发布日期" style="width: 100%" /></el-form-item>
        <el-form-item label="当前阶段" prop="current_stage">
          <el-select v-model="form.current_stage" filterable allow-create default-first-option clearable placeholder="请选择或输入当前阶段" style="width: 100%">
            <el-option v-for="stage in currentStageOptions" :key="stage" :label="stage" :value="stage" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      </template>

      <template v-if="assetType === 'requirement'">
        <el-form-item label="需求标题" prop="title"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="需求内容" prop="original_content"><el-input v-model="form.original_content" type="textarea" :rows="7" /></el-form-item>
      </template>

      <template v-if="assetType === 'bug'">
        <el-form-item label="Bug 标题" prop="title"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="严重级别"><el-select v-model="form.severity" style="width: 100%"><el-option label="严重" value="critical" /><el-option label="主要" value="major" /><el-option label="一般" value="minor" /></el-select></el-form-item>
        <el-form-item label="优先级"><el-select v-model="form.priority" style="width: 100%"><el-option label="P0" value="P0" /><el-option label="P1" value="P1" /><el-option label="P2" value="P2" /><el-option label="P3" value="P3" /></el-select></el-form-item>
        <el-form-item v-if="item" label="状态"><el-tag>{{ bugStatusLabel }}</el-tag><span class="bug-status-hint">状态由指派 / 解决 / 验证流程驱动</span></el-form-item>
        <el-form-item label="复现步骤"><el-input v-model="form.steps" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="实际结果"><el-input v-model="form.actual_result" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="预期结果"><el-input v-model="form.expected_result" type="textarea" :rows="3" /></el-form-item>
      </template>

      <template v-if="assetType === 'legacy_item'">
        <el-form-item label="遗留项标题" prop="title"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="类型"><el-input v-model="form.type" /></el-form-item>
        <el-form-item label="计划处理版本"><el-select v-model="form.planned_version_id" clearable placeholder="可选" style="width: 100%"><el-option v-for="version in filteredVersions" :key="version.id" :label="version.version_no" :value="version.id" /></el-select></el-form-item>
        <el-form-item label="优先级"><el-select v-model="form.priority" style="width: 100%"><el-option label="P0" value="P0" /><el-option label="P1" value="P1" /><el-option label="P2" value="P2" /><el-option label="P3" value="P3" /></el-select></el-form-item>
        <el-form-item label="状态"><el-select v-model="form.status" style="width: 100%"><el-option label="待处理" value="pending" /><el-option label="已处理" value="done" /></el-select></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      </template>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, inject, reactive, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import {
  createWorkbenchBug, createWorkbenchLegacyItem, createWorkbenchSystem, createWorkbenchVersion,
  getWorkbenchProjectDashboardAssets, saveWorkbenchRequirement,
  updateWorkbenchBug, updateWorkbenchLegacyItem, updateWorkbenchRequirement, updateWorkbenchSystem, updateWorkbenchVersion,
  getWorkbenchProjectUsers,
} from '@/api/testWorkbench'

const props = defineProps({ modelValue: Boolean, projectId: Number, assetType: String, item: { type: Object, default: null } })
const emit = defineEmits(['update:modelValue', 'saved'])
const { scope } = inject('workbenchContext')
const formRef = ref(null)
const saving = ref(false)
const systems = ref([])
const versions = ref([])
const requirements = ref([])
const testCases = ref([])
const bugs = ref([])
const users = ref([])
const form = reactive({})
const systemTypeOptions = ['Web 应用', '管理后台', '移动 App', 'H5', '微信小程序', '支付宝小程序', '服务端', '开放平台 / API', '桌面端', '嵌入式 / IoT', '其他']
const currentStageOptions = ['规划中', '测试中', '已发布']
const visible = computed({ get: () => props.modelValue, set: (value) => emit('update:modelValue', value) })
const config = computed(() => ({ system: { name: '系统' }, version: { name: '版本' }, requirement: { name: '需求' }, test_case: { name: '测试用例' }, bug: { name: 'Bug' }, legacy_item: { name: '遗留项' } }[props.assetType]))
const needsVersion = computed(() => ['requirement', 'test_case', 'bug', 'legacy_item'].includes(props.assetType))
const needsRequirementLink = computed(() => ['test_case', 'bug', 'legacy_item'].includes(props.assetType))
const needsTestCaseLink = computed(() => ['bug', 'legacy_item'].includes(props.assetType))
const bugStatusLabel = computed(() => ({ pending: '待解决', resolved: '已解决', closed: '已验证关闭', legacy: '遗留' }[props.item?.status] || props.item?.status || '待解决'))
const filteredVersions = computed(() => form.system_id ? versions.value.filter((item) => item.system_id === form.system_id) : [])
const filteredRequirements = computed(() => requirements.value.filter((item) => (
  (!form.system_id || item.system_id === form.system_id)
  && (!form.version_id || item.version_id === form.version_id)
)))
const filteredTestCases = computed(() => testCases.value.filter((item) => (
  (!form.system_id || item.system_id === form.system_id)
  && (!form.version_id || item.version_id === form.version_id)
)))
const filteredBugs = computed(() => bugs.value.filter((item) => (
  (!form.system_id || item.system_id === form.system_id)
  && (!form.version_id || item.version_id === form.version_id)
)))
const rules = computed(() => {
  const required = [{ required: true, message: '此项不能为空', trigger: 'blur' }]
  return {
    name: required, version_no: required, title: required,
    current_stage: props.assetType === 'version' ? [{ required: true, message: '请选择或输入当前阶段', trigger: 'change' }] : [],
    system_id: props.assetType !== 'system' ? [{ required: true, message: '请选择所属系统', trigger: 'change' }] : [],
    version_id: needsVersion.value ? [{ required: true, message: '请选择所属版本', trigger: 'change' }] : [],
  }
})

const resetForm = () => {
  Object.assign(form, {
    system_id: props.item?.system_id || scope.value.system_id || undefined, version_id: props.item?.version_id || scope.value.version_id || undefined,
    name: props.item?.name || '', type: props.item?.type || (props.assetType === 'legacy_item' ? 'bug' : ''), description: props.item?.description || '',
    version_no: props.item?.version_no || '', status: props.item?.status || (props.assetType === 'bug' ? 'pending' : props.assetType === 'legacy_item' ? 'pending' : 'active'),
    plan_release_date: props.item?.plan_release_date || '', actual_release_date: props.item?.actual_release_date || '', current_stage: props.item?.current_stage || '',
    title: props.item?.title || '', original_content: props.item?.original_content || '', case_no: props.item?.case_no || '',
    priority: props.item?.priority || 'P2', scenario: props.item?.scenario || '', case_type: props.item?.case_type || '', expected_result: props.item?.expected_result || '', steps: props.item?.steps || '', steps_text: (props.item?.steps_json || []).map(item => typeof item === 'string' ? item : (item.action || item.step || JSON.stringify(item))).join('\n'), precondition: props.item?.precondition || '', actual_result: props.item?.actual_result || '',
    severity: props.item?.severity || 'major', planned_version_id: props.item?.planned_version_id || undefined,
    requirement_id: props.item?.requirement_id || undefined, test_case_id: props.item?.test_case_id || undefined, bug_id: props.item?.bug_id || undefined, assignee_id: props.item?.assignee_id ?? null, verifier_id: props.item?.verifier_id ?? null,
  })
}
const loadOptions = async () => {
  const [scopeResult, requirementResult, testCaseResult, bugResult, userResult] = await Promise.all([
    getWorkbenchProjectDashboardAssets(props.projectId, { asset_type: 'system', page: 1, page_size: 10 }),
    getWorkbenchProjectDashboardAssets(props.projectId, { asset_type: 'requirement', page: 1, page_size: 100 }),
    getWorkbenchProjectDashboardAssets(props.projectId, { asset_type: 'test_case', page: 1, page_size: 100 }),
    getWorkbenchProjectDashboardAssets(props.projectId, { asset_type: 'bug', page: 1, page_size: 100 }),
    props.assetType === 'bug' ? getWorkbenchProjectUsers(props.projectId) : Promise.resolve(null),
  ])
  systems.value = scopeResult?.systems || []
  versions.value = scopeResult?.versions || []
  requirements.value = requirementResult?.items || []
  testCases.value = testCaseResult?.items || []
  bugs.value = bugResult?.items || []
  users.value = userResult || []
}
const loadRelatedAssets = async (assetType, keyword) => {
  const result = await getWorkbenchProjectDashboardAssets(props.projectId, {
    asset_type: assetType,
    system_id: form.system_id || undefined,
    version_id: form.version_id || undefined,
    title: keyword?.trim() || undefined,
    page: 1,
    page_size: 100,
  })
  return result?.items || []
}
const searchRequirements = async (keyword) => { requirements.value = await loadRelatedAssets('requirement', keyword) }
const searchTestCases = async (keyword) => { testCases.value = await loadRelatedAssets('test_case', keyword) }
const searchBugs = async (keyword) => { bugs.value = await loadRelatedAssets('bug', keyword) }
const handleSystemChange = () => {
  if (form.version_id && !filteredVersions.value.some((item) => item.id === form.version_id)) form.version_id = undefined
  handleVersionChange()
}
const handleVersionChange = () => {
  if (form.requirement_id && !filteredRequirements.value.some((item) => item.id === form.requirement_id)) form.requirement_id = undefined
  if (form.test_case_id && !filteredTestCases.value.some((item) => item.id === form.test_case_id)) form.test_case_id = undefined
  if (form.bug_id && !filteredBugs.value.some((item) => item.id === form.bug_id)) form.bug_id = undefined
}
const confirmLowerVersionNo = async result => {
  if (!result?.requires_confirmation) return true
  try {
    await ElMessageBox.confirm(
      result.message,
      '版本号提醒',
      { confirmButtonText: '继续保存', cancelButtonText: '返回修改', type: 'warning' },
    )
    return true
  } catch {
    return false
  }
}
const submit = async () => {
  await formRef.value?.validate()
  saving.value = true
  try {
    const creating = !props.item
    const platform = { project_id: props.projectId, system_id: form.system_id, version_id: form.version_id }
    const requirementRelation = { requirement_id: form.requirement_id ?? null }
    const testCaseRelation = { test_case_id: form.test_case_id ?? null }
    const handlers = {
      system: creating ? () => createWorkbenchSystem({ project_id: props.projectId, name: form.name, type: form.type, description: form.description }) : () => updateWorkbenchSystem(props.item.id, { name: form.name, type: form.type, description: form.description }),
      version: creating ? () => createWorkbenchVersion({ project_id: props.projectId, system_id: form.system_id, version_no: form.version_no, description: form.description, plan_release_date: form.plan_release_date, actual_release_date: form.actual_release_date, current_stage: form.current_stage }) : () => updateWorkbenchVersion(props.item.id, { version_no: form.version_no, description: form.description, plan_release_date: form.plan_release_date, actual_release_date: form.actual_release_date, current_stage: form.current_stage }),
      requirement: creating ? () => saveWorkbenchRequirement({ ...platform, title: form.title, original_content: form.original_content, source_type: 'manual' }) : () => updateWorkbenchRequirement(props.item.id, { title: form.title, original_content: form.original_content }),
      bug: creating ? () => createWorkbenchBug({ ...platform, ...requirementRelation, ...testCaseRelation, title: form.title, severity: form.severity, priority: form.priority, assignee_id: form.assignee_id ?? null, steps: form.steps, actual_result: form.actual_result, expected_result: form.expected_result }) : () => updateWorkbenchBug(props.item.id, { ...requirementRelation, ...testCaseRelation, title: form.title, severity: form.severity, priority: form.priority, assignee_id: form.assignee_id ?? null, verifier_id: form.verifier_id ?? null, steps: form.steps, actual_result: form.actual_result, expected_result: form.expected_result }),
      legacy_item: creating ? () => createWorkbenchLegacyItem({ ...platform, ...requirementRelation, ...testCaseRelation, bug_id: form.bug_id ?? null, title: form.title, type: form.type, description: form.description, planned_version_id: form.planned_version_id, priority: form.priority, status: form.status }) : () => updateWorkbenchLegacyItem(props.item.id, { ...requirementRelation, ...testCaseRelation, bug_id: form.bug_id ?? null, title: form.title, type: form.type, description: form.description, planned_version_id: form.planned_version_id, priority: form.priority, status: form.status }),
    }
    let result = await handlers[props.assetType]()
    if (props.assetType === 'version' && result?.requires_confirmation) {
      if (!(await confirmLowerVersionNo(result))) return
      const versionPayload = { version_no: form.version_no, description: form.description, plan_release_date: form.plan_release_date, actual_release_date: form.actual_release_date, current_stage: form.current_stage, confirm_lower_version: true }
      result = creating
        ? await createWorkbenchVersion({ project_id: props.projectId, system_id: form.system_id, ...versionPayload })
        : await updateWorkbenchVersion(props.item.id, versionPayload)
    }
    visible.value = false
    emit('saved')
  } finally {
    saving.value = false
  }
}

watch(visible, async (isVisible) => {
  if (!isVisible) return
  resetForm()
  await loadOptions()
})
</script>

<style scoped>
.bug-status-hint { margin-left: 10px; color: #909399; font-size: 12px; }
.bug-editor-form { max-height: min(62vh, 620px); overflow: auto; padding-right: 4px; }
.bug-editor-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 14px; }
.bug-editor-grid :deep(.el-form-item) { margin-bottom: 14px; }
.bug-editor-grid__full { grid-column: 1 / -1; }
.version-form :deep(.el-form-item__label) { white-space: nowrap; }
.legacy-item-form :deep(.el-form-item__label) { white-space: nowrap; }
</style>
