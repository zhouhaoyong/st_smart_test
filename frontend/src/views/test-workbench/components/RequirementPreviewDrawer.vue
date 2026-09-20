<template>
  <el-dialog v-model="visible" :title="isCompleted ? '补全需求预览' : '原始需求预览'" width="92vw" top="7vh" append-to-body destroy-on-close class="requirement-preview-dialog">
    <div v-if="detail" class="requirement-preview">
      <div class="preview-head">
        <div>
          <el-input v-if="editing" v-model="titleDraft" class="title-editor" maxlength="200" show-word-limit />
          <h3 v-else>{{ detail.title }}</h3><span>{{ statusText }}</span>
        </div>
        <div class="preview-actions">
          <el-button
            v-if="detail.confirm_status !== 'confirmed'"
            type="primary"
            :loading="confirming"
            @click="confirm"
          >
            确认{{ isCompleted ? '补全需求' : '原始需求' }}
          </el-button>
          <el-button v-if="!editing" @click="startEdit">编辑</el-button>
          <el-button v-if="!isCompleted" type="primary" :icon="MagicStick" @click="reComplete">AI 补全</el-button>
        </div>
      </div>
      <div class="readonly-meta">
        <span>需求编号：{{ detail.req_no || '—' }}</span>
        <span v-if="isCompleted">来源原始需求编号：{{ detail.source_requirement_no || '—' }}</span>
        <span v-if="isCompleted">来源原始需求：{{ detail.source_requirement_title || '—' }}</span>
        <span>所属系统：{{ detail.system_name || '—' }}</span>
        <span>所属版本：{{ detail.version_no || '—' }}</span>
        <span>状态：{{ statusText }}</span>
        <span>创建时间：{{ formatTime(detail.created_at) }}</span>
        <span>创建人：{{ detail.creator_name || '—' }}</span>
      </div>
      <div class="preview-pane">
        <div v-if="!editing" class="tab-toolbar">
          <span class="tab-hint">{{ isCompleted ? `来源原始需求：${detail.source_requirement_title || '—'}` : '原始需求内容' }}</span>
          <el-button size="small" :disabled="!copySource" @click="copyRequirement">复制正文</el-button>
        </div>
        <el-alert v-if="isCompleted && detail.is_stale" title="来源原始需求已更新，请核对本补全需求是否仍适用。" type="warning" :closable="false" class="stale-alert" />
        <div v-if="editing" class="preview-columns">
          <section class="preview-col">
            <div class="preview-col-title"><span>正文编辑</span><el-button link size="small" :disabled="!markdownDraft" @click="copyEditingContent">复制</el-button></div>
            <textarea ref="editorRef" v-model="markdownDraft" class="completion-editor" spellcheck="false" @scroll="onEditorScroll" />
          </section>
          <section class="preview-col">
            <div class="preview-col-title"><span>实时预览</span><el-button link size="small" :disabled="!markdownDraft" @click="copyPreviewContent">复制</el-button></div>
            <div class="md-preview-wrapper">
              <div v-if="markdownDraft" ref="previewRef" class="markdown-rendered markdown-body md-preview" v-html="renderedDraft" @scroll="onPreviewScroll" />
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
          </section>
        </div>
        <div v-else-if="copySource" class="markdown-rendered markdown-body" v-html="renderedContent" />
        <pre v-else class="markdown-preview is-placeholder">暂无内容</pre>
      </div>
    </div>
    <template v-if="editing" #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="!titleDraft.trim() || !markdownDraft.trim()" @click="saveMarkdown">保存需求内容</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import { copyToClipboard } from '@/utils/clipboard'
import { renderMarkdown } from '@/utils/markdown'
import {
  confirmWorkbenchCompletedRequirement,
  confirmWorkbenchRequirement,
  updateWorkbenchCompletedRequirement,
  updateWorkbenchRequirement,
} from '@/api/testWorkbench'
import { formatBeijingTime } from '@/utils/beijingTime'

const props = defineProps({
  modelValue: Boolean,
  detail: { type: Object, default: null },
  requirementType: { type: String, default: 'original' },
  startEditing: Boolean,
})
const emit = defineEmits(['update:modelValue', 'confirmed', 'saved', 're-complete'])
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const confirming = ref(false)
const saving = ref(false)
const editing = ref(false)
const markdownDraft = ref('')
const titleDraft = ref('')
const editorRef = ref(null)
const previewRef = ref(null)

const isCompleted = computed(() => props.requirementType === 'completed')
const statusLabel = status => ({ draft: '待确认', confirmed: '已确认' }[status] || '待确认')
const statusText = computed(() => statusLabel(props.detail?.confirm_status))
// 统一走 renderMarkdown（marked 解析 + DOMPurify 消毒），避免 v-html 直出未消毒 HTML 造成 XSS。
const renderedContent = computed(() => renderMarkdown(props.detail?.markdown_content || props.detail?.original_content || ''))
// 编辑态为标题注入锚点，让目录与右侧预览保持一一对应。
const renderedDraft = computed(() => {
  const html = renderMarkdown(markdownDraft.value || '')
  let index = 0
  return html.replace(/<(h[1-3])>/g, (_, tag) => `<${tag} id="requirement-heading-${++index}">`)
})
const toc = computed(() => {
  const headings = []
  let index = 0
  let inFence = false
  for (const line of markdownDraft.value.split('\n')) {
    if (/^\s*(```|~~~)/.test(line)) { inFence = !inFence; continue }
    if (inFence) continue
    const match = line.match(/^(#{1,3})\s+(.+)/)
    if (match) headings.push({ level: match[1].length, text: match[2].trim(), id: `requirement-heading-${++index}` })
  }
  return headings
})
// 复制持久化的原文，不复制 Markdown 渲染后的 HTML，也不取尚未保存的编辑内容。
const copySource = computed(() => isCompleted.value ? props.detail?.markdown_content || '' : props.detail?.original_content || '')

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
const copyRequirement = () => copyContent(copySource.value)
const copyEditingContent = () => copyContent(markdownDraft.value)
const copyPreviewContent = () => copyContent(markdownDraft.value)
const scrollToHeading = id => previewRef.value?.querySelector(`#${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

// 编辑区和预览区以滚动比例同步；guard 防止程序化滚动再次触发反向同步。
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

const startEdit = () => {
  titleDraft.value = props.detail.title || ''
  markdownDraft.value = props.detail.markdown_content || props.detail.original_content || ''
  editing.value = true
}

const saveMarkdown = async () => {
  saving.value = true
  try {
    const result = isCompleted.value
      ? await updateWorkbenchCompletedRequirement(props.detail.id, { title: titleDraft.value, markdown_content: markdownDraft.value })
      : await updateWorkbenchRequirement(props.detail.id, { title: titleDraft.value, original_content: markdownDraft.value })
    editing.value = false
    emit('saved', result)
  } finally { saving.value = false }
}

// 重新补全：以当前「补全后的正文」为基线，另起一轮全新的 AI 补全对话。
// 语义上等价于把补全结果当作新的输入再补全一次——后端 requirement_body() 本就优先取
// markdown_content，且开启会话会清掉上一轮记录，因此这里只需引导父级打开 AI 补全会话。
// 不保留历史、结果覆盖式保存（与既有架构一致，无版本链）。会消耗额度，故先确认。
const reComplete = async () => {
  try {
    await ElMessageBox.confirm(
      '将以当前原始需求为基础开启一轮 AI 补全对话。保存结果会新建一条补全需求，不会覆盖原始需求。是否继续？',
      'AI 补全',
      { type: 'warning', confirmButtonText: '开始补全', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  visible.value = false
  emit('re-complete')
}

const confirm = async () => {
  try {
    await ElMessageBox.confirm(
      isCompleted.value ? '确认后，该补全需求可作为 AI 生成测试用例的来源。' : '确认后，该原始需求可参与合并并作为 AI 生成测试用例的来源。',
      '确认需求',
      { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  confirming.value = true
  try {
    if (isCompleted.value) await confirmWorkbenchCompletedRequirement(props.detail.id)
    else await confirmWorkbenchRequirement(props.detail.id)
    emit('confirmed')
  } finally { confirming.value = false }
}

watch(visible, open => {
  if (!open) return
  editing.value = false
  if (props.startEditing) startEdit()
})

const formatTime = value => formatBeijingTime(value) || '—'
</script>

<style scoped>
.preview-head { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.preview-head h3 { margin: 0 0 6px; font-size: 18px; color: #303133; }
.title-editor { width: 420px; margin-bottom: 6px; }
.preview-actions { display: flex; justify-content: flex-end; gap: 8px; }
.preview-head span { color: #909399; font-size: 13px; }
/* 宽度用 92vw 自适应，并以 max-width 兜住超宽屏，避免两栏编辑器被拉得过长影响阅读。 */
:global(.requirement-preview-dialog) { max-width: 1440px; height: min(800px, calc(100vh - 14vh)); margin-bottom: 0; display: flex; flex-direction: column; overflow: hidden; }
:global(.requirement-preview-dialog .el-dialog__body) { flex: 1; min-height: 0; overflow: hidden !important; }
.requirement-preview { height: 100%; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.preview-tabs { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.preview-tabs :deep(.el-tabs__header) { flex: none; }
.preview-tabs :deep(.el-tabs__content), .preview-tabs :deep(.el-tab-pane) { flex: 1; min-height: 0; height: 100%; overflow: hidden; }
.preview-pane { height: 100%; min-height: 0; display: flex; flex-direction: column; }
.readonly-meta { display: flex; flex-wrap: wrap; gap: 6px 18px; margin-bottom: 12px; padding: 10px 12px; color: var(--el-text-color-secondary); background: var(--el-fill-color-lighter); border-radius: 6px; font-size: 12px; line-height: 20px; }
.tab-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 10px; }
.tab-toolbar-actions { display: flex; align-items: center; gap: 8px; flex: none; }
.tab-hint { color: #909399; font-size: 12px; line-height: 1.6; }
.markdown-preview { flex: 1; min-height: 0; margin: 0; padding: 16px; overflow: auto; white-space: pre-wrap; color: #303133; background: #fafafa; border: 1px solid #ebeef5; border-radius: 6px; font: 13px/1.8 ui-monospace, SFMono-Regular, Menlo, monospace; }
.markdown-preview.is-placeholder { color: #c0c4cc; }
/* 只保留容器布局；正文排版（标题/表格/代码/hr…）统一在 src/styles/markdown.css 的 .markdown-body */
.markdown-rendered { flex: 1; min-height: 0; padding: 16px; overflow: auto; background: #fafafa; border: 1px solid #ebeef5; border-radius: 6px; font-size: 14px; }
.preview-columns { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; }
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
