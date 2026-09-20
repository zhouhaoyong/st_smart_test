<template>
  <el-dialog v-model="dialog.visible" title="提交 Bug" width="980px" top="7vh" append-to-body class="bug-dialog">
    <el-form :model="form" label-position="top" class="bug-form-grid">
      <el-form-item label="Bug 标题" required class="bug-form-grid__full"><el-input v-model="form.title" /></el-form-item>
      <el-form-item label="所属系统"><el-input :model-value="testCase?.system_name || '—'" disabled /></el-form-item>
      <el-form-item label="所属版本"><el-input :model-value="testCase?.version_no || '—'" disabled /></el-form-item>
      <el-form-item label="关联需求"><el-input :model-value="testCase?.requirement_title || '未关联'" disabled /></el-form-item>
      <el-form-item label="关联用例"><el-input :model-value="testCase ? `${testCase.case_no || '未编号'} · ${testCase.title || ''}` : '未关联'" disabled /></el-form-item>
      <el-form-item label="严重级别">
        <el-select v-model="form.severity" style="width: 100%"><el-option label="严重" value="critical" /><el-option label="主要" value="major" /><el-option label="一般" value="minor" /></el-select>
      </el-form-item>
      <el-form-item label="优先级">
        <el-select v-model="form.priority" style="width: 100%"><el-option label="P0" value="P0" /><el-option label="P1" value="P1" /><el-option label="P2" value="P2" /><el-option label="P3" value="P3" /></el-select>
      </el-form-item>
      <el-form-item label="指派人">
        <el-select v-model="form.assignee_id" clearable filterable placeholder="选填，暂不指派" style="width: 100%">
          <el-option v-for="user in users" :key="user.id" :label="user.real_name || user.username" :value="user.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="本次执行结果"><el-tag type="danger">失败</el-tag></el-form-item>
      <el-form-item label="复现步骤" class="bug-form-grid__full"><el-input v-model="form.steps" type="textarea" :rows="4" /></el-form-item>
      <el-form-item label="实际结果" class="bug-form-grid__full"><el-input v-model="form.actual_result" type="textarea" :rows="3" placeholder="已带入本次执行结果，可继续补充" /></el-form-item>
      <el-form-item label="预期结果" class="bug-form-grid__full"><el-input v-model="form.expected_result" type="textarea" :rows="3" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog.visible = false">取消</el-button>
      <el-button type="primary" @click="emit('submit')">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { getWorkbenchProjectUsers } from '@/api/testWorkbench'

const props = defineProps({
  dialog: { type: Object, required: true },
  form: { type: Object, required: true },
  testCase: { type: Object, default: null },
  projectId: { type: Number, required: true },
})
const emit = defineEmits(['submit'])
const users = ref([])

watch(() => props.dialog.visible, async visible => {
  if (!visible || users.value.length) return
  users.value = await getWorkbenchProjectUsers(props.projectId) || []
})
</script>

<style scoped>
.bug-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; max-height: min(62vh, 620px); overflow: auto; padding-right: 4px; }
.bug-form-grid :deep(.el-form-item) { margin-bottom: 14px; }
.bug-form-grid__full { grid-column: 1 / -1; }
</style>
