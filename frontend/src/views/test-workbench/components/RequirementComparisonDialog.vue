<template>
  <el-dialog v-model="visible" :title="title" width="92vw" top="6vh" append-to-body class="requirement-comparison-dialog">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="前后对比" name="content">
        <div class="comparison-layout">
          <section class="comparison-panel">
            <header> {{ mergeMode ? '合并前（来源需求）' : '补全前（原始需求）' }} </header>
            <div class="raw-content">
              <template v-if="mergeMode">
                <article v-for="(source, index) in sources" :key="`${source.req_no}-${index}`" class="source-block">
                  <h4>{{ source.req_no ? `${source.req_no} · ` : '' }}{{ source.title || '未命名来源' }}</h4>
                  <pre>{{ source.content || '暂无来源正文' }}</pre>
                </article>
              </template>
              <pre v-else>{{ original || '暂无原始正文' }}</pre>
            </div>
          </section>
          <section class="comparison-panel">
            <header>{{ mergeMode ? '合并后' : '补全后' }}</header>
            <div class="markdown-body result-content" v-html="rendered" />
          </section>
        </div>
      </el-tab-pane>
      <el-tab-pane label="纳入概要" name="summary">
        <p class="overview">{{ comparison?.overview || '暂无概要' }}</p>
        <el-empty v-if="!items.length" description="AI 未返回可核对的用户确认内容" :image-size="64" />
        <div v-else class="summary-list">
          <article v-for="(item, index) in items" :key="index" class="summary-item">
            <el-tag :type="statusType(item.status)" size="small">{{ statusText(item.status) }}</el-tag>
            <div><strong>{{ item.input || '未命名内容' }}</strong><p v-if="item.evidence">依据：{{ item.evidence }}</p><p v-if="item.note">{{ item.note }}</p></div>
          </article>
        </div>
      </el-tab-pane>
    </el-tabs>
    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button type="primary" @click="emit('preview-save')">预览并保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps({
  modelValue: Boolean,
  mergeMode: Boolean,
  title: { type: String, default: '预览并对比' },
  original: { type: String, default: '' },
  sources: { type: Array, default: () => [] },
  result: { type: String, default: '' },
  comparison: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'preview-save'])
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const activeTab = ref('content')
const rendered = computed(() => renderMarkdown(props.result || ''))
const items = computed(() => Array.isArray(props.comparison?.items) ? props.comparison.items : [])
const statusText = value => ({ included: '已纳入', partial: '部分纳入', not_included: '未纳入', skipped: '已跳过' }[value] || '待核对')
const statusType = value => ({ included: 'success', partial: 'warning', not_included: 'danger', skipped: 'info' }[value] || 'info')
watch(visible, open => { if (open) activeTab.value = 'content' })
</script>

<style scoped>
:global(.requirement-comparison-dialog) { max-width: 1440px; }
.comparison-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.comparison-panel { min-width: 0; overflow: hidden; border: 1px solid var(--el-border-color-light); border-radius: 6px; }
.comparison-panel > header { height: 42px; padding: 0 14px; line-height: 42px; font-weight: 600; background: var(--el-fill-color-light); border-bottom: 1px solid var(--el-border-color-lighter); }
.raw-content, .result-content { height: min(62vh, 640px); padding: 16px; overflow: auto; }
.raw-content pre { margin: 0; white-space: pre-wrap; word-break: break-word; font: 13px/1.75 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.source-block + .source-block { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--el-border-color-lighter); }
.source-block h4 { margin: 0 0 8px; font-size: 14px; }
.overview { margin: 0 0 12px; padding: 12px; background: var(--el-fill-color-light); line-height: 1.7; }
.summary-list { display: flex; flex-direction: column; gap: 10px; }
.summary-item { display: flex; gap: 10px; padding: 12px; border: 1px solid var(--el-border-color-lighter); }
.summary-item p { margin: 6px 0 0; color: var(--el-text-color-secondary); line-height: 1.65; }
</style>
