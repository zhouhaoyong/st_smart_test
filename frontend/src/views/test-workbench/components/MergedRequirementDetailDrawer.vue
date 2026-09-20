<template>
  <el-dialog
    v-model="drawer.visible"
    title="合并需求详情"
    width="92vw"
    top="7vh"
    append-to-body
    destroy-on-close
    class="merged-requirement-detail-dialog"
  >
    <div v-if="drawer.data" v-loading="drawer.loading" class="merged-requirement-detail">
      <div class="preview-head">
        <div>
          <el-input v-if="drawer.editing" v-model="drawer.titleDraft" class="title-editor" maxlength="200" show-word-limit />
          <h3 v-else>{{ drawer.data.title }}</h3>
          <div class="preview-meta">
            <el-tag :type="drawer.data.is_stale ? 'warning' : 'success'" effect="light" size="small">{{ drawer.data.is_stale ? '待重新合并' : '已合并' }}</el-tag>
            <span v-if="drawer.data.req_no">编号：{{ drawer.data.req_no }}</span>
            <span>来源需求 {{ (drawer.data.source_requirement_ids || []).length }} 条</span>
          </div>
        </div>
      </div>
      <el-tabs v-model="drawer.tab" class="merged-requirement-tabs">
        <el-tab-pane label="合并预览" name="preview">
          <div class="tab-toolbar">
            <div class="tab-toolbar-actions">
              <el-button v-if="!drawer.editing" size="small" :disabled="!copySource" @click="copyPreviewContent">复制正文</el-button>
              <el-button v-if="!drawer.editing" @click="startEdit">编辑正文</el-button>
            </div>
          </div>
          <div v-if="drawer.editing" class="preview-columns">
            <div class="preview-col">
              <div class="preview-col-title"><span>需求内容编辑</span><el-button link size="small" :disabled="!drawer.markdownDraft" @click="copyEditingContent">复制</el-button></div>
              <textarea ref="editorRef" v-model="drawer.markdownDraft" class="completion-editor" spellcheck="false" @scroll="onEditorScroll" />
            </div>
            <div class="preview-col">
              <div class="preview-col-title"><span>实时预览</span><el-button link size="small" :disabled="!drawer.markdownDraft" @click="copyPreviewContent">复制</el-button></div>
              <div class="md-preview-wrapper">
                <div v-if="drawer.markdownDraft" ref="previewRef" class="markdown-rendered markdown-body md-preview" v-html="renderedDraft" @scroll="onPreviewScroll" />
                <div v-else class="markdown-preview md-preview preview-empty is-placeholder">暂无内容</div>
                <nav v-if="toc.length" class="md-toc">
                  <div class="md-toc-title">目录</div>
                  <a
                    v-for="item in toc"
                    :key="item.id"
                    :class="['md-toc-item', `md-toc-level-${item.level}`]"
                    :title="item.text"
                    @click.prevent="scrollToHeading(item.id)"
                  >{{ item.text }}</a>
                </nav>
              </div>
            </div>
          </div>
          <div v-else-if="drawer.data.markdown_content" class="markdown-rendered markdown-body" v-html="renderedBody" />
          <pre v-else class="markdown-preview is-placeholder">暂无内容</pre>
        </el-tab-pane>
        <el-tab-pane label="来源需求" name="sources">
          <div class="tab-toolbar">
            <span class="tab-hint">本合并需求所依据的已确认来源需求。点击标题可查看对应需求详情。</span>
            <el-button v-if="drawer.data.is_stale" type="primary" plain :loading="drawer.remerging" @click="emit('remerge')">重新合并</el-button>
          </div>
          <el-table v-if="sourceList.length" :data="sourceList" size="small" border class="source-list-table">
            <el-table-column type="index" label="#" width="52" align="center" />
            <el-table-column prop="req_no" label="来源需求编号" width="170" show-overflow-tooltip />
            <el-table-column prop="title" label="来源需求标题" min-width="240" show-overflow-tooltip>
              <template #default="{ row }">
                <el-button v-if="sourceId(row)" link type="primary" class="source-title-link" :title="row.title || `需求 #${sourceId(row)}`" @click="emit('open-source', { id: sourceId(row), source_type: sourceType(row) })">{{ row.title || `需求 #${sourceId(row)}` }}</el-button>
                <span v-else class="source-title-text" :title="row.title || '—'">{{ row.title || '—' }}</span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无来源需求信息" :image-size="64" />
        </el-tab-pane>
      </el-tabs>
    </div>
    <template v-if="drawer.editing" #footer>
      <el-button @click="drawer.visible = false">取消</el-button>
      <el-button type="primary" :loading="drawer.saving" :disabled="!drawer.titleDraft.trim() || !drawer.markdownDraft.trim()" @click="emit('save-markdown')">保存需求内容</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { copyToClipboard } from '@/utils/clipboard'
import { renderMarkdown } from '@/utils/markdown'
const props = defineProps({
  drawer: { type: Object, required: true },
})
const emit = defineEmits(['save-markdown', 'remerge', 'open-source'])

const sourceList = computed(() => props.drawer.data?.source_requirement_ids || [])
const sourceId = row => row?.source_id || row?.requirement_id || null
const sourceType = row => row?.source_type || 'requirement'
// 合并正文与单条需求正文一致：marked 解析 + DOMPurify 消毒后 v-html 渲染。
const renderedBody = computed(() => renderMarkdown(props.drawer.data?.markdown_content || ''))
const editorRef = ref(null)
const previewRef = ref(null)
const renderedDraft = computed(() => {
  const html = renderMarkdown(props.drawer.markdownDraft || '')
  let index = 0
  return html.replace(/<(h[1-3])>/g, (_, tag) => `<${tag} id="merged-heading-${++index}">`)
})
const toc = computed(() => {
  const headings = []
  let index = 0
  let inFence = false
  for (const line of String(props.drawer.markdownDraft || '').split('\n')) {
    if (/^\s*(```|~~~)/.test(line)) { inFence = !inFence; continue }
    if (inFence) continue
    const match = line.match(/^(#{1,3})\s+(.+)/)
    if (match) headings.push({ level: match[1].length, text: match[2].trim(), id: `merged-heading-${++index}` })
  }
  return headings
})
// 合并需求始终复制保存的 Markdown 原文，而不是页面渲染出的 HTML。
const copySource = computed(() => props.drawer.data?.markdown_content || '')
const startEdit = () => {
  props.drawer.titleDraft = props.drawer.data?.title || ''
  props.drawer.markdownDraft = props.drawer.data?.markdown_content || ''
  props.drawer.editing = true
}

const copyContent = async value => {
  if (!value) return
  try {
    const copied = await copyToClipboard(value)
    if (!copied) throw new Error('clipboard unavailable')
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}
const copyEditingContent = () => copyContent(props.drawer.markdownDraft || '')
const copyPreviewContent = () => copyContent(props.drawer.editing ? props.drawer.markdownDraft : copySource.value)
const scrollToHeading = id => previewRef.value?.querySelector(`#${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

let syncing = false
const syncScroll = (from, to) => {
  if (syncing || !from || !to) return
  syncing = true
  const fromMax = from.scrollHeight - from.clientHeight
  const ratio = fromMax > 0 ? from.scrollTop / fromMax : 0
  const toMax = to.scrollHeight - to.clientHeight
  to.scrollTop = ratio * toMax
  requestAnimationFrame(() => { syncing = false })
}
const onEditorScroll = () => syncScroll(editorRef.value, previewRef.value)
const onPreviewScroll = () => syncScroll(previewRef.value, editorRef.value)

</script>

<style scoped>
:global(.merged-requirement-detail-dialog) { max-width: 1440px; height: min(800px, calc(100vh - 14vh)); margin-bottom: 0; display: flex; flex-direction: column; overflow: hidden; }
:global(.merged-requirement-detail-dialog .el-dialog__body) { flex: 1; min-height: 0; overflow: hidden !important; }
.merged-requirement-detail { height: 100%; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.merged-requirement-tabs { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.merged-requirement-tabs :deep(.el-tabs__header) { flex: none; }
.merged-requirement-tabs :deep(.el-tabs__content) { flex: 1; min-height: 0; overflow: hidden; }
.merged-requirement-tabs :deep(.el-tab-pane) { height: 100%; overflow: auto; }
.preview-head { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.preview-head h3 { margin: 0 0 6px; font-size: 18px; color: #303133; }
.title-editor { width: 420px; margin-bottom: 6px; }
.preview-meta { display: inline-flex; align-items: center; flex-wrap: wrap; gap: 10px; color: #909399; font-size: 13px; }
.tab-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 10px; }
.tab-toolbar-actions { display: flex; align-items: center; gap: 8px; flex: none; }
.tab-hint { color: #909399; font-size: 12px; line-height: 1.6; }
.source-list-table :deep(.el-table__header .cell), .source-list-table :deep(.el-table__body .cell) { white-space: nowrap; }
.source-list-table :deep(.el-table__body .cell) { overflow: hidden; text-overflow: ellipsis; }
.source-title-link, .source-title-text { display: inline-block; max-width: 100%; overflow: hidden; padding: 0; text-overflow: ellipsis; vertical-align: baseline; white-space: nowrap; }
.markdown-preview { min-height: 420px; margin: 0; padding: 16px; overflow: auto; white-space: pre-wrap; color: #303133; background: #fafafa; border: 1px solid #ebeef5; border-radius: 6px; font: 13px/1.8 ui-monospace, SFMono-Regular, Menlo, monospace; }
.markdown-preview.is-placeholder { color: #c0c4cc; }
/* 只保留容器布局；正文排版（标题/表格/代码/hr…）统一在 src/styles/markdown.css 的 .markdown-body */
.markdown-rendered { min-height: 420px; padding: 16px; overflow: auto; background: #fafafa; border: 1px solid #ebeef5; border-radius: 6px; font-size: 14px; }
.preview-columns { height: min(62vh, 640px); display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; }
.preview-col { display: flex; flex-direction: column; min-width: 0; min-height: 0; overflow: hidden; border: 1px solid var(--el-border-color-light); border-radius: 8px; }
.preview-col-title { display: flex; align-items: center; justify-content: space-between; height: 42px; padding: 0 12px; gap: 8px; color: #606266; background: var(--el-fill-color-light); border-bottom: 1px solid var(--el-border-color-lighter); font-size: 13px; font-weight: 600; }
.completion-editor { display: block; flex: 1; width: 100%; min-height: 0; padding: 14px; border: 0; outline: 0; resize: none; overflow: auto; box-sizing: border-box; white-space: pre; tab-size: 2; color: var(--el-text-color-primary); background: var(--el-bg-color); font: 13.5px/1.75 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.md-preview-wrapper { display: flex; flex: 1; min-height: 0; overflow: hidden; }
.md-preview { flex: 1; min-width: 0; min-height: 0; margin: 0; border: 0; border-radius: 0; }
.preview-empty { display: flex; align-items: center; justify-content: center; }
.md-toc { width: 156px; flex: none; padding: 12px 10px; overflow-y: auto; background: var(--el-fill-color-lighter); border-left: 1px solid var(--el-border-color-lighter); }
.md-toc-title { margin-bottom: 8px; color: var(--el-text-color-secondary); font-size: 12px; font-weight: 600; }
.md-toc-item { display: block; padding: 3px 0; overflow: hidden; color: var(--el-text-color-regular); font-size: 12px; line-height: 1.5; text-decoration: none; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }
.md-toc-item:hover { color: var(--el-color-primary); }
.md-toc-level-1 { font-weight: 600; }
.md-toc-level-2 { padding-left: 10px; }
.md-toc-level-3 { padding-left: 20px; color: var(--el-text-color-secondary); font-size: 11px; }
</style>
