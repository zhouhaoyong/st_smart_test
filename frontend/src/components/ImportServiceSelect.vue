<template>
  <el-select
    :model-value="modelValue"
    clearable
    allow-create
    filterable
    :placeholder="placeholder"
    :size="size"
    style="width: 100%"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-option v-if="includeEmptyOption" :label="placeholder" :value="null" />
    <el-option
      v-for="service in services"
      :key="service.key"
      :label="formatServiceOptionLabel(service)"
      :value="service.key"
    />
  </el-select>
</template>

<script setup>
import { formatServiceOptionLabel } from '@/utils/serviceEnvironment'

defineProps({
  modelValue: { type: [String, Number], default: null },
  services: { type: Array, default: () => [] },
  placeholder: { type: String, default: '不使用服务标识' },
  size: { type: String, default: 'small' },
  includeEmptyOption: Boolean,
})

defineEmits(['update:modelValue'])
</script>
