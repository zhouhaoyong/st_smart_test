<template>
  <header class="workbench-page-header">
    <div class="header-copy">
      <h2>{{ title }}</h2>
    </div>
    <div v-if="$slots.actions" class="header-actions"><slot name="actions" /></div>
  </header>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
})
</script>

<style scoped>
.workbench-page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-shrink: 0; }
.header-copy h2 { margin: 0; color: #303133; font-size: 20px; line-height: 28px; font-weight: 600; }
.header-actions { flex-shrink: 0; }
</style>
