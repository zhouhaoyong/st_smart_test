<template>
  <el-dialog
    :model-value="modelValue"
    title="选择 AI 生成用例接口"
    width="min(1120px, calc(100vw - 48px))"
    top="5vh"
    append-to-body
    :close-on-click-modal="false"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
    @closed="handleClosed"
  >
    <InterfaceCaseGenerationScopePanel
      ref="panelRef"
      :project-id="projectId"
      :collection-tree="collectionTree"
      :interface-ids="interfaceIds"
      @confirm="emit('confirm', $event)"
      @cancel="emit('update:modelValue', false)"
    />
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import InterfaceCaseGenerationScopePanel from '@/components/InterfaceCaseGenerationScopePanel.vue'

defineProps({
  modelValue: Boolean,
  projectId: { type: [Number, String], default: null },
  collectionTree: { type: Array, default: () => [] },
  interfaceIds: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'confirm'])
const panelRef = ref(null)

function handleClosed() {
  panelRef.value?.resetState()
}
</script>
