<template>
  <el-dialog
    :model-value="modelValue"
    title="批量设置服务"
    width="420px"
    append-to-body
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-form label-width="80px">
      <el-form-item label="服务">
        <ImportServiceSelect
          v-model="serviceKey"
          :services="services"
          include-empty-option
          style="width: 100%"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="handleConfirm">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import ImportServiceSelect from './ImportServiceSelect.vue'

const props = defineProps({
  modelValue: Boolean,
  services: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'confirm'])
const serviceKey = ref(null)

watch(() => props.modelValue, visible => {
  if (visible) serviceKey.value = null
})

function handleConfirm() {
  emit('confirm', serviceKey.value || null)
  emit('update:modelValue', false)
}
</script>
