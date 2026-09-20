<template>
  <el-dialog
    :model-value="modelValue"
    title="从响应中选取字段"
    width="92vw"
    top="8vh"
    class="jsonpath-picker-dialog"
    append-to-body
    :close-on-click-modal="false"
    @update:model-value="updateVisible"
  >
    <div class="picker-body">
      <div class="picker-expression">
        <el-input
          v-model="draft"
          class="expression-readonly"
          placeholder="请在下方选择字段，或返回断言处修改"
          readonly
        >
          <template #prepend>表达式</template>
        </el-input>
        <el-button :loading="loading" @click="reload">重新请求</el-button>
      </div>

      <!-- 新增、修改、删除类接口直接请求就是真实写库，不替用户自动发 -->
      <div v-if="awaitingManualFetch" class="picker-manual-fetch">
        <p class="picker-manual-fetch__text">
          <span>获取响应示例会真实调用当前接口，一次可勾选和提取多个字段。</span>
          <br />
          <span>确认请点击</span>
          <el-button class="manual-fetch-button" type="primary" link size="small" @click="reload">
            <el-icon><Plus /></el-icon>
            重新请求
          </el-button>
          <span>获取和提取响应数据。</span>
        </p>
      </div>

      <template v-else>
        <div class="picker-preview">
          <div v-if="previewItems.length" class="preview-head">
            <span v-if="checkedNodes.length" class="preview-selected-count">
              <span class="preview-selected-count__label">已选</span>
              <strong class="preview-selected-count__number">{{ checkedNodes.length }}</strong>
            </span>
            <div v-if="previewItems.length" class="preview-tabs" role="tablist" aria-label="取值字段">
              <div
                v-for="(item, index) in previewItems"
                :key="item.path"
                class="preview-tab"
                :class="{ 'is-active': index === activePreviewIndex }"
                :title="item.path"
                role="tab"
                tabindex="0"
                :aria-selected="index === activePreviewIndex"
                @click="selectPreview(index)"
                @keydown.enter="selectPreview(index)"
                @keydown.space.prevent="selectPreview(index)"
              >
                <span class="preview-tab-label">{{ item.label }}</span>
                <button
                  type="button"
                  class="preview-tab-close"
                  :aria-label="`取消选择 ${item.label}`"
                  title="取消选择"
                  @click.stop="removePreview(item)"
                ><el-icon><Close /></el-icon></button>
              </div>
            </div>
            <div v-if="previewItems.length" class="preview-actions">
              <el-button
                class="preview-nav"
                size="small"
                :disabled="activePreviewIndex <= 0"
                aria-label="上一个字段"
                @click="previousPreview"
              ><el-icon><ArrowLeft /></el-icon></el-button>
              <el-button
                class="preview-nav"
                size="small"
                :disabled="activePreviewIndex >= previewItems.length - 1"
                aria-label="下一个字段"
                @click="nextPreview"
              ><el-icon><ArrowRight /></el-icon></el-button>
              <el-button v-if="canCopyValue" class="preview-copy" type="primary" link size="small" @click="copyValue">
                复制
              </el-button>
            </div>
          </div>
          <pre v-if="!previewItems.length" class="preview-value is-hint">请先在下方选择字段，或直接输入表达式</pre>
          <pre v-else-if="evaluating" class="preview-value is-hint">取值中…</pre>
          <pre v-else class="preview-value">{{ activePreviewText }}</pre>
        </div>

        <el-alert v-if="errorText" :title="errorText" type="error" :closable="false" show-icon />

        <div v-loading="loading" class="picker-tree" element-loading-text="正在请求接口…">
          <div v-if="tree" class="field-search">
            <el-input
              v-model="searchQuery"
              class="field-search-input"
              size="small"
              clearable
              placeholder="搜索字段名或值"
              aria-label="搜索字段名或值"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <span class="field-search-count">{{ searchMatches.length ? `${searchIndex + 1}/${searchMatches.length}` : '0/0' }}</span>
            <el-button
              class="field-search-nav"
              text
              size="small"
              :disabled="!searchMatches.length"
              aria-label="上一个搜索结果"
              @click="moveSearch(-1)"
            ><el-icon><ArrowUp /></el-icon></el-button>
            <el-button
              class="field-search-nav"
              text
              size="small"
              :disabled="!searchMatches.length"
              aria-label="下一个搜索结果"
              @click="moveSearch(1)"
            ><el-icon><ArrowDown /></el-icon></el-button>
          </div>
          <div v-if="tree" class="picker-tree-content">
            <ul class="tree-root">
              <template v-if="Array.isArray(tree.children) && tree.children.length">
                <TreeNode
                  v-for="(node, index) in tree.children"
                  :key="node.path || index"
                  :node="node"
                  :selected-path="draft"
                  checkable
                  :checked-paths="checkedPaths"
                  :search-text="searchQuery"
                  :search-match-paths="searchMatchPaths"
                  :search-active-path="activeSearchPath"
                  :preview-active-path="activePreviewPath"
                  @select="onSelect"
                  @check="onCheck"
                />
              </template>
              <TreeNode
                v-else
                :node="tree"
                :selected-path="draft"
                checkable
                :checked-paths="checkedPaths"
                :search-text="searchQuery"
                :search-match-paths="searchMatchPaths"
                :search-active-path="activeSearchPath"
                :preview-active-path="activePreviewPath"
                @select="onSelect"
                @check="onCheck"
              />
            </ul>
          </div>
          <el-empty v-else-if="!loading && !errorText" description="暂无响应数据" :image-size="72" />
        </div>
      </template>
    </div>

    <template #footer>
      <template v-if="selectionMode">
        <el-button v-if="loading" @click="cancelReload">取消请求</el-button>
        <el-button @click="closeDialog">取消</el-button>
        <el-button type="primary" :disabled="loading || !tree" @click="confirmSelection">
          确定选择（{{ checkedNodes.length }}）
        </el-button>
      </template>
      <template v-else>
        <!-- 勾选多个字段时一次生成多条断言，不影响原有的单条表达式使用方式 -->
        <template v-if="isBatch">
          <el-button v-if="loading" @click="cancelReload">取消请求</el-button>
          <el-button @click="closeDialog">取消</el-button>
          <el-button type="primary" @click="confirmMany">添加 {{ checkedNodes.length }} 条断言</el-button>
        </template>
        <template v-else>
          <el-button v-if="loading" @click="cancelReload">取消请求</el-button>
          <el-button @click="closeDialog">取消</el-button>
          <!-- 取值还没回来就点，期望值会填不上，这里等取值结束再放开 -->
          <el-button
            type="primary"
            :loading="evaluating"
            :disabled="!draft.trim()"
            @click="confirm"
          >
            使用该表达式
          </el-button>
        </template>
      </template>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch, nextTick, onBeforeUnmount } from 'vue'
import TreeNode from '@/views/tools/TreeNode.vue'
import { inspectJsonResponse } from '@/api/tools'
import { formatAssertionActual } from '@/utils/executionResult'
import { useCopyText } from '@/composables/useCopyText'
import { Plus, Search, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Close } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // 断言当前的表达式，打开时作为初始值
  expression: { type: String, default: '' },
  // 是否按当前用例的全部 JSONPath 断言同步勾选结果
  selectionMode: { type: Boolean, default: false },
  // 当前用例已有的断言，打开字段树后按 JSONPath 回显勾选状态
  selectedAssertions: { type: Array, default: () => [] },
  // 由外层提供：执行一次请求并返回响应体文本；返回空表示取不到（外层已自行提示）
  loader: { type: Function, default: null },
  // 请求方法：只有查询类方法才在打开时自动请求，其余方法交由用户确认后手动请求
  method: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'confirm', 'confirm-many', 'confirm-selection'])

const { copyText } = useCopyText()

const draft = ref('')
const responseText = ref('')
const tree = ref(null)
const found = ref(false)
const valueText = ref('')
// 回填期望值要判断类型，展示用的文本不够，另存一份原始值
const rawValue = ref(undefined)
const loading = ref(false)
const evaluating = ref(false)
const errorText = ref('')
// 批量选取的字段节点：节点上带了值和类型，生成断言时直接用，不必再逐个取值
const checkedNodes = ref([])
const searchQuery = ref('')
const searchIndex = ref(0)
// 非查询类方法打开时不自动请求，停在等待用户确认的状态
const awaitingManualFetch = ref(false)

let evaluateTimer = null
let activeController = null
const REQUEST_TIMEOUT_MS = 30 * 1000

const checkedPaths = computed(() => checkedNodes.value.map(item => item.path))
const isBatch = computed(() => checkedNodes.value.length > 1)
const searchTextOf = node => {
  const values = [node?.label, node?.preview]
  if (Object.prototype.hasOwnProperty.call(node || {}, 'value')) {
    const value = node.value
    if (value !== undefined) {
      if (typeof value === 'object' && value !== null) {
        try {
          values.push(JSON.stringify(value))
        } catch {
          values.push(String(value))
        }
      } else {
        values.push(String(value))
      }
    }
  }
  return values.filter(value => value !== undefined && value !== null).join(' ').toLowerCase()
}
const searchMatches = computed(() => {
  const keyword = searchQuery.value.trim().toLowerCase()
  if (!keyword || !tree.value) return []

  const matches = []
  const visit = (node, isRoot = false) => {
    if (!node) return
    if (!isRoot && searchTextOf(node).includes(keyword)) matches.push(node)
    if (Array.isArray(node.children)) node.children.forEach(child => visit(child))
  }
  visit(tree.value, true)
  return matches
})
const searchMatchPaths = computed(() => searchMatches.value.map(node => String(node.path || '').trim()).filter(Boolean))
const activeSearchPath = computed(() => String(searchMatches.value[searchIndex.value]?.path || '').trim())
const selectedAssertionPaths = computed(() => new Set(
  (props.selectedAssertions || [])
    .filter(item => !item?.type || item.type === 'jsonpath')
    .map(item => String(item?.expression || '').trim())
    .filter(Boolean)
))

const activePreviewIndex = ref(0)

const previewLabel = (node, path) => {
  const label = String(node?.label || '').trim()
  if (label) return label
  const normalizedPath = String(path || '').trim()
  const matches = normalizedPath.match(/(?:^|[.\[])([^.\[\]]+)\]?$/)
  return matches?.[1] || normalizedPath || '字段'
}

const nodePreview = node => {
  const hasValue = Object.prototype.hasOwnProperty.call(node || {}, 'value')
  return {
    path: String(node?.path || '').trim(),
    label: previewLabel(node, node?.path),
    text: hasValue ? formatAssertionActual(node.value, true) : '—',
    found: hasValue,
  }
}

const previewItems = computed(() => {
  const selected = checkedNodes.value.filter(item => item?.path)
  if (props.selectionMode) return selected.map(nodePreview)
  if (selected.length > 1) return selected.map(nodePreview)
  if (selected.length === 1 && selected[0].path === draft.value.trim()) return selected.map(nodePreview)
  if (!draft.value.trim()) return []
  return [{
    path: draft.value.trim(),
    label: previewLabel(null, draft.value),
    text: found.value ? valueText.value : '—',
    found: found.value,
  }]
})

const activePreview = computed(() => previewItems.value[activePreviewIndex.value] || null)
const activePreviewPath = computed(() => String(activePreview.value?.path || '').trim())
const activePreviewText = computed(() => activePreview.value?.text ?? '—')
const canCopyValue = computed(() => Boolean(responseText.value) && activePreview.value?.found === true && !evaluating.value)

const resetState = () => {
  tree.value = null
  responseText.value = ''
  found.value = false
  valueText.value = ''
  rawValue.value = undefined
  errorText.value = ''
  activePreviewIndex.value = 0
  searchQuery.value = ''
  searchIndex.value = 0
  // 重新请求后字段树整体重建，旧的勾选可能已经不存在，一并清掉
  checkedNodes.value = []
}

const restoreCheckedNodes = () => {
  if (!props.selectionMode) return
  const selectedPaths = selectedAssertionPaths.value
  const nodes = []
  const visit = node => {
    if (!node) return
    if (selectedPaths.has(String(node.path || '').trim())) nodes.push(node)
    if (Array.isArray(node.children)) node.children.forEach(visit)
  }
  visit(tree.value)
  checkedNodes.value = nodes
}

// 拉响应并生成字段树；表达式已填时顺带带上，少一次往返
const reload = async () => {
  if (typeof props.loader !== 'function' || loading.value) return
  resetState()
  awaitingManualFetch.value = false
  loading.value = true
  const controller = new AbortController()
  activeController = controller
  let timeoutId = null
  let text = ''
  try {
    // 请求失败、未选环境等原因由外层按各自场景提示，这里不再重复提示
    const timeoutPromise = new Promise((_, reject) => {
      timeoutId = setTimeout(() => {
        controller.abort()
        reject(new Error('获取响应示例超时，请重试'))
      }, REQUEST_TIMEOUT_MS)
    })
    text = await Promise.race([props.loader({ signal: controller.signal }), timeoutPromise])
  } catch (error) {
    if (!controller.signal.aborted || error?.message?.includes('超时')) {
      errorText.value = error?.message || '获取响应示例失败'
    }
    return
  } finally {
    if (timeoutId) clearTimeout(timeoutId)
    if (activeController === controller) activeController = null
    loading.value = false
  }
  if (!text) {
    return
  }
  try {
    responseText.value = text
    const data = await inspectJsonResponse({
      response: text,
      expression: draft.value.trim(),
      include_tree: true,
    })
    tree.value = data?.tree || null
    restoreCheckedNodes()
    applyResult(data)
  } catch (error) {
    errorText.value = error?.data?.message || error?.message || '解析响应失败'
  } finally {
  }
}

const cancelReload = () => {
  if (!activeController) return
  activeController.abort()
  activeController = null
  loading.value = false
  errorText.value = '已取消获取响应示例'
  if (!responseText.value) awaitingManualFetch.value = true
}

const closeDialog = () => {
  cancelReload()
  emit('update:modelValue', false)
}

const updateVisible = value => {
  if (!value) cancelReload()
  emit('update:modelValue', value)
}

const applyResult = (data) => {
  found.value = data?.found === true
  valueText.value = formatAssertionActual(data?.value, found.value)
  rawValue.value = found.value ? data?.value : undefined
}

// 只重算取值，不重建字段树，避免手改表达式时树的展开状态被重置
const evaluate = async () => {
  const expression = draft.value.trim()
  if (!responseText.value || !expression) {
    found.value = false
    valueText.value = ''
    rawValue.value = undefined
    return
  }
  evaluating.value = true
  try {
    const data = await inspectJsonResponse({
      response: responseText.value,
      expression,
      include_tree: false,
    })
    applyResult(data)
  } catch (error) {
    errorText.value = error?.data?.message || error?.message || '取值失败'
  } finally {
    evaluating.value = false
  }
}

const scheduleEvaluate = () => {
  if (evaluateTimer) clearTimeout(evaluateTimer)
  evaluateTimer = setTimeout(evaluate, 300)
}

const onSelect = (node) => {
  if (!node?.path) return
  draft.value = node.path
}

// 勾中一个时等同于选中它（底部仍是单条按钮），勾到第二个才切换成批量
const onCheck = ({ node, checked }) => {
  if (!node?.path) return
  const index = checkedNodes.value.findIndex(item => item.path === node.path)
  if (checked && index === -1) {
    checkedNodes.value.push(node)
    activePreviewIndex.value = checkedNodes.value.length - 1
    draft.value = node.path
  }
  if (!checked && index !== -1) {
    checkedNodes.value.splice(index, 1)
    activePreviewIndex.value = Math.min(activePreviewIndex.value, Math.max(checkedNodes.value.length - 1, 0))
    draft.value = ''
  }
}

const removePreview = (item) => {
  if (!item?.path) return
  const index = checkedNodes.value.findIndex(node => node.path === item.path)
  const wasChecked = index !== -1

  if (wasChecked) {
    checkedNodes.value.splice(index, 1)
    if (index < activePreviewIndex.value) activePreviewIndex.value -= 1
  }

  // 关闭 Tab 等同于取消当前字段，沿用取消勾选后清空表达式的规则。
  draft.value = ''
  activePreviewIndex.value = Math.min(
    activePreviewIndex.value,
    Math.max(previewItems.value.length - 1, 0),
  )
}

const scrollToSearchResult = () => {
  if (!activeSearchPath.value) return
  nextTick(() => {
    const result = document.querySelector('.picker-tree .search-active')
    result?.scrollIntoView({ block: 'nearest' })
  })
}

const scrollToPreviewField = () => {
  if (!activePreviewPath.value) return
  nextTick(() => {
    const rows = document.querySelectorAll('.picker-tree [data-preview-path]')
    const result = Array.from(rows).find(row => row.getAttribute('data-preview-path') === activePreviewPath.value)
    result?.scrollIntoView({ block: 'nearest' })
  })
}

const selectPreview = index => {
  const item = previewItems.value[index]
  if (!item?.path) return
  activePreviewIndex.value = index
  draft.value = item.path
  scrollToPreviewField()
}

const previousPreview = () => {
  selectPreview(Math.max(0, activePreviewIndex.value - 1))
}

const nextPreview = () => {
  selectPreview(Math.min(previewItems.value.length - 1, activePreviewIndex.value + 1))
}

const moveSearch = direction => {
  const total = searchMatches.value.length
  if (!total) return
  searchIndex.value = (searchIndex.value + direction + total) % total
  scrollToSearchResult()
}

const copyValue = () => copyText(activePreviewText.value)

// 期望值输入框存的是文本：布尔与数字按原文转写，对象、数组、null 按 JSON 文本回填。
// 断言执行时会把期望值当 JSON 解析后与实际值整体比较，所以 JSON 文本能真正生效。
// 只有「字段没取到」才返回空，表示不填期望值。
const buildFillFromValue = (value) => {
  if (value === undefined) return null
  if (typeof value === 'string') return { expected: value }
  if (typeof value === 'number' || typeof value === 'boolean') return { expected: String(value) }
  try {
    return { expected: JSON.stringify(value) }
  } catch {
    return null
  }
}

// 与批量口径一致：取到什么就填什么，对象与数组按 JSON 文本回填
const confirm = () => {
  const expression = draft.value.trim()
  if (!expression) return
  emit('confirm', expression, buildFillFromValue(rawValue.value))
  emit('update:modelValue', false)
}

const confirmMany = () => {
  const items = checkedNodes.value
    .filter(item => item?.path)
    .map(item => ({ expression: item.path, fill: buildFillFromValue(item.value) }))
  if (!items.length) return
  emit('confirm-many', items)
  emit('update:modelValue', false)
}

// 确认后把勾选结果交给外层同步当前表单；空数组也要提交，表示临时删除全部 JSONPath 断言
const confirmSelection = () => {
  const items = checkedNodes.value
    .filter(item => item?.path)
    .map(item => ({ expression: item.path, fill: buildFillFromValue(item.value) }))
  emit('confirm-selection', items)
  emit('update:modelValue', false)
}

watch(() => props.modelValue, (visible) => {
  if (!visible) return
  draft.value = props.expression || ''
  // 所有方法都先由用户确认后手动请求，避免打开断言选择器就触发真实接口调用。
  resetState()
  awaitingManualFetch.value = true
})

watch(draft, () => {
  if (!props.modelValue) return
  scheduleEvaluate()
})

watch(searchMatches, matches => {
  searchIndex.value = 0
  if (matches.length) scrollToSearchResult()
})

watch(activePreviewPath, scrollToPreviewField, { flush: 'post' })

onBeforeUnmount(() => {
  if (evaluateTimer) clearTimeout(evaluateTimer)
})
</script>

<style scoped>
.picker-body { display: flex; flex-direction: column; gap: 14px; min-height: 0; }
.picker-expression { display: flex; align-items: center; gap: 8px; }
.picker-expression .el-input { flex: 1 1 auto; min-width: 0; }
.picker-expression .el-button { flex-shrink: 0; }
.expression-readonly :deep(.el-input__wrapper) { background: #f5f7fa; }
.expression-readonly :deep(.el-input__inner) { cursor: default; }
.manual-fetch-button { margin: 0 4px; padding: 3px 4px; vertical-align: middle; font-weight: 600; }

.picker-manual-fetch {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 280px;
  box-sizing: border-box;
  padding: 24px;
  border: 1px solid #e5eaf3;
  border-radius: 8px;
  background: #fafcff;
}
.picker-manual-fetch__text {
  max-width: 720px;
  margin: 0;
  color: #606266;
  font-size: 13px;
  line-height: 1.8;
  text-align: center;
}

.picker-preview {
  border: 1px solid #dcdfe6;
  border-top: 1px solid #dcdfe6;
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
}
.preview-head {
  display: flex;
  align-items: stretch;
  gap: 0;
  min-width: 0;
  min-height: 46px;
  padding: 0 8px;
  background: #fbfcff;
  border-bottom: 1px solid #e5eaf3;
}
.preview-tabs {
  display: flex;
  flex: 1 1 auto;
  align-items: stretch;
  min-width: 0;
  gap: 1px;
  padding: 4px 0;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: #c4c7cc transparent;
}
.preview-tabs::-webkit-scrollbar { height: 4px; }
.preview-tabs::-webkit-scrollbar-track { background: transparent; }
.preview-tabs::-webkit-scrollbar-thumb { border-radius: 999px; background: #c4c7cc; }
.preview-tabs::-webkit-scrollbar-thumb:hover { background: #a8abb2; }
.preview-tab {
  position: relative;
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 0 0 92px;
  width: 92px;
  min-width: 0;
  height: 34px;
  padding: 0 5px 0 8px;
  overflow: hidden;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #606266;
  font: inherit;
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
}
.preview-tab:focus-visible {
  outline: 2px solid #409eff;
  outline-offset: -2px;
}
.preview-tab-label {
  min-width: 0;
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.preview-tab-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 20px;
  width: 20px;
  height: 20px;
  padding: 0;
  border: 0;
  border-radius: 3px;
  background: transparent;
  color: #a8abb2;
  opacity: 0;
  cursor: pointer;
}
.preview-tab:hover .preview-tab-close,
.preview-tab.is-active .preview-tab-close,
.preview-tab:focus-within .preview-tab-close { opacity: 1; }
.preview-tab-close:hover { color: #f56c6c; background: #fef0f0; }
.preview-selected-count {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  align-self: center;
  min-width: 54px;
  margin-right: 8px;
  padding: 0 10px 0 2px;
  border-right: 1px solid #e5eaf3;
  color: #606266;
  font-size: 12px;
  line-height: 28px;
  white-space: nowrap;
}
.preview-selected-count__label { color: #909399; }
.preview-selected-count__number {
  color: #2563eb;
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.preview-tab:not(:first-child)::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 0;
  width: 1px;
  height: 18px;
  transform: translateY(-50%);
  background: #e6eaf0;
  pointer-events: none;
}
.preview-tab:hover { color: #2563eb; background: #f5f9ff; }
.preview-tab.is-active {
  color: #2563eb;
  font-weight: 600;
  background: #eef5ff;
  box-shadow: inset 0 -2px #409eff;
}
.preview-actions {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 4px;
  margin-left: 8px;
  padding-left: 8px;
  border-left: 1px solid #e5eaf3;
}
.preview-nav {
  width: 28px;
  height: 26px;
  padding: 0;
  border-color: #dcdfe6;
  color: #606266;
  background: #fff;
}
.preview-nav:not(.is-disabled):hover {
  border-color: #a0cfff;
  color: #409eff;
  background: #f5f9ff;
}
.preview-copy { margin-left: 2px; padding: 3px 4px; }
/* 用块级 pre 承载取值结果，滚动条才会落在容器右侧、而不是浮在内容上方 */
.preview-value {
  display: block;
  width: 100%;
  margin: 0;
  padding: 10px 12px;
  height: 132px;
  box-sizing: border-box;
  overflow: auto;
  color: #303133;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
}
.preview-value.is-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-family: inherit;
  font-size: 13px;
  text-align: center;
}

.picker-tree {
  display: flex;
  flex-direction: column;
  height: 44vh;
  min-height: 220px;
  max-height: 44vh;
  overflow: hidden;
  border: 1px solid #e5eaf3;
  border-radius: 6px;
  padding: 8px;
}
.field-search {
  position: relative;
  z-index: 1;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 4px;
  margin: -8px -8px 8px;
  padding: 8px;
  background: #fff;
  border-bottom: 1px solid #f0f2f5;
}
.picker-tree-content {
  min-height: 0;
  flex: 1 1 auto;
  overflow: auto;
}
.field-search-input { flex: 1 1 auto; min-width: 0; }
.field-search-count {
  flex: 0 0 auto;
  min-width: 42px;
  color: #909399;
  font-size: 12px;
  line-height: 24px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.field-search-nav { flex: 0 0 24px; width: 24px; height: 24px; padding: 0; }
.tree-root { margin: 0; padding: 0; }
.picker-tree :deep(.el-empty) { margin: 0; padding: 28px 0; }
</style>

<style>
.jsonpath-picker-dialog { max-width: 960px; }
.jsonpath-picker-dialog .el-dialog__body { padding-top: 10px; }
</style>
