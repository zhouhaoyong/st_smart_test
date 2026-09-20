<template>
  <el-dialog v-model="dialog.visible" :title="title" width="420px">
    <el-form :model="form" label-width="90px">
      <el-form-item :label="dialog.kind === 'version' ? '版本号' : '系统名称'" required>
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item v-if="dialog.kind === 'system'" label="系统类型">
        <el-input v-model="form.type" placeholder="如：管理后台、H5、APP" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog.visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="emit('submit')">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  dialog: { type: Object, required: true },
  form: { type: Object, required: true },
  saving: Boolean,
})
const emit = defineEmits(['submit'])

const title = computed(() => ({ system: '新建系统', version: '新建版本' }[props.dialog.kind]))
</script>
