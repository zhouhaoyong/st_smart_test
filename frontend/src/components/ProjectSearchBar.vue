<template>
  <div class="search-bar">
    <el-input
      :model-value="modelValue"
      :placeholder="placeholder"
      :prefix-icon="Search"
      clearable
      size="large"
      class="search-input"
      @update:modelValue="$emit('update:modelValue', $event)"
      @input="$emit('input', $event)"
      @clear="$emit('clear')"
      @keyup.enter="$emit('search')"
    />
    <el-button type="primary" :icon="Search" size="large" :loading="loading" @click="$emit('search')">搜索</el-button>
    <el-button v-if="showCreate" type="primary" size="large" :icon="Plus" @click="$emit('create')">{{ createText }}</el-button>
    <slot name="actions" />
  </div>
</template>

<script setup>
import { Plus, Search } from '@element-plus/icons-vue'

defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '搜索项目名称...' },
  createText: { type: String, default: '新建项目' },
  loading: { type: Boolean, default: false },
  showCreate: { type: Boolean, default: true },
})

defineEmits(['update:modelValue', 'input', 'search', 'clear', 'create'])
</script>

<style scoped>
.search-bar { margin-bottom: 24px; display: flex; align-items: center; gap: 12px; }
.search-input { width: 360px; }
@media (max-width: 720px) {
  .search-bar { align-items: stretch; flex-direction: column; }
  .search-input { width: 100%; }
}
</style>
