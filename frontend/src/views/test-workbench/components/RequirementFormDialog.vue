<template>
  <el-dialog v-model="visible" :title="item ? '编辑需求' : '新建需求'" width="680px" destroy-on-close>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="88px">
      <el-form-item label="所属系统" prop="system_id">
        <el-select v-model="form.system_id" :disabled="!!item" placeholder="请选择所属系统" style="width: 100%" @change="handleSystemChange">
          <el-option v-for="system in systems" :key="system.id" :label="system.name" :value="system.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="所属版本" prop="version_id">
        <el-select v-model="form.version_id" :disabled="!!item" placeholder="请选择所属版本" style="width: 100%">
          <el-option v-for="version in filteredVersions" :key="version.id" :label="version.version_no" :value="version.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="需求标题" prop="title"><el-input v-model="form.title" maxlength="200" show-word-limit /></el-form-item>
      <el-form-item label="需求内容">
        <div class="content-input">
          <el-input v-model="form.original_content" type="textarea" :rows="8" :input-style="{ paddingBottom: '28px' }" placeholder="可先留空，稍后通过手动编辑或 AI 补全完善" />
          <span class="content-count">{{ contentLength }} 字符</span>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, inject, reactive, ref, watch } from 'vue'
import { getWorkbenchProjectDashboardAssets, saveWorkbenchRequirement, updateWorkbenchRequirement } from '@/api/testWorkbench'

const props = defineProps({ modelValue: Boolean, projectId: Number, item: { type: Object, default: null } })
const emit = defineEmits(['update:modelValue', 'saved'])
const { scope } = inject('workbenchContext')
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const formRef = ref(null)
const saving = ref(false)
const systems = ref([])
const versions = ref([])
const form = reactive({ system_id: undefined, version_id: undefined, title: '', original_content: '' })
const rules = { system_id: [{ required: true, message: '请选择所属系统', trigger: 'change' }], version_id: [{ required: true, message: '请选择所属版本', trigger: 'change' }], title: [{ required: true, message: '请输入需求标题', trigger: 'blur' }] }
const filteredVersions = computed(() => versions.value.filter(item => item.system_id === form.system_id))
const contentLength = computed(() => form.original_content.length)

const loadOptions = async () => {
  const result = await getWorkbenchProjectDashboardAssets(props.projectId, { asset_type: 'system', page: 1, page_size: 100 })
  systems.value = result?.systems || []
  versions.value = result?.versions || []
}
const reset = () => Object.assign(form, {
  system_id: props.item?.system_id || scope.value.system_id || undefined,
  version_id: props.item?.version_id || scope.value.version_id || undefined,
  title: props.item?.title || '',
  original_content: props.item?.original_content || '',
})
const handleSystemChange = () => {
  if (!filteredVersions.value.some(item => item.id === form.version_id)) form.version_id = undefined
}
const submit = async () => {
  await formRef.value?.validate()
  saving.value = true
  try {
    const result = props.item
      ? await updateWorkbenchRequirement(props.item.id, { title: form.title, original_content: form.original_content })
      : await saveWorkbenchRequirement({ ...form, project_id: props.projectId, source_type: 'manual' })
    visible.value = false
    emit('saved', result, !props.item)
  } finally {
    saving.value = false
  }
}
watch(visible, async open => {
  if (!open) return
  await loadOptions()
  reset()
})
</script>

<style scoped>
.content-input { position: relative; width: 100%; }
.content-count { position: absolute; right: 12px; bottom: 6px; color: #909399; font-size: 12px; line-height: 18px; pointer-events: none; }
</style>
