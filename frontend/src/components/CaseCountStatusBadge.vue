<template>
  <el-tag
    v-if="normalizedCount > 0"
    :type="normalizedPendingCount > 0 ? 'warning' : 'success'"
    size="small"
    class="case-count-status"
  >{{ normalizedCount }}</el-tag>
  <el-tag v-else type="info" size="small" class="case-count-status case-count-status--empty">0</el-tag>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  count: { type: [Number, String], default: 0 },
  pendingCount: { type: [Number, String], default: 0 },
})

const normalizeCount = value => Math.max(0, Number(value) || 0)
const normalizedCount = computed(() => normalizeCount(props.count))
const normalizedPendingCount = computed(() => normalizeCount(props.pendingCount))
</script>

<style scoped>
.case-count-status { font-weight: 600; }
</style>
