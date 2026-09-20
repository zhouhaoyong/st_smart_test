<template>
  <el-table-column type="selection" width="50" fixed :reserve-selection="reserveSelection" />

  <el-table-column label="接口名称" min-width="180" show-overflow-tooltip>
    <template #default="{ row }">
      <span
        class="interface-detail-link"
        role="button"
        tabindex="0"
        @click.stop="$emit('open-detail', row)"
        @keydown.enter.stop="$emit('open-detail', row)"
        @keydown.space.prevent.stop="$emit('open-detail', row)"
      >{{ row.name || '-' }}</span>
    </template>
  </el-table-column>

  <el-table-column label="URL" min-width="220" show-overflow-tooltip>
    <template #default="{ row }">
      <span
        class="interface-detail-link"
        role="button"
        tabindex="0"
        @click.stop="$emit('open-detail', row)"
        @keydown.enter.stop="$emit('open-detail', row)"
        @keydown.space.prevent.stop="$emit('open-detail', row)"
      >{{ row.url || '-' }}</span>
    </template>
  </el-table-column>

  <el-table-column label="服务标识" min-width="170">
    <template #default="{ row }">
      <ImportServiceSelect v-model="row.service_key" :services="services" />
    </template>
  </el-table-column>

  <el-table-column label="一级目录" width="130">
    <template #default="{ row }">
      <slot name="level1" :row="row">{{ row.level1_name || '-' }}</slot>
    </template>
  </el-table-column>

  <el-table-column label="二级目录" width="130">
    <template #default="{ row }">
      <slot name="level2" :row="row">{{ row.level2_name || '-' }}</slot>
    </template>
  </el-table-column>

  <el-table-column label="方法" width="80" align="center">
    <template #default="{ row }">
      <el-tag :type="methodTagType(row.method)" size="small">{{ row.method || '-' }}</el-tag>
    </template>
  </el-table-column>

</template>

<script setup>
import ImportServiceSelect from './ImportServiceSelect.vue'

defineProps({
  services: { type: Array, default: () => [] },
  reserveSelection: Boolean,
})

defineEmits(['open-detail'])

function methodTagType(method) {
  return { GET: 'success', POST: 'primary', PUT: 'warning', DELETE: 'danger', PATCH: 'info' }[method] || ''
}
</script>

<style scoped>
.interface-detail-link {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-color-primary);
  cursor: pointer;
}
.interface-detail-link:hover { text-decoration: underline; }
</style>
