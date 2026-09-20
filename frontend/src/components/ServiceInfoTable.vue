<template>
  <el-table
    v-if="serviceRows.length"
    :data="serviceRows"
    border
    size="small"
    class="service-info-table"
  >
    <el-table-column prop="key" label="服务标识" min-width="160" show-overflow-tooltip />
    <el-table-column prop="name" label="服务名称" min-width="160" show-overflow-tooltip />
    <el-table-column prop="path_prefix" label="路径前缀" min-width="240" show-overflow-tooltip />
  </el-table>
  <div v-else class="service-info-empty">未使用</div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  service: { type: [Object, String, Array], default: null },
})

const normalizeService = (value) => {
  if (!value) return null
  if (typeof value === 'string') {
    try { value = JSON.parse(value) } catch { return null }
  }
  if (Array.isArray(value)) value = value[0]
  if (!value || typeof value !== 'object') return null

  const key = String(value.key || '').trim()
  const name = String(value.name || '').trim()
  const pathPrefix = String(value.path_prefix || '').trim()
  if (!key && !name && !pathPrefix) return null

  return {
    key: key || '-',
    name: name || key || '-',
    path_prefix: pathPrefix || '-',
  }
}

const serviceRows = computed(() => {
  const service = normalizeService(props.service)
  return service ? [service] : []
})
</script>

<style scoped>
.service-info-table { width: 100%; }
.service-info-empty {
  padding: 18px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
  color: var(--el-text-color-secondary);
  font-size: 13px;
  text-align: center;
}
</style>
