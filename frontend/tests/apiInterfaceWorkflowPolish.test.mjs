import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = path.resolve(import.meta.dirname, '..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')

test('AI 用例生成应使用选择接口、生成中、结果预览和保存成功五步向导', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')

  assert.match(wizard, /<el-step[^>]*title="选择接口"/)
  assert.match(wizard, /<el-step[^>]*title="生成模式"/)
  assert.match(wizard, /<el-step[^>]*title="生成中"/)
  assert.match(wizard, /<el-step[^>]*title="预览确认"/)
  assert.match(wizard, /<el-step[^>]*title="保存成功"/)
  assert.match(wizard, /<InterfaceCaseGenerationScopePanel/)
  assert.match(wizard, /<AiGenerationModePickerDialog[^>]*embedded/)
})

test('AI向导返回上一步应保留接口选择条件和已选接口', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')

  assert.match(wizard, /<div v-show="wizardStep === 1" class="ai-generation-scope-step">[\s\S]*?<InterfaceCaseGenerationScopePanel/)
  assert.match(wizard, /<div v-show="wizardStep === 2" class="ai-generation-mode-step">[\s\S]*?<AiGenerationModePickerDialog/)
  assert.match(wizard, /v-if="wizardStep === 3 && generating"/)
  assert.match(wizard, /v-else-if="wizardStep === 3"/)
  assert.match(wizard, /v-(?:if|else-if)="wizardStep === 4"/)
  assert.match(wizard, /v-else-if="wizardStep === 5"/)
})

test('AI 用例生成应在生成完成后进入预览，保存成功后进入终态', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')
  const startSource = wizard.slice(
    wizard.indexOf('async function startGeneration'),
    wizard.indexOf('function retryFailedGeneration'),
  )
  const saveSource = wizard.slice(
    wizard.indexOf('async function saveResults'),
    wizard.indexOf('async function closeAll'),
  )

  assert.match(startSource, /wizardStep\.value = 3/)
  assert.match(startSource, /const result = await batchGeneration\.run[\s\S]*?generationResult\.value = result[\s\S]*?wizardStep\.value = 4/)
  assert.match(saveSource, /saved\.value = true[\s\S]*?wizardStep\.value = 5/)
  assert.match(wizard, /@click="goToModeStep">上一步<\/el-button>/)
  assert.match(wizard, /@click="saveResults"[\s\S]*>保存新增用例/)
})

test('AI向导取消应先关闭界面，再异步清理预览', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')
  const closeSource = wizard.slice(
    wizard.indexOf('async function closeAll'),
    wizard.indexOf('async function handleWizardBeforeClose'),
  )

  assert.doesNotMatch(wizard, /@update:model-value="handleWizardVisibility"/)
  assert.ok(
    closeSource.indexOf("emit('update:modelValue', false)")
      < closeSource.indexOf('discardInterfaceCaseGeneration'),
    '关闭操作不应等待预览清理接口完成',
  )
})

test('接口列表工具栏应分为筛选行和操作行，并保留全部分组动作', () => {
  const interfaces = read('src/views/Interfaces.vue')
  const toolbarStart = interfaces.indexOf('list-toolbar-frame')
  const toolbarEnd = interfaces.indexOf('<div class="interface-table-scroll"', toolbarStart)
  const toolbar = interfaces.slice(toolbarStart, toolbarEnd)
  const batchStart = toolbar.indexOf('<el-dropdown trigger="click" @command="handleBatchCommand">')
  const batchEnd = toolbar.indexOf('</el-dropdown>', batchStart) + '</el-dropdown>'.length
  const batchDropdown = toolbar.slice(batchStart, batchEnd)

  assert.match(toolbar, /interface-filter-form/)
  assert.match(toolbar, /label="名称或 URL"/)
  assert.match(toolbar, /placeholder="搜索接口名称或 URL"/)
  assert.match(toolbar, /placeholder="搜索接口名称或 URL"[^>]*style="width:200px"/)
  assert.match(toolbar, /v-model="searchMethod"[^>]*style="width:100px"/)
  assert.match(toolbar, /v-model="searchCreator"[^>]*style="width:120px"/)
  assert.match(toolbar, /<el-input-number[\s\S]*?controls-position="right"[\s\S]*?class="case-count-value-input"/)
  assert.doesNotMatch(toolbar, /<el-input[\s\S]*?v-model="searchCaseCount"[\s\S]*?type="number"/)
  const filterLabels = ['名称或 URL', '方法', '接口状态', '用例数', '创建人']
  for (let index = 0; index < filterLabels.length - 1; index += 1) {
    assert.ok(
      toolbar.indexOf(`label="${filterLabels[index]}"`) < toolbar.indexOf(`label="${filterLabels[index + 1]}"`),
      `${filterLabels[index]} 应排在 ${filterLabels[index + 1]} 前面`,
    )
  }
  assert.match(toolbar, /v-model="searchMethod"/)
  assert.match(toolbar, /v-for="method in interfaceMethodOptions"/)
  assert.match(toolbar, /<el-dropdown[\s\S]*?导入/)
  assert.match(toolbar, /<el-dropdown[\s\S]*?批量操作/)
  assert.match(toolbar, /<el-button type="primary" @click="openInterfaceCaseGeneration">AI生成用例<\/el-button>/)
  assert.doesNotMatch(batchDropdown, /AI生成用例/)
  for (const action of ['文件导入', 'cURL导入', '批量处理状态', '批量设置服务', '批量移动', '批量删除']) {
    assert.match(toolbar, new RegExp(action))
  }

  const listScope = interfaces.slice(0, interfaces.indexOf('<!-- 接口编辑对话框 -->'))
  assert.doesNotMatch(listScope, /<el-form-item[^>]*label="待处理原因"/)
  assert.match(interfaces, /待处理原因/) // 列表仍保留结果展示和处理依据
})

test('接口名称或 URL 查询应使用后端联合关键词参数', () => {
  const interfaces = read('src/views/Interfaces.vue')
  const endpoint = read('../backend/api/v1/endpoints/interfaces.py')

  assert.match(interfaces, /if \(searchName\.value\.trim\(\)\) extra\.keyword = searchName\.value\.trim\(\)/)
  assert.doesNotMatch(interfaces, /if \(searchName\.value\) extra\.name = searchName\.value/)
  assert.match(endpoint, /keyword: str \| None = None/)
  assert.match(endpoint, /or_\(Interface\.name\.contains\(keyword\), Interface\.url\.contains\(keyword\)\)/)
})

test('接口列表方法筛选应使用当前项目的去重方法选项并交给后端过滤', () => {
  const interfaces = read('src/views/Interfaces.vue')
  const api = read('src/api/interfaces.js')
  const endpoint = read('../backend/api/v1/endpoints/interfaces.py')

  assert.match(interfaces, /getInterfaceMethods/)
  assert.match(interfaces, /if \(searchMethod\.value\) extra\.method = searchMethod\.value/)
  assert.match(endpoint, /@router\.get\("\/methods"\)/)
  assert.match(endpoint, /method: str \| None = None/)
  assert.match(endpoint, /func\.upper\(Interface\.method\) == normalized_method/)
  assert.match(api, /url: '\/interfaces\/methods'/)
})

test('接口复制按钮应有进行中保护，避免重复提交和重复 Toast', () => {
  const interfaces = read('src/views/Interfaces.vue')

  assert.match(interfaces, /const copyingInterfaceId = ref\(null\)/)
  assert.match(interfaces, /<el-dropdown-item command="copy" :disabled="copyingInterfaceId !== null">复制<\/el-dropdown-item>/)
  assert.match(interfaces, /if \(copyingInterfaceId\.value !== null\) return/)
  assert.doesNotMatch(interfaces, /const handleCopy[\s\S]*?ElMessage\.success/)
})

test('文件导入结果摘要应限制宽度并保持水平居中', () => {
  const summary = read('src/components/ImportResultSummary.vue')

  assert.match(summary, /\.import-result-summary\s*\{[\s\S]*?max-width:/)
  assert.match(summary, /\.import-result-summary\s*\{[\s\S]*?margin:\s*0 auto/)
})

test('API 测试主要列表和弹窗空状态应复用统一空状态组件', () => {
  const interfaces = read('src/views/Interfaces.vue')
  const cases = read('src/views/InterfaceCases.vue')
  const dashboard = read('src/views/ProjectDashboard.vue')
  const importLogs = read('src/components/InterfaceImportLogDrawer.vue')
  const environments = read('src/views/Environments.vue')

  assert.doesNotMatch(interfaces, /:show-image="false"/)
  assert.match(interfaces, /<el-tree[\s\S]*?<template #empty>\s*<GlobalEmpty \/>/)
  assert.match(interfaces, /<GlobalEmpty v-else-if="!loading" \/>/)
  assert.match(cases, /<GlobalEmpty v-if="!ifsLoading && interfaces\.length === 0" text="暂无数据" \/>/)
  assert.match(cases, /<GlobalEmpty v-if="!casesLoading && cases\.length === 0 && currentIfaceId" text="暂无数据" \/>/)
  assert.match(dashboard, /import GlobalEmpty from '@\/components\/GlobalEmpty\.vue'/)
  assert.match(dashboard, /<GlobalEmpty v-else text="暂无数据" \/>/)
  assert.match(importLogs, /<div v-if="!loading && !errorMessage && !logs\.length" class="log-empty">[\s\S]*<GlobalEmpty text="暂无操作记录" \/>/)
  assert.match(importLogs, /<template #empty>\s*<GlobalEmpty \/>/)
  assert.match(environments, /<GlobalEmpty v-else-if="!loading" text="暂无数据" action-text="新建环境" @action="handleCreate" \/>/)
})

test('左右空状态都应在各自内容区域内垂直居中', () => {
  const interfaces = read('src/views/Interfaces.vue')

  assert.match(interfaces, /\.collection-tree :deep\(\.el-tree__empty-block\)\s*\{[\s\S]*?height:\s*100%[\s\S]*?align-items:\s*center/)
  assert.match(interfaces, /\.interface-table-scroll\.is-empty\s*\{[\s\S]*?align-items:\s*center/)
})

test('接口列表无数据时展示独立空状态，有数据时才渲染可横向滚动的表格', () => {
  const interfaces = read('src/views/Interfaces.vue')

  assert.match(interfaces, /<el-table v-if="interfaceList\.length"/)
  assert.match(interfaces, /<GlobalEmpty v-else-if="!loading" \/>/)
  assert.match(interfaces, /\.interface-table-scroll\s*\{[\s\S]*?overflow:\s*auto/)
  assert.match(interfaces, /\.interface-table-scroll\.is-empty\s*\{[\s\S]*?overflow:\s*hidden/)
})

test('AI 用例生成第一步应使用紧凑筛选并保持操作按钮同一行', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')
  const scope = read('src/components/InterfaceCaseGenerationScopePanel.vue')

  assert.match(wizard, /width="min\(1120px, calc\(100vw - 48px\)\)"/)
  assert.match(scope, /<el-form-item label="名称或 URL"/)
  assert.match(scope, /v-model="filters\.keyword"/)
  assert.match(scope, /placeholder="名称或 URL"/)
  assert.doesNotMatch(scope, /<el-form-item label="URL">/)
  assert.match(scope, /\.scope-filter-form\s*\{[\s\S]*?flex-wrap:\s*nowrap/)
  assert.match(scope, /<el-form-item class="scope-filter-actions">/)
  assert.match(scope, /@media \(max-width: 1199px\)/)
})

test('名称或 URL 搜索应同时作用于分页查询和跨分页全选', () => {
  const scope = read('src/components/InterfaceCaseGenerationScopePanel.vue')
  const api = read('src/api/interfaces.js')
  const endpoint = read('../backend/api/v1/endpoints/interfaces.py')

  assert.match(scope, /keyword: filters\.keyword\.trim\(\) \|\| undefined/)
  assert.match(scope, /getInterfaces\(null, props\.projectId, page\.value, pageSize\.value, requestParams\(\)\)/)
  assert.match(scope, /getInterfaceSelectionIds\(props\.projectId, requestParams\(\)\)/)
  assert.match(api, /getInterfaces[\s\S]*Object\.assign\(params, extraParams\)/)
  assert.match(endpoint, /keyword: str \| None = None/)
  assert.match(endpoint, /or_\(Interface\.name\.contains\(keyword\), Interface\.url\.contains\(keyword\)\)/)
})

test('接口集筛选的多值 GET 参数应被 FastAPI 注册为查询参数', () => {
  const endpoint = read('../backend/api/v1/endpoints/interfaces.py')

  assert.match(endpoint, /from fastapi import[^\n]*Query/)
  assert.equal(
    (endpoint.match(/collection_ids: Annotated\[list\[int\] \| None, Query\(\)\] = None/g) || []).length,
    2,
    '列表查询和跨页全选接口都必须显式声明 collection_ids 为 Query 参数',
  )
})

test('AI生成用例接口集选择应使用带复选框的级联多选，并保持输入框紧凑', () => {
  const scope = read('src/components/InterfaceCaseGenerationScopePanel.vue')

  assert.match(scope, /<el-cascader/)
  assert.match(scope, /:options="collectionTree"/)
  assert.match(scope, /:props="collectionCascaderProps"/)
  assert.match(scope, /multiple:\s*true/)
  assert.match(scope, /checkStrictly:\s*true/)
  assert.match(scope, /emitPath:\s*false/)
  assert.match(scope, /<el-cascader[\s\S]*?collapse-tags[\s\S]*?:max-collapse-tags="1"/)
  assert.doesNotMatch(scope, /<template #tag=/)
  assert.doesNotMatch(scope, /scope-collection-summary-(name|count)/)
  assert.match(scope, /<el-form-item label="接口集" class="scope-collection-filter-item">/)
  assert.match(scope, /class="scope-collection-control"/)
  assert.match(scope, /class="scope-collection-select"/)
  assert.match(scope, /<div v-if="!isFixedScope" class="scope-filter-frame">[\s\S]*?<el-form[\s\S]*?<\/el-form>[\s\S]*?<\/div>/)
  assert.doesNotMatch(scope, /<el-button @click="resetFilters">重置<\/el-button>/)
  assert.doesNotMatch(scope, /function resetFilters\(/)
  assert.doesNotMatch(scope, /<el-tree-select|<el-option[\s\S]*collectionOptions/)
  assert.match(scope, /\.scope-collection-control\s*\{[\s\S]*?width:\s*220px[\s\S]*?height:\s*32px/)
  assert.match(scope, /:global\(\.scope-collection-select\)\s*\{[\s\S]*?width:\s*220px\s*!important[\s\S]*?height:\s*32px\s*!important/)
  assert.doesNotMatch(scope, /\.scope-collection-select\.el-input/)
  assert.match(scope, /\.scope-collection-filter-item\s*\{[\s\S]*?height:\s*32px[\s\S]*?max-height:\s*32px/)
  assert.match(scope, /\.scope-filter-form :deep\(\.el-form-item\)\s*\{[\s\S]*?height:\s*32px[\s\S]*?max-height:\s*32px/)
  assert.match(scope, /\.scope-collection-filter-item :deep\(\.el-form-item__content\)\s*\{[\s\S]*?flex:\s*0 0 220px !important[\s\S]*?width:\s*220px !important[\s\S]*?height:\s*32px !important/)
  assert.match(scope, /\.scope-filter-keyword\s*\{[\s\S]*?flex:\s*0 0 auto !important;/)
  assert.match(scope, /\.scope-filter-keyword :deep\(\.el-input\)\s*\{[\s\S]*?width:\s*180px/)
  assert.match(scope, /\.scope-filter-frame\s*\{[\s\S]*?box-sizing:\s*border-box[\s\S]*?padding:\s*12px 16px[\s\S]*?background:\s*#f8fafc[\s\S]*?border:\s*1px solid #edf1f6[\s\S]*?border-radius:\s*10px/)
  assert.match(scope, /\.scope-filter-form\s*\{[\s\S]*?gap:\s*0 12px[\s\S]*?margin:\s*0/)
  assert.match(scope, /\.scope-filter-form :deep\(\.el-form-item\)\s*\{[\s\S]*?margin:\s*0/)
  assert.match(scope, /\.scope-collection-filter-item :deep\(\.el-form-item__content\)\s*\{[\s\S]*?overflow:\s*visible\s*!important/)
  assert.match(scope, /:global\(\.scope-collection-select \.el-cascader__tags\)\s*\{[\s\S]*?position:\s*absolute\s*!important[\s\S]*?top:\s*50%\s*!important[\s\S]*?bottom:\s*auto\s*!important[\s\S]*?box-sizing:\s*border-box[\s\S]*?flex-wrap:\s*nowrap\s*!important[\s\S]*?overflow:\s*hidden[\s\S]*?transform:\s*translateY\(-50%\)\s*!important/)
  assert.match(scope, /:global\(\.scope-collection-select \.el-cascader__tags\)\s*\{[\s\S]*?display:\s*flex\s*!important[\s\S]*?align-items:\s*center\s*!important/)
  assert.match(scope, /\.scope-collection-control\s*\{[\s\S]*?overflow:\s*visible\s*!important/)
  assert.match(scope, /:global\(\.scope-collection-select \.el-input__wrapper\)\s*\{[\s\S]*?overflow:\s*hidden\s*!important/)
  assert.match(scope, /:global\(\.scope-collection-select \.el-cascader__tags \.el-tag\)\s*\{[\s\S]*?height:\s*24px\s*!important[\s\S]*?margin:\s*0\s*!important[\s\S]*?line-height:\s*22px\s*!important/)
  assert.match(scope, /:global\(\.scope-collection-select \.el-input__wrapper\)\s*\{[\s\S]*?height:\s*32px[\s\S]*?max-height:\s*32px/)
  assert.match(scope, /:global\(\.scope-collection-select \.el-input__suffix\)\s*\{[\s\S]*?position:\s*absolute\s*!important[\s\S]*?top:\s*50%\s*!important[\s\S]*?bottom:\s*auto\s*!important[\s\S]*?height:\s*20px\s*!important[\s\S]*?align-items:\s*center\s*!important[\s\S]*?transform:\s*translateY\(-50%\)\s*!important/)
  assert.match(scope, /:global\(\.scope-collection-select \.el-input__suffix-inner\)\s*\{[\s\S]*?align-items:\s*center\s*!important[\s\S]*?justify-content:\s*center\s*!important[\s\S]*?height:\s*100%\s*!important/)
  assert.match(scope, /:global\(\.scope-collection-select \.el-input__suffix \.el-icon\)\s*\{[\s\S]*?display:\s*inline-flex\s*!important[\s\S]*?align-items:\s*center\s*!important[\s\S]*?justify-content:\s*center\s*!important/)
  assert.match(scope, /:global\(\.scope-collection-select \.el-cascader__clear-icon\),\s*\n:global\(\.scope-collection-select \.el-cascader__close-icon\)\s*\{[\s\S]*?position:\s*static\s*!important[\s\S]*?top:\s*auto\s*!important[\s\S]*?transform:\s*none\s*!important/)
  assert.match(scope, /:global\(\.scope-collection-select \.el-input__clear\)\s*\{[\s\S]*?position:\s*static\s*!important[\s\S]*?top:\s*auto\s*!important[\s\S]*?transform:\s*none\s*!important/)
  assert.match(scope, /\.scope-table-scroll\s*\{[\s\S]*?width:\s*100%/)
  assert.match(scope, /\.scope-table\s*\{[\s\S]*?min-width:\s*100%/)
  assert.doesNotMatch(scope, /<el-form-item label="用例数">/)
  assert.doesNotMatch(scope, /test_case_count_operator|scope-case-count-input|caseCountOperators/)
  assert.match(scope, /allFilteredSelected \? '取消全选' : '全选'/)
  assert.match(scope, /const allFilteredSelected = ref\(false\)/)
  assert.match(scope, /const shouldClear = filteredIds\.length > 0/)
  assert.match(scope, /if \(shouldClear\) next\.delete\(id\)/)
  assert.match(scope, /else next\.add\(id\)/)
    const paginationStart = scope.indexOf('<div class="scope-pagination-bar">')
    const footerStart = scope.indexOf('<div v-if="showFooter"', paginationStart)
    assert.ok(paginationStart >= 0)
    assert.ok(footerStart > paginationStart)
    assert.doesNotMatch(scope.slice(paginationStart, footerStart), /全选/)
  assert.doesNotMatch(scope, /已选 \{\{ selectedIds\.size \}\} 个接口，生成结果将进入用例管理待确认/)
  assert.match(scope, /scope-pagination-bar/)
})

test('所有步骤式弹窗的当前步骤与完成步骤使用统一绿色状态', () => {
  const sources = [
    read('src/components/BatchInterfaceCaseGenerationDialog.vue'),
    read('src/components/ImportDialog.vue'),
    read('src/views/test-workbench/components/TestCaseGenerateDialog.vue'),
    read('src/views/ProjectDashboard.vue'),
    read('src/views/test-workbench/pages/WorkbenchDashboardPage.vue'),
  ]

  for (const source of sources) assert.match(source, /wizard-steps-green/)

  const app = read('src/App.vue')
  assert.match(app, /\.wizard-steps-green \.el-step__head\.is-process/)
  assert.match(app, /\.wizard-steps-green \.el-step__title\.is-process[\s\S]*?color:\s*#67c23a/)
  assert.match(app, /\.wizard-steps-green \.el-step__description\.is-process[\s\S]*?color:\s*#67c23a/)
  assert.match(app, /\.wizard-steps-green \.el-step__head\.is-finish[\s\S]*?color:\s*#67c23a/)
  assert.match(app, /\.wizard-steps-green \.el-step__line-inner[\s\S]*?background-color:\s*#67c23a/)
  assert.match(app, /\.wizard-steps-green \.el-step\.is-process \.el-step__main[\s\S]*?background-color:\s*#f0f9eb/)
  assert.match(app, /\.wizard-steps-green \.el-step\.is-process \.el-step__main[\s\S]*?border:\s*1px solid #e1f3d8/)
  assert.match(app, /\.wizard-steps-green \.el-step\.is-process \.el-step__main[\s\S]*?border-radius:\s*999px/)
})

test('AI生成用例接口列表应合并接口名称和 URL，并支持点击名称打开详情', () => {
  const scope = read('src/components/InterfaceCaseGenerationScopePanel.vue')
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')

  assert.match(scope, /<el-table-column label="接口名称\/URL"/)
  assert.match(scope, /class="scope-interface-name-url-cell"/)
  assert.match(scope, /class="scope-interface-name"[\s\S]*?@click\.stop="emit\('view-interface', row\)"/)
  assert.match(scope, /class="scope-interface-url"/)
  assert.doesNotMatch(scope, /<el-table-column prop="name" label="接口名称"/)
  assert.doesNotMatch(scope, /<el-table-column prop="url" label="URL"/)
  const tableStart = scope.indexOf('<el-table')
  const tableEnd = scope.indexOf('</el-table>', tableStart)
  const table = scope.slice(tableStart, tableEnd)
  const columns = ['接口名称/URL', '用例数', '方法', '接口集', '服务标识', '状态', '待处理原因']
  for (let index = 0; index < columns.length; index += 1) {
    assert.match(table, new RegExp(`label="${columns[index]}"`))
    if (index > 0) {
      assert.ok(
        table.indexOf(`label="${columns[index - 1]}"`) < table.indexOf(`label="${columns[index]}"`),
        `${columns[index]} 应排在 ${columns[index - 1]} 后面`,
      )
    }
  }
  assert.match(scope, /<el-table-column label="服务标识"[^>]*show-overflow-tooltip/)
  assert.match(scope, /row\.service_key \|\| '-'/)
  assert.match(scope, /<el-table-column label="待处理原因"[^>]*show-overflow-tooltip/)
  assert.match(scope, /row\.workflow_status === 'pending'/)
  assert.match(scope, /row\.pending_reason_label \|\| '-'/)
  assert.match(scope, /defineEmits\(\['confirm', 'cancel', 'view-interface'\]\)/)
  assert.match(wizard, /@view-interface="openInterfaceDetail"/)
})

test('接口和用例详情应移除参数配置标题，并用级联单选选择接口集', () => {
  const interfaces = read('src/views/Interfaces.vue')
  const cases = read('src/views/InterfaceCases.vue')
  const interfaceEdit = read('src/components/InterfaceEditDialog.vue')
  const interfaceDetail = read('src/components/InterfaceDetailDialog.vue')

  for (const source of [interfaces, cases, interfaceDetail]) {
    assert.doesNotMatch(source, /<el-divider content-position="left">参数配置<\/el-divider>/)
  }

  assert.match(interfaces, /<InterfaceEditDialog[\s\S]*:collection-tree="collectionTree"/)
  assert.match(interfaceEdit, /<CollectionSingleSelect[\s\S]*v-model="props\.model\.collection_id"[\s\S]*display-mode="cascader"/)
  assert.match(cases, /<CollectionSingleSelect[\s\S]*v-model="selectedColId"[\s\S]*display-mode="cascader"/)
})

test('接口编辑详情应支持状态编辑并按四行排列基础字段', () => {
  const interfaces = read('src/views/Interfaces.vue')
  const interfaceEdit = read('src/components/InterfaceEditDialog.vue')
  const basicFields = read('src/components/InterfaceBasicFields.vue')
  const endpoint = read('../backend/api/v1/endpoints/interfaces.py')

  const infoTab = interfaceEdit.match(
    /<el-tab-pane v-if="props\.showInfo && props\.model\.id" label="信息" name="info">([\s\S]*?)<\/el-tab-pane>/,
  )?.[1] || ''
  const basicFieldsEditor = interfaceEdit

  assert.match(basicFieldsEditor, /<template #status>[\s\S]*?<el-select v-model="props\.model\.workflow_status"[\s\S]*?待处理[\s\S]*?已处理[\s\S]*?<\/template>/)
  assert.match(basicFieldsEditor, /<template #collection>[\s\S]*?<CollectionSingleSelect[\s\S]*?v-model="props\.model\.collection_id"[\s\S]*?display-mode="cascader"[\s\S]*?<\/template>/)
  assert.match(basicFieldsEditor, /<template #service>[\s\S]*?label="服务标识"[\s\S]*?<\/template>/)
  assert.match(basicFieldsEditor, /<template #description>[\s\S]*?label="描述"[\s\S]*?<el-input[\s\S]*?v-model="props\.model\.description"[\s\S]*?:rows="1"[\s\S]*?<\/template>/)
  assert.match(basicFieldsEditor, /<template #pending-reason>[\s\S]*?label="待处理原因"[\s\S]*?interfacePendingReasonLabel[\s\S]*?<\/template>/)
  const statusSlot = basicFieldsEditor.match(/<template #status>([\s\S]*?)<\/template>/)?.[1] || ''
  const pendingReasonSlot = basicFieldsEditor.match(/<template #pending-reason>([\s\S]*?)<\/template>/)?.[1] || ''
  assert.doesNotMatch(statusSlot, /pending_reason_label/)
  assert.doesNotMatch(pendingReasonSlot, /<el-(select|input)/)
  assert.match(infoTab, /<RecordMetadataTable :record="props\.model" \/>/)
  assert.doesNotMatch(infoTab, /接口状态|workflow_status/)
  const customLayout = basicFields.match(/<template v-if="\$slots\.status">([\s\S]*?)<\/template>/)?.[1] || ''
  const rows = customLayout.match(/<el-row[\s\S]*?<\/el-row>/g) || []
  assert.equal(rows.length, 4, '接口详情基础字段应分为四行')
  assert.match(rows[0], /接口名称[\s\S]*?请求方法/)
  assert.match(rows[1], /URL[\s\S]*?<slot name="service" \/>/)
  assert.match(rows[2], /<slot name="collection" \/>[\s\S]*?<slot name="description" \/>/)
  assert.match(rows[3], /<slot name="status" \/>[\s\S]*?<slot name="pending-reason" \/>/)
  assert.match(interfaceEdit, /workflow_status: props\.model\.workflow_status/)
  assert.match(endpoint, /workflow_status: str \| None = None/)
  assert.match(endpoint, /if "workflow_status" in update_data:[\s\S]*?INTERFACE_STATUS_DONE[\s\S]*?mark_interface_done\(interface\)/)
})

test('接口状态变更时详情页应即时同步待处理原因', () => {
  const interfaces = read('src/views/Interfaces.vue')
  const editor = read('src/components/InterfaceEditDialog.vue')

  assert.match(editor, /const interfacePendingReasonLabel = computed\(\(\) => \{[\s\S]*?if \(props\.model\?\.workflow_status !== 'pending'\) return '-'/)
  assert.match(editor, /props\.model\?\.pending_reason_label \|\| \(props\.model\?\.id \? '存量数据待确认' : '-'/)
  assert.match(editor, /:title="interfacePendingReasonLabel"[\s\S]*?interfacePendingReasonLabel/)
})

test('接口列表状态应通过独立轻量弹层修改，保留完整编辑流程', () => {
  const interfaces = read('src/views/Interfaces.vue')

  assert.match(interfaces, /<InterfaceWorkflowStatusDialog[\s\S]*:status="workflowStatusDialog\.status"/)
  assert.match(interfaces, /<button[^>]*class="interface-status-trigger"[^>]*@click\.stop="openWorkflowStatusDialog\(row\)"/)
  assert.match(interfaces, /const openWorkflowStatusDialog = \(row\) => \{[\s\S]*?workflowStatusDialog\.status = row\.workflow_status \|\| 'pending'/)
  assert.match(interfaces, /await updateInterface\(workflowStatusDialog\.interfaceId, \{[\s\S]*?workflow_status: workflowStatus[\s\S]*?\}\)/)
  const statusDialog = read('src/components/InterfaceWorkflowStatusDialog.vue')
  assert.match(statusDialog, /title="修改接口状态"/)
  assert.match(statusDialog, /v-model="draftStatus"/)
  assert.match(statusDialog, /待处理[\s\S]*?已处理/)
  assert.match(statusDialog, /emit\('save', draftStatus\.value\)/)
})

test('接口状态弹窗应仅展示状态和选项，并保持内容紧凑居中', () => {
  const interfaces = read('src/views/Interfaces.vue')
  const statusDialog = read('src/components/InterfaceWorkflowStatusDialog.vue')

  assert.doesNotMatch(interfaces, /interfaceName="workflowStatusDialog\.interfaceName"/)
  assert.doesNotMatch(statusDialog, /interfaceName|workflow-status-target|待处理原因由系统根据接口处理情况自动维护/)
  assert.match(statusDialog, /align-center/)
  assert.match(statusDialog, /class="workflow-status-current"[\s\S]*当前状态[\s\S]*<el-tag/)
  assert.match(statusDialog, /class="workflow-status-options"[^>]*role="radiogroup"[\s\S]*待处理[\s\S]*已处理/)
  assert.match(statusDialog, /<template #footer>[\s\S]*取消[\s\S]*保存/)
  assert.match(statusDialog, /\.workflow-status-dialog\s*\{[\s\S]*align-items:\s*center[\s\S]*gap:/)
})

test('AI生成用例第一步不应额外渲染空的弹窗底部区域', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')

  assert.match(wizard, /<template #footer v-if="wizardStep >= 3">/)
  assert.doesNotMatch(wizard, /<template #footer>\s*<div v-if="wizardStep === 3/)
})

test('AI生成用例第二步应移除冗余说明并保持底部操作可见', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')
  const panel = read('src/components/AiGenerationModePickerPanel.vue')

  assert.doesNotMatch(panel, /class="gen-settings-guide"/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-mode-step\)\s*,[\s\S]*?width:\s*min\(1120px, calc\(100vw - 48px\)\) !important;/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-mode-step\)\s*\{[\s\S]*?height:\s*min\(580px, calc\(100vh - 48px\)\);/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-mode-step \.gen-settings-embedded\)\s*\{[\s\S]*?display:\s*flex[\s\S]*?flex:\s*1;/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-mode-step \.ai-generation-wizard-body\)\s*\{[\s\S]*?justify-content:\s*center;/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-mode-step \.ai-generation-mode-step\)\s*\{[\s\S]*?flex:\s*0 1 auto;/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-mode-step \.gen-settings-body\)\s*\{[\s\S]*?min-height:\s*0;/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-mode-step \.ai-generation-wizard-body\)\s*\{[\s\S]*?overflow:\s*hidden/)
  assert.match(wizard, /\.ai-generation-wizard-steps\s*:deep\(\.el-step\)\s*\{[\s\S]*?flex:\s*1 1 0;/)
})

test('AI生成用例失败结果应展示服务商失败明细并在固定区域内滚动', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')

  assert.match(wizard, /const generationFailureDetails = computed\(\(\) =>[\s\S]*?failedDetails/)
  assert.match(wizard, /generationFailureDetails\.length/)
  assert.match(wizard, /class="generation-failure-details"/)
      assert.match(wizard, /class="generation-failure-detail-name"[\s\S]*?failure\.name/)
      assert.match(wizard, /class="generation-failure-detail-reason"[\s\S]*?failure\.reason \|\| failure\.detail/)
      assert.match(wizard, /\.generation-failure-details\s*\{[\s\S]*?height:\s*auto;[\s\S]*?max-height:\s*min\(300px, 34vh\);[\s\S]*?overflow-y:\s*auto;/)
      assert.match(wizard, /\.generation-failure-body\s*\{[\s\S]*?min-height:\s*0;/)
    })

test('AI生成用例各步骤应按内容使用不同高度', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')

  assert.match(wizard, /'is-failure-step': wizardStep === 3 && !generating/)
  for (const step of ['scope', 'mode', 'progress', 'failure', 'result', 'saved']) {
    assert.match(
      wizard,
      new RegExp(`ai-generation-wizard-dialog\\.is-${step}-step\\)\\s*\\{[\\s\\S]*?height:\\s*min\\(`),
      `${step} 步应有独立高度`,
    )
  }
  assert.doesNotMatch(wizard, /ai-generation-wizard-dialog\.is-scope-step\),[\s\S]*?is-saved-step\)\s*\{[\s\S]*?height:\s*min\(760px/)
})

test('AI生成用例第二步应保持协调尺寸并支持返回上一步', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')
  const picker = read('src/components/AiGenerationModePickerDialog.vue')
  const panel = read('src/components/AiGenerationModePickerPanel.vue')

  assert.match(wizard, /:class="\{[\s\S]*?'is-scope-step': wizardStep === 1,[\s\S]*?'is-mode-step': wizardStep === 2,[\s\S]*?'is-result-step': wizardStep === 4,[\s\S]*?'is-saved-step': wizardStep === 5[\s\S]*?\}"/)
  assert.match(wizard, /<AiGenerationModePickerDialog[\s\S]*?embedded[\s\S]*?:show-previous="true"/)
  assert.match(wizard, /@back="goToScopeStep"/)
  assert.match(wizard, /function goToScopeStep\(\)\s*\{[\s\S]*?wizardStep\.value = 1/)
  assert.match(picker, /showPrevious:\s*\{\s*type:\s*Boolean,\s*default:\s*false\s*\}/)
  assert.match(picker, /:show-previous="showPrevious"/)
  assert.match(picker, /defineEmits\(\['update:modelValue', 'confirm', 'cancel', 'models-refreshed', 'back'\]\)/)
  assert.match(panel, /v-if="showPrevious"[\s\S]*?>上一步<\/el-button>/)
  assert.match(panel, /showPrevious:\s*\{\s*type:\s*Boolean,\s*default:\s*false\s*\}/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-mode-step\)\s*\{[\s\S]*?height:\s*min\(580px, calc\(100vh - 48px\)\);/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-mode-step \.el-dialog__body\)\s*\{[\s\S]*?flex:\s*1;[\s\S]*?overflow:\s*hidden;/)
})

test('AI生成用例第四步应保持协调尺寸且结果页不出现滚动条', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')

  assert.match(wizard, /'is-result-step': wizardStep === 4/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-result-step\)\s*\{[\s\S]*?height:\s*min\(620px, calc\(100vh - 48px\)\);/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-result-step \.el-dialog__body\)\s*\{[\s\S]*?flex:\s*1;[\s\S]*?overflow:\s*hidden;/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-result-step \.ai-generation-wizard\)\s*\{[\s\S]*?height:\s*100%;/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-result-step \.generation-result-body\)\s*\{[\s\S]*?flex:\s*0 1 auto;[\s\S]*?min-height:\s*0;[\s\S]*?overflow:\s*visible;/)
})

test('AI生成用例第三步生成中状态应在接近现有高度的范围内展示', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')

  assert.match(wizard, /'is-progress-step': wizardStep === 3 && generating/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-progress-step\)\s*\{[\s\S]*?height:\s*min\(620px, calc\(100vh - 48px\)\);/)
})

test('AI生成用例五步应使用协调的弹窗宽高', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')

  assert.match(wizard, /width="min\(1120px, calc\(100vw - 48px\)\)"/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-scope-step\),[\s\S]*?ai-generation-wizard-dialog\.is-mode-step\),[\s\S]*?ai-generation-wizard-dialog\.is-progress-step\),[\s\S]*?ai-generation-wizard-dialog\.is-failure-step\),[\s\S]*?ai-generation-wizard-dialog\.is-result-step\),[\s\S]*?ai-generation-wizard-dialog\.is-saved-step\)\s*\{[\s\S]*?width:\s*min\(1120px, calc\(100vw - 48px\)\) !important;/)
  assert.doesNotMatch(wizard, /ai-generation-wizard-dialog\.is-scope-step\),[\s\S]*?is-saved-step\)\s*\{[\s\S]*?height:\s*min\(760px/)
})

test('AI生成用例表格底部不应显示相邻的重复分割线', () => {
  const scope = read('src/components/InterfaceCaseGenerationScopePanel.vue')

  assert.match(scope, /\.scope-table :deep\(\.el-table__inner-wrapper::before\)\s*\{\s*display:\s*none;/)
})

test('AI生成用例第一步无数据时应保持列表滚动区并复用统一空状态', () => {
  const scope = read('src/components/InterfaceCaseGenerationScopePanel.vue')

  assert.match(scope, /<GlobalEmpty text="暂无数据" \/>/)
  assert.doesNotMatch(scope, /<GlobalEmpty[^>]*:show-image="false"/)
  assert.match(scope, /const scopeTableMaxHeight = 384/)
  assert.match(scope, /\.scope-table-scroll\s*\{[\s\S]*?flex:\s*1 1 auto[\s\S]*?height:\s*auto[\s\S]*?min-height:\s*0/)
  assert.match(scope, /\.scope-table :deep\(\.el-table__empty-block\)\s*\{[\s\S]*?height:\s*100%[\s\S]*?min-height:\s*0;/)
  assert.match(scope, /\.scope-table :deep\(\.global-empty \.el-empty\)\s*\{[\s\S]*?min-height:\s*0;/)
})

test('AI生成用例弹窗应只保留内容区滚动，不滚动整个弹窗主体', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')
  const scope = read('src/components/InterfaceCaseGenerationScopePanel.vue')

  assert.match(wizard, /\.ai-generation-wizard\s*\{[\s\S]*?width:\s*100%[\s\S]*?height:\s*100%[\s\S]*?min-height:\s*0/)
  assert.match(wizard, /\.ai-generation-wizard-body\s*\{[\s\S]*?flex:\s*1[\s\S]*?overflow:\s*hidden/)
  assert.match(wizard, /ai-generation-wizard-dialog\.is-scope-step \.scope-panel\)\s*\{[\s\S]*?width:\s*100%[\s\S]*?align-self:\s*stretch;/)
  assert.match(wizard, /ai-generation-wizard-dialog \.el-dialog__body\)\s*\{[\s\S]*?overflow:\s*hidden/)
  assert.match(scope, /\.scope-panel\s*\{[\s\S]*?width:\s*100%[\s\S]*?height:\s*100%[\s\S]*?overflow:\s*hidden/)
})

test('AI生成用例各步骤的底部操作区应完整可见且不被内容区挤压', () => {
  const wizard = read('src/components/BatchInterfaceCaseGenerationDialog.vue')
  const scope = read('src/components/InterfaceCaseGenerationScopePanel.vue')
  const panel = read('src/components/AiGenerationModePickerPanel.vue')

  assert.match(wizard, /ai-generation-wizard-dialog \.el-dialog__header\)\s*\{[\s\S]*?flex:\s*0 0 auto;/)
  assert.match(wizard, /ai-generation-wizard-dialog \.el-dialog__footer\)\s*\{[\s\S]*?flex:\s*0 0 auto;/)
  assert.match(scope, /\.scope-panel\s*\{[\s\S]*?box-sizing:\s*border-box[\s\S]*?flex:\s*1 1 auto;/)
  assert.match(scope, /\.scope-table-scroll\s*\{[\s\S]*?flex:\s*1 1 auto[\s\S]*?height:\s*auto[\s\S]*?min-height:\s*0[\s\S]*?overflow-y:\s*hidden/)
  assert.match(scope, /\.scope-footer\s*\{[\s\S]*?flex:\s*0 0 auto[\s\S]*?min-height:\s*0/)
  assert.match(panel, /\.gen-settings-footer\s*\{[\s\S]*?flex:\s*0 0 auto[\s\S]*?white-space:\s*nowrap/)
})

test('表格横向滚动应属于独立滚动区并贴在内容区底部', () => {
  const scope = read('src/components/InterfaceCaseGenerationScopePanel.vue')
  const interfaces = read('src/views/Interfaces.vue')

  assert.match(scope, /class="scope-table-scroll"/)
  assert.match(scope, /\.scope-table-scroll\s*\{[\s\S]*?flex:\s*1 1 auto[\s\S]*?height:\s*auto[\s\S]*?min-width:\s*0[\s\S]*?min-height:\s*0[\s\S]*?overflow-x:\s*auto[\s\S]*?overflow-y:\s*hidden/)
  assert.match(interfaces, /\.interface-table-scroll\s*\{[\s\S]*?flex:\s*1[\s\S]*?min-height:\s*0[\s\S]*?overflow:\s*auto/)
  assert.match(interfaces, /<el-table v-if="interfaceList\.length"[^>]*height="100%"[^>]*class="interface-table"/)
  assert.match(interfaces, /\.interface-table-scroll\.is-empty\s*\{[\s\S]*?overflow:\s*hidden/)
})

test('API 测试子页面的列表、详情和选择器空状态应复用统一组件', () => {
  const parameterSets = read('src/views/ParameterSets.vue')
  const reports = read('src/views/Reports.vue')
  const executions = read('src/views/Executions.vue')

  assert.match(parameterSets, /import GlobalEmpty from ['"]@\/components\/GlobalEmpty\.vue['"]/
  )
  assert.match(parameterSets, /<GlobalEmpty[\s\S]*?v-else-if="!loading"/)
  assert.match(parameterSets, /action-text[\s\S]*?立即创建/)
  assert.match(reports, /<GlobalEmpty[\s\S]*?v-else-if="!groupLoading"[\s\S]*?没有匹配的用例/)
  assert.match(executions, /<GlobalEmpty[\s\S]*?v-else[\s\S]*?暂无可用执行策略，请管理员先启用执行策略/)
})
