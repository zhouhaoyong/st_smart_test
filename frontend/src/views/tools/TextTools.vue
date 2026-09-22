<template>
  <div class="tool-page">
    <div class="page-header"><h2>{{ pageTitle }}</h2></div>
    <p v-if="activeTab === 'translation'" class="translation-privacy-tip">
      提示：翻译内容将发送至外部翻译服务，请勿输入密码、Token、API Key 等敏感信息。
    </p>
    <el-card>
      <el-tabs v-model="activeTab" class="text-tabs">
        <el-tab-pane label="多语言翻译" name="translation">
          <div class="translation-layout">
            <section class="editor-panel">
              <div class="panel-header">
                <span class="panel-label">{{ fromLabel }}</span>
                <el-select v-model="tl.form.from_lang" size="small" style="width:100px">
                  <el-option v-for="(label, value) in langNames" :key="value" :label="label" :value="value" />
                </el-select>
              </div>
              <el-input v-model="tl.form.text" type="textarea" :rows="12" placeholder="请输入要翻译的文本" />
            </section>
            <div class="swap-column">
              <el-button circle :icon="Sort" size="default" @click="tlSwapLang" style="width:44px;height:44px" />
            </div>
            <section class="editor-panel">
              <div class="panel-header">
                <span class="panel-label">{{ toLabel }}</span>
                <el-select v-model="tl.form.to_lang" size="small" style="width:100px">
                  <el-option v-for="(label, value) in langNames" :key="value" :label="label" :value="value" />
                </el-select>
              </div>
              <el-input v-model="tl.result" type="textarea" :rows="12" readonly placeholder="翻译结果将显示在这里" />
            </section>
          </div>
          <div class="action-bar">
            <el-button type="primary" @click="tlTranslate" :loading="tl.loading" size="large" round>开始翻译</el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="文本对比" name="textdiff">
          <div class="diff-editor-layout">
            <section class="editor-panel">
              <div class="panel-label">文本 A</div>
              <div class="numbered-textarea">
                <div ref="leftLineNumbersRef" class="line-numbers" aria-hidden="true">
                  <span
                    v-for="line in lineNumbers(td.form.text_left)"
                    :key="line"
                    :class="lineMarkerClass('left', line)"
                  >{{ line }}</span>
                </div>
                <div class="textarea-stack">
                  <textarea
                    ref="leftTextareaRef"
                    v-model="td.form.text_left"
                    class="plain-textarea"
                    rows="14"
                    wrap="off"
                    spellcheck="false"
                    placeholder="粘贴原始文本"
                    @scroll="syncDiffScroll('left', $event)"
                  />
                </div>
              </div>
            </section>
            <section class="editor-panel">
              <div class="panel-label">文本 B</div>
              <div class="numbered-textarea">
                <div ref="rightLineNumbersRef" class="line-numbers" aria-hidden="true">
                  <span
                    v-for="line in lineNumbers(td.form.text_right)"
                    :key="line"
                    :class="lineMarkerClass('right', line)"
                  >{{ line }}</span>
                </div>
                <div class="textarea-stack">
                  <textarea
                    ref="rightTextareaRef"
                    v-model="td.form.text_right"
                    class="plain-textarea"
                    rows="14"
                    wrap="off"
                    spellcheck="false"
                    placeholder="粘贴对比文本"
                    @scroll="syncDiffScroll('right', $event)"
                  />
                </div>
              </div>
            </section>
          </div>
          <div class="diff-toolbar">
            <el-select v-model="td.form.mode" size="small" style="width:120px">
              <el-option label="按行对比" value="line" />
              <el-option label="按字符对比" value="char" />
            </el-select>
            <el-checkbox v-model="td.form.ignore_case">忽略大小写</el-checkbox>
            <el-checkbox v-model="td.form.ignore_whitespace">忽略空白</el-checkbox>
            <el-button type="primary" @click="tdDiff" :loading="td.loading" style="margin-left:auto">开始对比</el-button>
          </div>
          <div v-if="td.hasCompared && td.form.mode === 'line' && lineDiffRows.length" ref="diffResultsRef" class="line-diff-results">
            <div class="diff-summary">
              <span>共 {{ lineDiffRows.length }} 处差异</span>
              <span v-if="lineDiffSummary.replace">修改 {{ lineDiffSummary.replace }} 行</span>
              <span v-if="lineDiffSummary.delete">删除 {{ lineDiffSummary.delete }} 行</span>
              <span v-if="lineDiffSummary.insert">新增 {{ lineDiffSummary.insert }} 行</span>
            </div>
            <div class="line-diff-table">
              <div class="line-diff-head">
                <span>文本 A</span>
                <span>文本 B</span>
              </div>
              <button
                v-for="(row, i) in lineDiffRows"
                :key="`${row.diffIndex}-${i}`"
                type="button"
                :class="['line-diff-row', `is-${row.type}`, { 'is-active-diff': row.diffIndex === activeDiffIndex }]"
                @click="locateDiff(td.diffs[row.diffIndex], row.diffIndex)"
              >
                <span :class="['line-diff-cell', { 'is-empty': !row.left }]">
                  <b v-if="row.left" class="line-diff-number">{{ row.left.number }}</b>
                  <code>{{ displayLineContent(row.left) }}</code>
                </span>
                <span :class="['line-diff-cell', { 'is-empty': !row.right }]">
                  <b v-if="row.right" class="line-diff-number">{{ row.right.number }}</b>
                  <code>{{ displayLineContent(row.right) }}</code>
                </span>
              </button>
            </div>
          </div>
          <div v-else-if="td.hasCompared && td.form.mode === 'char' && td.diffs.length" ref="diffResultsRef" class="diff-results">
            <div
              v-for="(d, i) in td.diffs"
              :key="i"
              :ref="i === 0 ? setFirstDiffRef : null"
              :class="['diff-item', { 'is-active-diff': i === activeDiffIndex }]"
              role="button"
              tabindex="0"
              @click="locateDiff(d, i)"
              @keydown.enter.prevent="locateDiff(d, i)"
              @keydown.space.prevent="locateDiff(d, i)"
            >
              <div class="diff-item-head">
                <span class="diff-index">#{{ i + 1 }}</span>
                <el-tag size="small" :type="diffTagType(d.type)">{{ diffTypeText(d.type) }}</el-tag>
                <span class="diff-action-tip">点击定位</span>
              </div>
              <div class="diff-content-grid">
                <div class="diff-side">
                  <div class="diff-side-title">文本 A 中的差异内容</div>
                  <div class="diff-side-lines">{{ diffPositionText(d, 'left') }}</div>
                  <pre class="diff-text diff-left">{{ displayDiffText(d.left_text, d.type, 'left') }}</pre>
                </div>
                <div class="diff-side">
                  <div class="diff-side-title">文本 B 中的差异内容</div>
                  <div class="diff-side-lines">{{ diffPositionText(d, 'right') }}</div>
                  <pre class="diff-text diff-right">{{ displayDiffText(d.right_text, d.type, 'right') }}</pre>
                </div>
              </div>
            </div>
          </div>
          <div v-else-if="td.hasCompared && !td.loading" class="same-result">
            文本完全一致
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Sort } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { withAiRequestTimeout } from '@/utils/aiRequestTimeout'
import { buildLineDiffRows, getCharacterRangeLabel, getLineDiffSummary } from '@/utils/textDiffView'

const activeTab = ref('translation')
const route = useRoute()
const pageTitle = computed(() => route.meta.title || '文本工具')

watch(
  () => route.meta.toolTab,
  (tab) => {
    activeTab.value = tab || 'textdiff'
  },
  { immediate: true },
)

const langNames = { zh: '中文', en: '英文', ja: '日文', ko: '韩文', fr: '法文', de: '德文', ru: '俄文', es: '西文' }
const tl = reactive({ loading: false, result: '', form: { text: '', from_lang: 'en', to_lang: 'zh' } })
const fromLabel = computed(() => '源语言: ' + (langNames[tl.form.from_lang] || ''))
const toLabel = computed(() => '目标语言: ' + (langNames[tl.form.to_lang] || ''))

const tlSwapLang = () => {
  const tmp = tl.form.from_lang
  tl.form.from_lang = tl.form.to_lang
  tl.form.to_lang = tmp
  if (tl.result) { tl.form.text = tl.result; tl.result = '' }
}

const tlTranslate = async () => {
  if (!tl.form.text.trim()) { ElMessage.warning('请输入文本'); return }
  tl.loading = true
  try {
    const res = await request({ url: '/tools/translate', method: 'post', data: tl.form, ...withAiRequestTimeout() })
    tl.result = res.result || ''
  } catch {} finally {
    tl.loading = false
  }
}

const td = reactive({
  loading: false,
  diffs: [],
  hasCompared: false,
  form: { text_left: '', text_right: '', mode: 'line', ignore_case: false, ignore_whitespace: false },
})
const leftLineNumbersRef = ref(null)
const rightLineNumbersRef = ref(null)
const leftTextareaRef = ref(null)
const rightTextareaRef = ref(null)
const diffResultsRef = ref(null)
const firstDiffRef = ref(null)
const syncingScroll = ref(false)
const activeDiffIndex = ref(-1)
const DIFF_LINE_HEIGHT = 22
let tdRequestVersion = 0

const lineNumbers = (text) => Array.from({ length: Math.max((text || '').split('\n').length, 1) }, (_, i) => i + 1)

const syncLineNumbers = (textarea, gutter) => {
  if (!textarea || !gutter) return
  gutter.scrollTop = textarea.scrollTop
}

const syncDiffScroll = (side, event) => {
  const source = event.target
  const target = side === 'left' ? rightTextareaRef.value : leftTextareaRef.value
  const sourceGutter = side === 'left' ? leftLineNumbersRef.value : rightLineNumbersRef.value
  const targetGutter = side === 'left' ? rightLineNumbersRef.value : leftLineNumbersRef.value

  syncLineNumbers(source, sourceGutter)
  if (syncingScroll.value || !target) return

  syncingScroll.value = true
  target.scrollTop = source.scrollTop
  target.scrollLeft = source.scrollLeft
  syncLineNumbers(target, targetGutter)
  requestAnimationFrame(() => { syncingScroll.value = false })
}

const setFirstDiffRef = (el) => {
  if (el) firstDiffRef.value = el
}

const charIndexToLine = (text, index) => {
  const safeIndex = Math.max(index, 0)
  return (text.slice(0, safeIndex).match(/\n/g) || []).length + 1
}

const diffLinesForSide = (diff, side) => {
  const text = side === 'left' ? td.form.text_left : td.form.text_right
  const startKey = side === 'left' ? 'left_start' : 'right_start'
  const endKey = side === 'left' ? 'left_end' : 'right_end'

  if (td.form.mode === 'char') {
    if (diff[endKey] <= diff[startKey]) return []
    const start = charIndexToLine(text, diff[startKey]) - 1
    const end = charIndexToLine(text, diff[endKey] - 1) - 1
    return Array.from({ length: end - start + 1 }, (_, index) => start + index + 1)
  }
  if (diff[endKey] <= diff[startKey]) return []
  return Array.from({ length: diff[endKey] - diff[startKey] }, (_, index) => diff[startKey] + index + 1)
}

const diffHighlightLines = (side) => {
  const lines = new Set()
  td.diffs.forEach((diff) => {
    diffLinesForSide(diff, side).forEach((line) => lines.add(line))
  })
  return Array.from(lines).sort((a, b) => a - b)
}

const activeHighlightLines = (side) => {
  const diff = td.diffs[activeDiffIndex.value]
  return diff ? diffLinesForSide(diff, side) : []
}

const lineMarkerClass = (side, line) => ({
  'is-diff-line': diffHighlightLines(side).includes(line),
  'is-active-line': activeHighlightLines(side).includes(line),
})

const lineStartOffsets = (text) => {
  const offsets = [0]
  for (let i = 0; i < text.length; i += 1) {
    if (text[i] === '\n') offsets.push(i + 1)
  }
  return offsets
}

const lineRangeToOffsets = (text, start, end) => {
  const offsets = lineStartOffsets(text)
  const safeStart = Math.min(Math.max(start, 0), offsets.length - 1)
  const safeEnd = Math.min(Math.max(end, safeStart), offsets.length)
  return {
    start: offsets[safeStart] ?? text.length,
    end: safeEnd < offsets.length ? offsets[safeEnd] : text.length,
  }
}

const diffSelectionRange = (diff, side) => {
  const text = side === 'left' ? td.form.text_left : td.form.text_right
  const startKey = side === 'left' ? 'left_start' : 'right_start'
  const endKey = side === 'left' ? 'left_end' : 'right_end'

  if (td.form.mode === 'char') {
    return {
      start: Math.min(Math.max(diff[startKey], 0), text.length),
      end: Math.min(Math.max(diff[endKey], diff[startKey]), text.length),
    }
  }
  return lineRangeToOffsets(text, diff[startKey], diff[endKey])
}

const selectDiffRange = (textarea, range) => {
  if (!textarea || !range) return
  textarea.setSelectionRange(range.start, range.end)
}

const scrollEditorsToDiff = async (diff, index, scrollResult = true) => {
  await nextTick()
  if (!diff) return

  activeDiffIndex.value = index
  const leftLine = diffLinesForSide(diff, 'left')[0] || 1
  const rightLine = diffLinesForSide(diff, 'right')[0] || 1
  const topLine = Math.max(Math.min(leftLine, rightLine) - 3, 0)
  const scrollTop = topLine * DIFF_LINE_HEIGHT
  for (const textarea of [leftTextareaRef.value, rightTextareaRef.value]) {
    if (textarea) textarea.scrollTop = scrollTop
  }
  syncLineNumbers(leftTextareaRef.value, leftLineNumbersRef.value)
  syncLineNumbers(rightTextareaRef.value, rightLineNumbersRef.value)
  selectDiffRange(leftTextareaRef.value, diffSelectionRange(diff, 'left'))
  selectDiffRange(rightTextareaRef.value, diffSelectionRange(diff, 'right'))
  rightTextareaRef.value?.focus({ preventScroll: true })
  if (scrollResult) firstDiffRef.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

const scrollEditorsToFirstDiff = async () => {
  await scrollEditorsToDiff(td.diffs[0], 0, false)
}

const locateDiff = (diff, index) => {
  scrollEditorsToDiff(diff, index, false)
}

const diffLineRangeText = (diff, side) => {
  const lines = diffLinesForSide(diff, side)
  if (!lines.length) return '无对应行'
  const first = lines[0]
  const last = lines[lines.length - 1]
  return first === last ? `第 ${first} 行` : `第 ${first}-${last} 行`
}

const diffPositionText = (diff, side) => {
  if (td.form.mode === 'line') return diffLineRangeText(diff, side)
  const text = side === 'left' ? td.form.text_left : td.form.text_right
  const start = side === 'left' ? diff.left_start : diff.right_start
  const end = side === 'left' ? diff.left_end : diff.right_end
  return getCharacterRangeLabel(text, start, end)
}

const lineDiffRows = computed(() => buildLineDiffRows(td.diffs, td.form.text_left, td.form.text_right))
const lineDiffSummary = computed(() => getLineDiffSummary(lineDiffRows.value))
const displayLineContent = (line) => !line ? '此处无内容' : line.content || '空行'

watch(
  () => [td.form.text_left, td.form.text_right, td.form.mode, td.form.ignore_case, td.form.ignore_whitespace],
  () => {
    tdRequestVersion += 1
    td.loading = false
    td.diffs = []
    td.hasCompared = false
    activeDiffIndex.value = -1
  },
)

const displayDiffText = (text, type, side) => {
  if (text) return text
  if (type === 'insert' && side === 'left') return '文本 A 此处没有内容'
  if (type === 'delete' && side === 'right') return '文本 B 此处没有内容'
  return '无内容'
}

const diffTypeText = (type) => ({ replace: '内容不同', delete: '仅文本 A 有', insert: '仅文本 B 有' }[type] || type)
const diffTagType = (type) => ({ replace: 'warning', delete: 'danger', insert: 'success' }[type] || 'info')

const tdDiff = async () => {
  if (!td.form.text_left || !td.form.text_right) { ElMessage.warning('请输入两段文本'); return }
  const requestVersion = tdRequestVersion
  td.diffs = []
  td.hasCompared = false
  activeDiffIndex.value = -1
  td.loading = true
  try {
    const res = await request({ url: '/tools/text-diff', method: 'post', data: td.form })
    if (requestVersion !== tdRequestVersion) return
    td.diffs = res.diffs || []
    td.hasCompared = true
    firstDiffRef.value = null
    activeDiffIndex.value = td.diffs.length ? 0 : -1
    if (td.diffs.length) scrollEditorsToFirstDiff()
  } catch {} finally {
    if (requestVersion === tdRequestVersion) td.loading = false
  }
}
</script>

<style scoped>
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 22px; }
.translation-privacy-tip { margin: -8px 0 16px; color: #8c6d1f; font-size: 13px; line-height: 20px; }
.panel-label { font-weight: 600; font-size: 14px; margin-bottom: 8px; color: #595959; }
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.text-tabs :deep(.el-tabs__header) { display: none; }
.translation-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 72px minmax(0, 1fr);
  gap: 20px;
  align-items: center;
}
.diff-editor-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
}
.editor-panel { min-width: 0; }
.editor-panel :deep(.el-textarea__inner) {
  font-family: SFMono-Regular, Consolas, Monaco, monospace;
  font-size: 13px;
  line-height: 1.6;
}
.swap-column { display: flex; align-items: center; justify-content: center; }
.action-bar { margin-top: 20px; text-align: center; }
.diff-toolbar { margin: 12px 0; display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.numbered-textarea {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  transition: border-color .2s, box-shadow .2s;
  background: #fff;
}
.numbered-textarea:focus-within {
  border-color: #1677ff;
  box-shadow: 0 0 0 2px rgba(22, 119, 255, .12);
}
.line-numbers {
  max-height: 332px;
  overflow: hidden;
  padding: 8px 8px 8px 0;
  background: #f7f8fa;
  border-right: 1px solid #ebeef5;
  color: #a8abb2;
  font-family: SFMono-Regular, Consolas, Monaco, monospace;
  font-size: 13px;
  line-height: 22px;
  text-align: right;
  user-select: none;
  pointer-events: none;
}
.line-numbers span { display: block; height: 22px; }
.line-numbers span.is-diff-line {
  color: #d48806;
  background: rgba(250, 173, 20, .12);
}
.line-numbers span.is-active-line {
  color: #1677ff;
  background: rgba(22, 119, 255, .16);
  font-weight: 700;
}
.textarea-stack {
  position: relative;
  min-width: 0;
  background: #fff;
  overflow: hidden;
}
.plain-textarea {
  position: relative;
  z-index: 1;
  width: 100%;
  min-height: 332px;
  resize: vertical;
  border: 0;
  outline: none;
  background: transparent;
  padding: 8px 10px;
  color: #303133;
  font-family: SFMono-Regular, Consolas, Monaco, monospace;
  font-size: 13px;
  line-height: 22px;
  box-sizing: border-box;
  overflow: auto;
  overflow-wrap: normal;
  white-space: pre;
}
.plain-textarea::placeholder { color: #a8abb2; }
.line-diff-results { margin-top: 16px; border: 1px solid #ebeef5; border-radius: 6px; overflow: hidden; }
.diff-summary { display: flex; flex-wrap: wrap; gap: 16px; padding: 10px 12px; background: #f7f8fa; color: #606266; font-size: 13px; }
.line-diff-table { overflow: auto; }
.line-diff-head,
.line-diff-row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); min-width: 640px; }
.line-diff-head { background: #fafafa; color: #606266; font-size: 13px; font-weight: 600; }
.line-diff-head span { padding: 8px 12px; }
.line-diff-head span + span { border-left: 1px solid #ebeef5; }
.line-diff-row { width: 100%; padding: 0; border: 0; border-top: 1px solid #f0f2f5; background: #fff; color: #303133; text-align: left; cursor: pointer; font: inherit; }
.line-diff-row:hover { background: #f7fbff; }
.line-diff-row.is-active-diff { outline: 2px solid rgba(22, 119, 255, .35); outline-offset: -2px; position: relative; z-index: 1; }
.line-diff-cell { display: grid; grid-template-columns: 48px minmax(0, 1fr); min-height: 36px; align-items: stretch; }
.line-diff-cell + .line-diff-cell { border-left: 1px solid #ebeef5; }
.line-diff-number { padding: 8px 10px; background: rgba(0, 0, 0, .025); color: #909399; font: 12px/20px SFMono-Regular, Consolas, Monaco, monospace; text-align: right; }
.line-diff-cell code { padding: 8px 10px; color: inherit; font: 13px/20px SFMono-Regular, Consolas, Monaco, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
.line-diff-row.is-replace .line-diff-cell { background: rgba(250, 173, 20, .1); }
.line-diff-row.is-delete .line-diff-cell:first-child { background: rgba(245, 108, 108, .1); }
.line-diff-row.is-insert .line-diff-cell:last-child { background: rgba(103, 194, 58, .1); }
.line-diff-cell.is-empty { color: #909399; font-style: italic; background: #fafafa !important; }
.diff-results { margin-top: 16px; display: flex; flex-direction: column; gap: 10px; }
.diff-item {
  padding: 10px 12px;
  border-radius: 6px;
  border-left: 3px solid #faad14;
  background: #fffbe6;
  font-family: monospace;
  font-size: 13px;
}
.diff-item[role="button"] {
  cursor: pointer;
  transition: box-shadow .2s, transform .2s;
}
.diff-item[role="button"]:hover {
  box-shadow: 0 6px 18px rgba(15, 23, 42, .08);
  transform: translateY(-1px);
}
.diff-item.is-active-diff {
  outline: 2px solid rgba(22, 119, 255, .35);
  box-shadow: 0 8px 22px rgba(22, 119, 255, .12);
}
.diff-item-head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
.diff-index {
  color: #1677ff;
  font-weight: 700;
}
.diff-action-tip {
  margin-left: auto;
  color: #909399;
  font-family: inherit;
}
.diff-content-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.diff-side {
  min-width: 0;
}
.diff-side-title {
  margin-bottom: 4px;
  color: #606266;
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
}
.diff-side-lines {
  margin-bottom: 6px;
  color: #909399;
  font-family: SFMono-Regular, Consolas, Monaco, monospace;
  font-size: 12px;
}
.diff-text {
  margin: 0;
  padding: 8px 10px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
  min-height: 34px;
}
.diff-left { color: #f56c6c; background: rgba(245, 108, 108, .08); }
.diff-right { color: #67c23a; background: rgba(103, 194, 58, .08); }
.same-result { text-align: center; padding: 20px; color: #67c23a; }
@media (max-width: 900px) {
  .translation-layout,
  .diff-editor-layout,
  .diff-content-grid { grid-template-columns: 1fr; }
  .swap-column { order: 2; }
}
</style>
