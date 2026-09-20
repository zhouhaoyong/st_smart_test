<template>
  <section v-if="content" class="conversation-content-block">
    <header class="content-block-head" @click="open = !open">
      <span>{{ title }}</span>
      <div class="content-block-actions">
        <el-button v-if="copyable" link size="small" @click.stop="emit('copy', copyContent)">复制</el-button>
        <el-button link size="small" @click.stop="open = !open">{{ open ? '收起' : '展开' }}</el-button>
      </div>
    </header>
    <div v-show="open" class="content-block-body">
      <div v-if="markdown" class="markdown-body content-block-markdown" v-html="renderMarkdown(content)" />
      <pre v-else class="content-block-text">{{ content }}</pre>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps({
  title: { type: String, required: true },
  content: { type: String, default: '' },
  markdown: Boolean,
  modelValue: Boolean,
  copyable: Boolean,
})
const emit = defineEmits(['update:modelValue', 'copy'])
const open = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const copyContent = computed(() => `## ${props.title}\n\n${props.content}`)
</script>

<style scoped>
.conversation-content-block { margin-top: 12px; border-top: 1px solid var(--el-color-primary-light-7); }
.content-block-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 38px; color: var(--el-text-color-regular); font-size: 13px; font-weight: 600; cursor: pointer; user-select: none; }
.content-block-head:hover { color: var(--el-text-color-primary); }
.content-block-head > span { flex: 1; min-width: 0; }
.content-block-actions { display: flex; align-items: center; gap: 4px; }
.content-block-body { max-height: 260px; margin: 0 0 8px; overflow: auto; border-radius: 4px; background: rgba(255, 255, 255, .72); }
.content-block-text { margin: 0; padding: 10px; color: var(--el-text-color-regular); font: 12px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space: pre-wrap; word-break: break-word; }
.content-block-markdown { padding: 10px 12px; color: var(--el-text-color-regular); }
</style>
