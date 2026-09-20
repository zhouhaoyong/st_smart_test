<template>
  <div v-if="diffs.length" class="assert-table">
    <div class="assert-table-head">
      <span>结果</span>
      <span>断言</span>
      <span>操作符</span>
      <span>期望值</span>
      <span>实际值</span>
    </div>
    <div
      v-for="(diff, index) in diffs"
      :key="index"
      :class="['assert-table-row', diff.result === 'pass' ? 'assert-pass' : 'assert-fail']"
    >
      <span>
        <el-tag :type="diff.result === 'pass' ? 'success' : 'danger'" size="small" effect="plain">
          {{ diff.result === 'pass' ? '通过' : '失败' }}
        </el-tag>
      </span>
      <span class="assert-name">{{ assertionLabel(diff) }}</span>
      <span>{{ getAssertionOperatorLabel(diff.operator) }}</span>
      <span class="assert-val expected-val">{{ expectedText(diff) }}</span>
      <span :class="['assert-val', diff.result === 'pass' ? 'actual-pass' : 'actual-fail']">{{ actualText(diff) }}</span>
    </div>
  </div>
  <div v-else class="empty-inline">{{ emptyText }}</div>
</template>

<script setup>
import { getAssertionOperatorLabel, assertionOperatorNeedsExpected } from '@/utils/assertionOperators'
import { formatAssertionActual } from '@/utils/executionResult'

const props = defineProps({
  diffs: { type: Array, default: () => [] },
  emptyText: { type: String, default: '暂无断言结果' },
})

const assertionLabel = (diff) => {
  if (diff?.type === 'jsonpath') return diff.expression || 'JSONPath'
  if (diff?.type === 'status_code') return '状态码'
  if (diff?.type === 'response_time') return '响应时间'
  if (diff?.type === 'contains') return '包含文本'
  return diff?.type || '断言'
}

// 「非空」这类操作符不需要期望值，期望值列显示占位符而不是留白
const expectedText = (diff) => {
  if (!assertionOperatorNeedsExpected(diff?.operator)) return '—'
  return stringifyPretty(diff?.expected)
}

const actualText = (diff) => formatAssertionActual(diff?.actual, diff?.actual_found !== false)

const stringifyPretty = (value) => {
  if (value == null || value === '') return ''
  if (typeof value === 'string') return value
  try { return JSON.stringify(value, null, 2) } catch { return String(value) }
}
</script>

<style scoped>
.assert-table { border: 1px solid #e5eaf3; border-radius: 6px; overflow: hidden; }
.assert-table-head, .assert-table-row {
  display: grid;
  grid-template-columns: 90px minmax(180px, 1.2fr) 110px minmax(160px, 1fr) minmax(160px, 1fr);
  gap: 10px;
  align-items: center;
}
.assert-table-head {
  padding: 9px 12px;
  color: #606266;
  font-size: 12px;
  background: #f5f7fa;
  border-bottom: 1px solid #e5eaf3;
}
.assert-table-row { padding: 10px 12px; border-bottom: 1px solid #edf1f7; font-size: 13px; }
.assert-table-row:last-child { border-bottom: none; }
.assert-table-row.assert-fail { background: #fff7f7; }
.assert-name { color: #303133; word-break: break-all; }
.assert-val { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: monospace; font-size: 12px; }
.expected-val { color: #1677ff; }
.actual-pass { color: #67c23a; }
.actual-fail { color: #f56c6c; }
.empty-inline { padding: 22px; color: #909399; text-align: center; background: #fafafa; border-radius: 6px; }
@media (max-width: 768px) {
  .assert-table-head, .assert-table-row { grid-template-columns: 70px minmax(120px, 1fr) 70px minmax(120px, 1fr) minmax(120px, 1fr); }
}
</style>
