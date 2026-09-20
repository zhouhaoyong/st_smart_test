<template>
  <span class="collection-node-label" :class="{ 'is-disabled': disabled, 'is-wrapped': !truncate }">
    <el-icon class="collection-node-label__icon"><Folder /></el-icon>
    <span class="collection-node-label__name">{{ node?.name || '-' }}</span>
    <span
      v-if="showCount"
      class="collection-node-label__count"
      :class="`is-${statusType}`"
      :title="showTooltip ? statusHint : undefined"
    >({{ interfaceCount }})</span>
    <slot />
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { Folder } from '@element-plus/icons-vue'
import { getCollectionStatusHint, getCollectionStatusType } from '@/utils/interfaceCollections'

const props = defineProps({
  node: { type: Object, default: null },
  showCount: { type: Boolean, default: true },
  showTooltip: { type: Boolean, default: true },
  truncate: { type: Boolean, default: true },
  disabled: { type: Boolean, default: false },
})

const interfaceCount = computed(() => Math.max(0, Number(props.node?.interface_count) || 0))
const statusType = computed(() => getCollectionStatusType(props.node))
const statusHint = computed(() => getCollectionStatusHint(props.node))
</script>

<style scoped>
.collection-node-label {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  gap: 6px;
  color: var(--el-text-color-primary);
  font-size: 14px;
  font-weight: 500;
}

.collection-node-label__icon {
  flex: 0 0 auto;
  color: var(--el-color-primary);
}

.collection-node-label__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.collection-node-label.is-wrapped {
  width: 100%;
  flex-wrap: wrap;
}

.collection-node-label.is-wrapped .collection-node-label__name {
  flex: 1 1 0;
  overflow: visible;
  text-overflow: clip;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.collection-node-label__count {
  flex: 0 0 auto;
  font-size: 12px;
  font-weight: 600;
}

.collection-node-label__count.is-empty { color: var(--el-text-color-placeholder); }
.collection-node-label__count.is-pending { color: var(--el-color-warning); }
.collection-node-label__count.is-done { color: var(--el-color-success); }
.collection-node-label.is-disabled { opacity: 0.65; }
</style>
