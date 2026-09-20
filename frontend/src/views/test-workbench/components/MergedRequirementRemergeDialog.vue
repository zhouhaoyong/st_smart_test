<template>
  <el-dialog v-model="dialog.visible" title="重新合并" width="820px" destroy-on-close>
    <el-form label-width="88px">
      <el-form-item label="需求标题"><el-input v-model="dialog.title" /></el-form-item>
      <el-form-item label="需求内容"><el-input v-model="dialog.markdown_content" type="textarea" :rows="16" resize="none" /></el-form-item>
    </el-form>
    <div class="dialog-hint">已根据来源需求的最新正文重新生成合并内容，保存后将清除「待重新合并」标记。</div>
    <template #footer>
      <el-button @click="dialog.visible = false">取消</el-button>
      <el-button type="primary" :loading="dialog.saving" @click="emit('confirm')">确认合并</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
defineProps({
  dialog: { type: Object, required: true },
})
const emit = defineEmits(['confirm'])
</script>

<style scoped>
.dialog-hint { margin-top: 6px; color: #909399; font-size: 12px; line-height: 1.6; }
</style>
