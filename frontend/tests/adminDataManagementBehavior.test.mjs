import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8')

test('audit log delete-all uses the last applied query and supports initial results', () => {
  const source = read('../src/views/AuditLogs.vue')

  assert.match(source, /appliedSearchForm/)
  assert.match(source, /filtersDirty/)
  assert.match(source, /canDeleteAll = computed\(\(\) => isSuperAdmin\.value && hasLoaded\.value && !filtersDirty\.value/)
  assert.doesNotMatch(source, /canDeleteAll = computed\(\(\) => isSuperAdmin\.value && searched\.value/)
  assert.match(source, /style="width:260px"/)
})

test('usage record delete-all uses the last applied query and supports initial results', () => {
  const source = read('../src/views/admin/AiUsage.vue')

  assert.match(source, /appliedLogFilters/)
  assert.match(source, /logFiltersDirty/)
  assert.match(source, /canDeleteAllLogs = computed\(\(\) => canViewAllAiData\.value && logsLoaded\.value && !logFiltersDirty\.value/)
  assert.doesNotMatch(source, /canDeleteAllLogs = computed\(\(\) => canViewAllAiData\.value && logsSearched\.value/)
})

test('cleanup details remain clickable when the pending count is zero', () => {
  const source = read('../src/views/DataCleanup.vue')

  assert.doesNotMatch(source, /@click="viewTableData\(row\.table_name\)"[\s\S]{0,180}:disabled="row\.pending_count === 0"/)
  assert.match(source, /@row-click="handleTableRowClick"/)
  assert.match(source, /@click\.stop="handleDeleteSingleTable\(row\)"/)
  assert.match(source, /cleanup-preview-table[\s\S]*cleanup-action-cell/)
  assert.match(source, /暂无待清理数据/)
  assert.match(source, /display_columns/)
})

test('dense admin list toolbars keep actions in a wrapped row with balanced spacing', () => {
  const users = read('../src/views/Users.vue')
  const auditLogs = read('../src/views/AuditLogs.vue')
  const aiModels = read('../src/views/admin/AiModels.vue')
  const aiUsage = read('../src/views/admin/AiUsage.vue')

  for (const source of [users, auditLogs, aiModels, aiUsage]) {
    assert.match(source, /flex-wrap: wrap/)
    assert.match(source, /gap: 10px 12px/)
  }

  assert.doesNotMatch(aiModels, /\.toolbar-button-item \{[^}]*overflow-x:\s*auto/)
  assert.doesNotMatch(aiUsage, /\.stats-filter-bar \{[^}]*overflow-x:\s*auto/)
  assert.doesNotMatch(aiUsage, /\.log-search-form \{[^}]*overflow-x:\s*auto/)
})

test('platform user management uses compact status and role filters', () => {
  const source = read('../src/views/Users.vue')
  const endpoint = read('../../backend/api/v1/endpoints/users.py')
  const searchArea = source.slice(source.indexOf('<div class="search-area">'), source.indexOf('<div class="scroll-area"'))
  const table = source.slice(source.indexOf('<el-table'), source.indexOf('</el-table>'))

  assert.match(source, /style="width:120px"/)
  assert.match(searchArea, /label="状态"[\s\S]*searchForm\.is_active/)
  assert.match(searchArea, /label="角色"[\s\S]*超级管理员[\s\S]*管理员[\s\S]*普通用户/)
  assert.doesNotMatch(searchArea, /<el-form-item label="管理员"|<el-form-item label="超级管理员"/)
  assert.match(table, /label="角色"/)
  assert.doesNotMatch(table, /label="管理员"|label="超级管理员"/)
  assert.match(endpoint, /role: str \| None = None/)
  assert.match(endpoint, /is_active: bool \| None = None/)
  assert.match(endpoint, /role == 'superuser'[\s\S]*User\.is_superuser == True/)
  assert.match(endpoint, /role == 'manager'[\s\S]*User\.is_superuser == False[\s\S]*User\.is_manager == True/)
  assert.match(endpoint, /role == 'normal'[\s\S]*User\.is_superuser == False[\s\S]*User\.is_manager == False/)
  assert.match(endpoint, /User\.is_active == is_active/)
})

test('AI model tabs keep compact filters on one row and omit platform creator search', () => {
  const source = read('../src/views/admin/AiModels.vue')

  assert.match(source, /class="model-name-filter"/)
  assert.match(source, /class="model-identifier-filter"/)
  assert.match(source, /class="model-status-filter filter-select"/)
  assert.match(source, /class="model-capability-filter filter-select"/)
  assert.match(source, /<el-form-item v-if="isUserModelsTab" label="模型使用人">/)
  assert.doesNotMatch(source, /<el-form-item v-if="showCreatorColumn \|\| isUserModelsTab"/)
  assert.match(source, /\.toolbar-button-item \{ flex: 0 0 auto; width: auto;/)
  assert.doesNotMatch(source, /\.toolbar-button-item \{ flex-basis: 100%; width: 100%;/)
})

test('AI model selection does not gate on capability detection and retry requires a chosen model', () => {
  const adminSource = read('../src/views/admin/AiModels.vue')
  const confirmSource = read('../src/views/test-workbench/components/RefinementStartConfirm.vue')
  const modelSelectionSource = read('../src/views/test-workbench/components/AiModelSelectionPanel.vue')
  const cardSource = read('../src/views/test-workbench/components/RefinementMessageCard.vue')
  const refinementSource = read('../src/views/test-workbench/composables/useRequirementRefinement.js')

  assert.doesNotMatch(adminSource, /使用权重|功能权重|setAiModelWeight|weightValue|weightRow/)
  assert.match(adminSource, /系统默认优先使用平台模型/)
  assert.doesNotMatch(confirmSource, /仅本次使用，不会修改已保存的功能权重/)
  assert.match(modelSelectionSource, /modelScopeText/)
  assert.match(modelSelectionSource, /平台模型/)
  assert.match(modelSelectionSource, /我的模型/)
  assert.match(cardSource, /retryCandidates/)
  assert.match(cardSource, /选择模型重试/)
  assert.match(refinementSource, /const retry = async retrySelection/)
  assert.doesNotMatch(refinementSource, /const personalRetryModel = action\.platformModelUnavailable/)
})
