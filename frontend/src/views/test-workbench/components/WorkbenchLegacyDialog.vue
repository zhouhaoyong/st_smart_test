<template>
  <el-dialog v-model="dialog.visible" title="遗留项" width="520px">
    <el-form :model="form" label-width="100px">
      <el-form-item label="遗留项标题" required><el-input v-model="form.title" /></el-form-item>
      <el-form-item label="类型"><el-input v-model="form.type" /></el-form-item>
      <el-form-item label="计划处理版本">
        <el-select v-model="form.planned_version_id" clearable style="width:100%">
          <el-option v-for="item in versions" :key="item.id" :label="item.version_no" :value="item.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog.visible = false">取消</el-button>
      <el-button type="primary" @click="emit('submit')">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
defineProps({
  dialog: { type: Object, required: true },
  form: { type: Object, required: true },
  versions: { type: Array, default: () => [] },
})
const emit = defineEmits(['submit'])
</script>
