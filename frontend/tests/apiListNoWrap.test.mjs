import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = relativePath => fs.readFileSync(new URL(relativePath, import.meta.url), 'utf8')

test('接口名称区域应从左侧开始并只在右侧溢出', () => {
  const source = read('../src/views/Interfaces.vue')
  const cellStyle = source.match(/\.interface-table-scroll :deep\(\.interface-name-url-cell\)\s*\{([^}]*)\}/)?.[1] || ''
  const nameStyle = source.match(/\.interface-table-scroll :deep\(\.interface-name-text\)\s*\{([^}]*)\}/)?.[1] || ''

  assert.match(cellStyle, /display:\s*block/)
  assert.match(cellStyle, /width:\s*100%/)
  assert.match(cellStyle, /box-sizing:\s*border-box/)
  assert.match(nameStyle, /min-width:\s*0/)
  assert.match(nameStyle, /width:\s*100%/)
  assert.match(nameStyle, /justify-content:\s*flex-start/)
  assert.match(nameStyle, /text-align:\s*left/)
})

test('接口主列表的长文本列必须单行省略并支持完整查看', () => {
  const source = read('../src/views/Interfaces.vue')

  assert.match(source, /<el-table-column label="接口名称\/URL" width="200" fixed="left"/)
  assert.match(source, /class="interface-name-url-cell"/)
  assert.match(source, /class="interface-name-text"[\s\S]*row\.name/)
  assert.match(source, /class="interface-url-text"[\s\S]*row\.url/)
  assert.match(source, /<el-table-column type="selection" width="45" fixed="left" \/>/)
  assert.match(source, /<el-table-column label="接口名称\/URL" width="200" fixed="left"/)
  assert.match(source, /prop="collection_name"[\s\S]{0,120}show-overflow-tooltip/)
  assert.match(source, /class="interface-table-scroll"/)
  assert.match(source, /\.interface-table-scroll[\s\S]{0,360}white-space:\s*nowrap/)
})

test('接口主列表默认展示 100 条，并提供 10、50、100 三档分页', () => {
  const source = read('../src/views/Interfaces.vue')

  assert.match(source, /:page-sizes="\[10, 50, 100\]"/)
  assert.match(source, /const pageSize = ref\(10\)/)
})

test('接口主列表名称链接的下划线应按名称文本宽度收缩', () => {
  const source = read('../src/views/Interfaces.vue')
  const nameStyle = source.match(/\.interface-table-scroll :deep\(\.interface-name-text\)\s*\{([^}]*)\}/)?.[1] || ''

  assert.match(nameStyle, /display:\s*inline-flex/)
  assert.doesNotMatch(nameStyle, /display:\s*block/)
  assert.match(nameStyle, /width:\s*auto/)
  assert.match(nameStyle, /max-width:\s*100%/)
  assert.doesNotMatch(nameStyle, /(?:^|\n)\s*width:\s*100%/)
})

test('接口主列表按业务顺序展示字段，并将行操作收进下拉菜单', () => {
  const source = read('../src/views/Interfaces.vue')
  const tableStart = source.indexOf('<el-table v-if="interfaceList.length"')
  const tableEnd = source.indexOf('</el-table>', tableStart)
  const table = source.slice(tableStart, tableEnd)

  assert.doesNotMatch(table, /prop="description"\s+label="描述"/)
  const orderedLabels = ['接口名称/URL', '用例数量', '方法', '服务标识', '状态', '待处理原因', '所属接口集', '创建人', '创建时间']
  for (let index = 0; index < orderedLabels.length - 1; index += 1) {
    assert.ok(
      table.indexOf(`label="${orderedLabels[index]}"`) < table.indexOf(`label="${orderedLabels[index + 1]}"`),
      `${orderedLabels[index]} 应排在 ${orderedLabels[index + 1]} 前面`,
    )
  }
  assert.match(table, /<el-table-column label="用例数量" width="88"/)
  assert.match(table, /<el-table-column prop="method" label="方法" width="84"/)
  assert.match(table, /<el-table-column prop="created_at" label="创建时间" width="190"(?![^>]*show-overflow-tooltip)/)
  assert.match(
    table,
    /<CaseCountStatusBadge[\s\S]*?:count="row\.test_case_count"[\s\S]*?:pending-count="row\.pending_test_case_count"/,
  )
  assert.match(table, /interfaces\/.*row\.id.*\/cases/)
  assert.match(table, /class="interface-name-url-cell"/)
  assert.match(table, /<el-dropdown[\s\S]*?command="cases"/)
  for (const action of ['用例管理', '编辑', '复制', '删除']) {
    assert.match(table, new RegExp(action))
  }
  assert.match(table, /class="interface-row-actions"[^>]*@click\.stop[^>]*@dblclick\.stop/)
})

test('接口主列表用例数量按待确认状态展示标签', () => {
  const source = read('../src/views/Interfaces.vue')
  const casesSource = read('../src/views/InterfaceCases.vue')
  const scopeSource = read('../src/components/InterfaceCaseGenerationScopePanel.vue')
  const badgeSource = read('../src/components/CaseCountStatusBadge.vue')
  const tableStart = source.indexOf('<el-table v-if="interfaceList.length"')
  const tableEnd = source.indexOf('</el-table>', tableStart)
  const table = source.slice(tableStart, tableEnd)
  const countColumn = table.match(/<el-table-column label="用例数量"[\s\S]*?<\/el-table-column>/)?.[0] || ''

  assert.match(source, /CaseCountStatusBadge/)
  assert.match(casesSource, /CaseCountStatusBadge/)
  assert.match(scopeSource, /CaseCountStatusBadge/)
  assert.match(countColumn, /<CaseCountStatusBadge[\s\S]*?:count="row\.test_case_count"[\s\S]*?:pending-count="row\.pending_test_case_count"/)
  assert.match(badgeSource, /v-if="normalizedCount > 0"/)
  assert.match(badgeSource, /normalizedPendingCount > 0 \? 'warning' : 'success'/)
  assert.match(badgeSource, /<el-tag v-else[\s\S]*?type="info"/)
  assert.doesNotMatch(badgeSource, /zeroAppearance/)
  assert.doesNotMatch(casesSource, /zero-appearance=/)
})

test('AI 生成用例接口选择列表按识别、覆盖、请求信息和状态顺序展示字段', () => {
  const source = read('../src/components/InterfaceCaseGenerationScopePanel.vue')
  const tableStart = source.indexOf('<el-table')
  const tableEnd = source.indexOf('</el-table>', tableStart)
  const table = source.slice(tableStart, tableEnd)
  const orderedLabels = ['接口名称/URL', '用例数', '方法', '接口集', '服务标识', '状态', '待处理原因']

  for (let index = 0; index < orderedLabels.length - 1; index += 1) {
    assert.ok(
      table.indexOf(`label="${orderedLabels[index]}"`) < table.indexOf(`label="${orderedLabels[index + 1]}"`),
      `${orderedLabels[index]} 应排在 ${orderedLabels[index + 1]} 前面`,
    )
  }
})

test('测试报告主列表和详情列表不能被长名称撑高', () => {
  const source = read('../src/views/Reports.vue')

  assert.match(source, /class="report-list-table"/)
  assert.match(source, /label="报告名称"[\s\S]{0,180}show-overflow-tooltip/)
  assert.match(source, /\.report-list-table[\s\S]{0,360}white-space:\s*nowrap/)
  assert.match(source, /class="case-name-text"[^>]*:title=/)
  assert.match(source, /\.case-name-text[\s\S]{0,240}text-overflow:\s*ellipsis/)
  assert.match(source, /class="step-name"[^>]*:title=/)
  assert.match(source, /\.step-name[\s\S]{0,240}text-overflow:\s*ellipsis/)
})

test('参数集详情的 Key、Value 和候选位置必须单行展示', () => {
  const source = read('../src/views/ParameterSetDetail.vue')

  assert.match(source, /class="parameter-item-table"/)
  assert.match(source, /prop="key"[\s\S]{0,100}show-overflow-tooltip/)
  assert.match(source, /label="Value"[\s\S]{0,120}show-overflow-tooltip/)
  assert.match(source, /class="parameter-item-link"/)
  assert.match(source, /\.parameter-item-link[\s\S]*?text-overflow:\s*ellipsis[\s\S]*?white-space:\s*nowrap/)
  assert.match(source, /\.candidate-location-select\s*\{[^}]*width:\s*230px;/)
})

test('参数集卡片描述和操作记录摘要必须受控为单行', () => {
  const parameterSets = read('../src/views/ParameterSets.vue')
  const importLogs = read('../src/components/InterfaceImportLogDrawer.vue')

  assert.match(parameterSets, /class="ps-card-desc"[^>]*:title=/)
  assert.match(parameterSets, /\.ps-card-desc[\s\S]{0,240}white-space:\s*nowrap/)
  assert.match(importLogs, /class="log-summary"[^>]*:title=/)
  assert.match(importLogs, /\.log-summary[\s\S]{0,240}white-space:\s*nowrap/)
})

test('数据看板贡献排行的创建人名称必须支持省略', () => {
  const source = read('../src/views/ProjectDashboard.vue')

  assert.match(source, /prop="name" label="创建人"[\s\S]{0,80}show-overflow-tooltip/)
})

test('测试工作台资产主列表和待处理列表必须单行省略', () => {
  const assetList = read('../src/views/test-workbench/components/WorkbenchAssetListPage.vue')
  const pendingList = read('../src/views/test-workbench/components/WorkbenchPendingList.vue')

  assert.match(assetList, /class="asset-list-table"/)
  assert.match(assetList, /\.asset-list-table[\s\S]{0,420}white-space:\s*nowrap/)
  assert.match(assetList, /class="editable-primary-field"[^>]*:title=/)
  assert.match(pendingList, /class="pending-table"/)
  assert.match(pendingList, /\.pending-table[\s\S]{0,420}white-space:\s*nowrap/)
})

test('测试工作台看板清理表和明细弹窗列表必须单行省略', () => {
  const dashboard = read('../src/views/test-workbench/pages/WorkbenchDashboardPage.vue')
  const assetDialog = read('../src/views/test-workbench/components/WorkbenchAssetListDialog.vue')

  assert.match(dashboard, /\.cleanup-table[\s\S]{0,420}white-space:\s*nowrap/)
  assert.match(assetDialog, /\.asset-table[\s\S]{0,420}white-space:\s*nowrap/)
})

test('测试工作台系统范围和需求来源列表必须约束自定义文本', () => {
  const scopeSelector = read('../src/views/test-workbench/components/WorkbenchScopeSelectorDialog.vue')
  const sourceSelector = read('../src/views/test-workbench/components/TestCaseSourceSelector.vue')

  assert.match(scopeSelector, /:title="row\.name"/)
  assert.match(scopeSelector, /:title="row\.version_no"/)
  assert.match(scopeSelector, /\.scope-table__system-toggle[\s\S]{0,520}text-overflow:\s*ellipsis/)
  assert.match(scopeSelector, /\.scope-table__version-name[\s\S]{0,260}white-space:\s*nowrap/)
  assert.match(sourceSelector, /class="source-table"/)
  assert.match(sourceSelector, /\.source-table[\s\S]{0,420}white-space:\s*nowrap/)
})

test('测试工作台用例预览、需求面板和合并来源列表必须单行省略', () => {
  const preview = read('../src/views/test-workbench/components/TestCaseGenerateDialog.vue')
  const requirementPanel = read('../src/views/test-workbench/components/WorkbenchRequirementPanel.vue')
  const mergedDetail = read('../src/views/test-workbench/components/MergedRequirementDetailDrawer.vue')

  assert.match(preview, /class="preview-table"/)
  assert.match(preview, /class="preview-table-link"[^>]*:title=/)
  assert.match(preview, /\.preview-table-link[\s\S]{0,320}white-space:\s*nowrap/)
  assert.match(requirementPanel, /\.requirements-table[\s\S]{0,320}white-space:\s*nowrap/)
  assert.match(mergedDetail, /class="source-list-table"/)
  assert.match(mergedDetail, /class="source-title-link"[^>]*:title=/)
  assert.match(mergedDetail, /\.source-title-link[\s\S]{0,320}text-overflow:\s*ellipsis/)
})

test('测试工作台模型候选项保持单行，不在窄屏下主动换行', () => {
  const source = read('../src/views/test-workbench/components/AiModelSelectionPanel.vue')

  assert.match(source, /\.model-option-main strong[\s\S]{0,260}min-width:\s*0/)
  assert.match(source, /\.model-option-quota[\s\S]{0,320}white-space:\s*nowrap/)
  assert.doesNotMatch(source, /\.model-option-quota\s*\{\s*white-space:\s*normal;/)
})

test('管理中心高风险列表的长文本必须保持单行并可省略', () => {
  const userUsageDetail = read('../src/views/admin/UserUsageDetail.vue')
  const aiModels = read('../src/views/admin/AiModels.vue')
  const messageTemplates = read('../src/views/admin/MessageTemplates.vue')
  const schedulePolicies = read('../src/views/SchedulePolicies.vue')
  const dataCleanup = read('../src/views/DataCleanup.vue')
  const aiUsage = read('../src/views/admin/AiUsage.vue')

  assert.match(userUsageDetail, /\.card-row > span:first-child[\s\S]{0,260}white-space:\s*nowrap/)
  assert.match(userUsageDetail, /\.log-table :deep\(\.el-table__cell \.cell\)[\s\S]{0,180}text-overflow:\s*ellipsis/)

  assert.match(aiModels, /class="token-ref-table"[\s\S]{0,100}header-cell-class-name="no-wrap-header"/)
  assert.match(aiModels, /prop="model" label="模型" min-width="280" show-overflow-tooltip/)
  assert.match(aiModels, /\.token-ref-table :deep\(\.el-table__cell \.cell\)[\s\S]{0,180}text-overflow:\s*ellipsis/)

  assert.match(messageTemplates, /class="preset-table"[\s\S]{0,100}header-cell-class-name="no-wrap-header"/)
  assert.match(messageTemplates, /prop="name" label="模板名称" min-width="160" show-overflow-tooltip/)
  assert.match(messageTemplates, /\.preset-table :deep\(\.el-table__cell \.cell\)[\s\S]{0,180}text-overflow:\s*ellipsis/)

  assert.match(schedulePolicies, /class="policy-table"[\s\S]{0,100}header-cell-class-name="no-wrap-header"/)
  assert.match(schedulePolicies, /class="policy-reference-table"[\s\S]{0,100}header-cell-class-name="no-wrap-header"/)
  assert.match(schedulePolicies, /class="policy-log-table"[\s\S]{0,100}header-cell-class-name="no-wrap-header"/)
  assert.match(schedulePolicies, /\.policy-table[\s\S]{0,500}white-space:\s*nowrap/)

  assert.match(dataCleanup, /class="cleanup-preview-table"[\s\S]{0,100}header-cell-class-name="no-wrap-header"/)
  assert.match(dataCleanup, /class="cleanup-relation-table"[\s\S]{0,100}header-cell-class-name="no-wrap-header"/)
  assert.match(dataCleanup, /\.cleanup-preview-table[\s\S]{0,650}white-space:\s*nowrap/)

  assert.match(aiUsage, /\.usage-table \.el-table__cell \.cell[\s\S]{0,180}text-overflow:\s*ellipsis/)
})

test('管理中心名称和地址列不能使用过宽的最小列宽', () => {
  const messageTemplates = read('../src/views/admin/MessageTemplates.vue')
  const messageChannels = read('../src/views/admin/MessageChannels.vue')

  assert.match(messageTemplates, /label="模板名称" min-width="280" show-overflow-tooltip/)
  assert.doesNotMatch(messageTemplates, /label="模板名称" min-width="620"/)

  assert.match(messageChannels, /prop="group_name" label="群名称" width="240" show-overflow-tooltip/)
  assert.match(messageChannels, /prop="webhook_url" label="Webhook" min-width="360" show-overflow-tooltip/)
  assert.doesNotMatch(messageChannels, /label="群名称" width="400"/)
  assert.doesNotMatch(messageChannels, /label="Webhook" min-width="560"/)
})
