<template>
  <el-button
    :aria-label="tooltip"
    :circle="!label"
    :disabled="isDisabled"
    :icon="DocumentCopy"
    :size="size"
    text
    @click.stop="handleCopy"
  >
    {{ label }}
  </el-button>
</template>

<script setup>
import { computed } from 'vue'
import { DocumentCopy } from '@element-plus/icons-vue'
import { useCopyText } from '@/composables/useCopyText'

const props = defineProps({
  value: { type: [String, Number], default: '' },
  label: { type: String, default: '' },
  tooltip: { type: String, default: '复制' },
  size: { type: String, default: 'small' },
  disabled: Boolean,
})
const emit = defineEmits(['copied'])
const { copyText } = useCopyText()
const isDisabled = computed(() => props.disabled || props.value === null || props.value === undefined || props.value === '')

async function handleCopy() {
  if (await copyText(props.value)) emit('copied')
}
</script>
