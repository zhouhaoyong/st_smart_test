<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="92vw"
    top="6vh"
    append-to-body
    :close-on-click-modal="false"
    class="refinement-save-dialog"
  >
    <p class="save-hint">左侧可直接编辑 Markdown 正文，右侧为实时预览。点击「保存」后才会写入并确认需求。</p>

    <!-- 字数守恒对照：补全的语义是「在原文上增补」，产出短于原文即属异常，先把量摆在最前面。 -->
    <div v-if="original" class="length-bar" :class="{ shrunk: deltaRatio < 0 }">
      <span>原文 <b>{{ original.length }}</b> 字</span>
      <el-icon><Right /></el-icon>
      <span>补全后 <b>{{ draft.length }}</b> 字</span>
      <el-tag :type="deltaRatio < 0 ? 'danger' : 'success'" size="small" effect="light" round>
        {{ deltaRatio >= 0 ? '+' : '' }}{{ deltaRatio.toFixed(1) }}%
      </el-tag>
      <span v-if="deltaRatio < 0" class="length-warn">产出比原文更短，请重点核对是否有内容被删除。</span>
    </div>

    <!-- 守恒校验未通过：后端已自动重试过一次仍不达标，这里必须让人看见再决定是否保存。 -->
    <el-alert
      v-if="checkFailed"
      class="check-alert"
      type="warning"
      show-icon
      :closable="false"
    >
      <template #title>
        <div class="check-alert__title">
          <span>原文内容需要核对</span>
          <el-tag type="warning" effect="plain" size="small">建议确认后保存</el-tag>
        </div>
      </template>
      <div class="check-alert__body">
        <div class="check-issues">
          <div v-for="(issue, index) in checkIssues" :key="index" class="check-issue">{{ issue }}</div>
        </div>
        <el-collapse v-if="missingLines.length" class="missing-collapse">
          <el-collapse-item name="missing">
            <template #title>
              <span>查看未匹配的原文内容</span>
              <span class="missing-collapse__meta">{{ missingTotal }} 行 · 展示前 {{ missingLines.length }} 行</span>
            </template>
            <ol class="missing-list">
              <li v-for="(line, index) in missingLines" :key="index">{{ line }}</li>
            </ol>
          </el-collapse-item>
        </el-collapse>
        <p class="check-tip">可在左侧补回内容后保存，也可以取消保存并返回对话重新整理。</p>
      </div>
    </el-alert>

    <el-form v-if="titleEditable" label-width="94px" class="asset-title-form">
      <el-form-item :label="titleLabel" required>
        <el-input v-model="draftTitle" :maxlength="titleMaxLength" show-word-limit />
      </el-form-item>
    </el-form>

    <div class="md-layout">
      <!-- 编辑区 -->
      <section class="md-card">
        <header class="md-card-head">
          <span class="panel-label">补全正文（Markdown，可编辑）</span>
          <el-button size="small" :icon="CopyDocument" @click="emit('copy', draft)">复制 Markdown</el-button>
        </header>
        <textarea
          ref="editorRef"
          v-model="draft"
          class="md-textarea"
          spellcheck="false"
          placeholder="AI 整理出的需求正文，可在此微调…"
          @scroll="onEditorScroll"
        />
      </section>

      <!-- 预览区 -->
      <section class="md-card">
        <header class="md-card-head">
          <span class="panel-label">预览</span>
          <span class="md-count">{{ draft.length }} 字</span>
        </header>
        <div class="md-preview-wrapper">
          <div v-if="draft.trim()" ref="previewRef" class="md-preview markdown-body" v-html="rendered" @scroll="onPreviewScroll" />
          <div v-else class="md-preview preview-empty">暂无正文</div>
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

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="!draft.trim() || (titleEditable && !draftTitle.trim())" @click="onSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { CopyDocument, Right } from '@element-plus/icons-vue'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps({
  modelValue: Boolean,
  source: { type: String, default: '' },
  // 补全前的原文，仅用于字数守恒对照（不做完整 diff，前端不引入 diff 库）
  original: { type: String, default: '' },
  // 后端守恒校验结果 { passed, issues[], missing_lines[], missing_total, metrics{} }
  check: { type: Object, default: null },
  title: { type: String, default: '预览并保存补全正文' },
  assetTitle: { type: String, default: '' },
  titleEditable: Boolean,
  titleLabel: { type: String, default: '需求标题' },
  titleMaxLength: { type: Number, default: 200 },
  saving: Boolean,
})
const emit = defineEmits(['update:modelValue', 'save', 'copy'])

const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const draft = ref('')
const draftTitle = ref('')
const previewRef = ref(null)
const editorRef = ref(null)

// 字数增减以「当前编辑中的正文」为准：用户手工补回内容后比例应当立刻回升。
const deltaRatio = computed(() => {
  const base = props.original?.length || 0
  if (!base) return 0
  return ((draft.value.length - base) / base) * 100
})
const checkFailed = computed(() => !!props.check && props.check.passed === false)
const checkIssues = computed(() => (Array.isArray(props.check?.issues) ? props.check.issues : []))
const missingLines = computed(() => (Array.isArray(props.check?.missing_lines) ? props.check.missing_lines : []))
const missingTotal = computed(() => Number(props.check?.missing_total || missingLines.value.length))

const onSave = () => {
  emit('save', { markdown_content: draft.value, title: draftTitle.value.trim() })
}

// 渲染时给 h1~h3 注入与目录一致的锚点 id。renderMarkdown 已做 DOMPurify 消毒，再注入 id 属性安全。
const rendered = computed(() => {
  const html = renderMarkdown(draft.value)
  let idx = 0
  return html.replace(/<(h[1-3])>/g, (_, tag) => `<${tag} id="save-heading-${++idx}">`)
})

// 从原始 Markdown 抽取 h1~h3 生成目录（顺序、编号与 rendered 中的 id 对齐）。
// 关键：跳过 ``` 围栏代码块内的 # 行——marked 不会把它们渲染成 <h1~3>，
// 若这里误计入，会导致目录条目比实际标题多、锚点编号整体错位、点击跳错位置。
const toc = computed(() => {
  const headings = []
  let idx = 0
  let inFence = false
  for (const line of (draft.value || '').split('\n')) {
    if (/^\s*(```|~~~)/.test(line)) { inFence = !inFence; continue }
    if (inFence) continue
    const m = line.match(/^(#{1,3})\s+(.+)/)
    if (m) headings.push({ level: m[1].length, text: m[2].trim(), id: `save-heading-${++idx}` })
  }
  return headings
})

const scrollToHeading = id => {
  const el = previewRef.value?.querySelector(`#${id}`)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// 左右联动滚动：编辑区与预览区按“滚动百分比”互相对齐，
// 用户在左侧编辑到哪，右侧预览大致同步到对应位置。用 guard 防止互相触发死循环。
let syncing = false
const syncScroll = (from, to) => {
  if (syncing || !from || !to) return
  syncing = true
  const fromMax = from.scrollHeight - from.clientHeight
  const ratio = fromMax > 0 ? from.scrollTop / fromMax : 0
  const toMax = to.scrollHeight - to.clientHeight
  to.scrollTop = ratio * toMax
  // 下一帧再解锁：本次程序化设置 scrollTop 触发的 scroll 事件先被 guard 吞掉
  requestAnimationFrame(() => { syncing = false })
}
const onEditorScroll = () => syncScroll(editorRef.value, previewRef.value)
const onPreviewScroll = () => syncScroll(previewRef.value, editorRef.value)

// 每次打开：用最新的整理结果初始化编辑内容（避免残留上一次的编辑）
watch(
  () => props.modelValue,
  isOpen => {
    if (isOpen) {
      draft.value = props.source || ''
      const heading = (draft.value.match(/^#\s+(.+)$/m)?.[1] || '').trim()
      draftTitle.value = props.assetTitle || heading
    }
  },
)
</script>

<style scoped>
/* 与「原始需求预览」弹窗同一宽度策略：92vw 自适应 + 超宽屏 max-width 兜底。
   用 :global 是因为 el-dialog append-to-body 后根节点是 teleport，scoped 属性不一定落到 .el-dialog 上。 */
:global(.refinement-save-dialog) { max-width: 1440px; }
.refinement-save-dialog :deep(.el-dialog__body) {
  padding-top: 8px;
}
.save-hint {
  margin: 0 0 10px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.asset-title-form { margin-bottom: 6px; }

/* 字数守恒对照条 */
.length-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  font-size: 13px;
}
.length-bar b { color: var(--el-text-color-primary); }
.length-bar.shrunk {
  background: var(--el-color-danger-light-9);
}
.length-warn { color: var(--el-color-danger); }

/* 守恒校验告警 */
.check-alert {
  margin-bottom: 12px;
  border: 1px solid var(--el-color-warning-light-5);
  border-radius: 8px;
  background: var(--el-color-warning-light-9);
}
.check-alert :deep(.el-alert__icon) {
  margin-top: 1px;
  font-size: 18px;
}
.check-alert :deep(.el-alert__content) {
  min-width: 0;
  padding-right: 2px;
}
.check-alert__title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 22px;
  color: var(--el-color-warning-dark-2);
  font-size: 14px;
  font-weight: 600;
}
.check-alert__title :deep(.el-tag) {
  font-weight: 400;
}
.check-alert__body {
  margin-top: 5px;
}
.check-issues {
  display: grid;
  gap: 3px;
  margin: 0;
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.6;
}
.check-issue::before {
  display: inline-block;
  width: 5px;
  height: 5px;
  margin: 0 8px 2px 1px;
  border-radius: 50%;
  background: var(--el-color-warning);
  content: '';
}
.missing-collapse {
  margin-top: 9px;
  border: 1px solid var(--el-color-warning-light-5);
  border-radius: 6px;
  background: var(--el-bg-color);
}
.missing-collapse :deep(.el-collapse-item__header) {
  height: 34px;
  line-height: 34px;
  font-size: 13px;
}
.missing-collapse__meta {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 400;
}
.missing-collapse :deep(.el-collapse-item__wrap) {
  background: var(--el-fill-color-lighter);
}
.missing-list {
  max-height: 220px;
  margin: 0 12px 8px 28px;
  padding: 6px 0 0 16px;
  overflow: auto;
}
.missing-list li {
  padding: 2px 0;
  font: 12.5px/1.7 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  word-break: break-all;
}
.check-tip {
  margin: 9px 0 0;
  font-size: 12.5px;
  color: var(--el-text-color-secondary);
}
.md-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: stretch;
}

/* 卡片式面板 */
.md-card {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  overflow: hidden;
  background: var(--el-bg-color);
}
.md-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 44px;
  padding: 0 14px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-light);
}
.panel-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.md-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* 编辑区 */
.md-textarea {
  display: block;
  width: 100%;
  height: min(62vh, 640px);
  padding: 14px 16px;
  border: none;
  outline: none;
  resize: none;
  overflow: auto;
  box-sizing: border-box;
  /* pre（而非 pre-wrap）：长行不换行，横向溢出时出现左右滚动条，
     与右侧预览的横向滚动一致，便于对照较长的表格 / 代码行 */
  white-space: pre;
  tab-size: 2;
  color: var(--el-text-color-primary);
  background: var(--el-bg-color);
  font: 13.5px/1.75 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.md-textarea::placeholder { color: var(--el-text-color-placeholder); }

/* 预览区 + 目录 */
.md-preview-wrapper {
  display: flex;
  height: min(62vh, 640px);
  overflow: hidden;
}
.md-preview {
  flex: 1;
  min-width: 0;
  padding: 16px 20px;
  overflow: auto;
  font-size: 15px;
  line-height: 1.85;
  color: var(--el-text-color-primary);
}
.preview-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-placeholder);
}
.md-toc {
  width: 168px;
  flex-shrink: 0;
  padding: 14px 10px 14px 14px;
  border-left: 1px solid var(--el-border-color-lighter);
  overflow-y: auto;
  background: var(--el-fill-color-lighter);
}
.md-toc-title {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
}
.md-toc-item {
  display: block;
  padding: 3px 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-regular);
  cursor: pointer;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.15s;
}
.md-toc-item:hover { color: var(--el-color-primary); }
.md-toc-level-1 { font-weight: 600; }
.md-toc-level-2 { padding-left: 10px; }
.md-toc-level-3 { padding-left: 20px; font-size: 11px; color: var(--el-text-color-secondary); }

/* 正文排版（标题/表格/代码/hr…）统一在 src/styles/markdown.css 的 .markdown-body，此处不再重复 */

@media (max-width: 900px) {
  .md-layout { grid-template-columns: 1fr; }
}
</style>
