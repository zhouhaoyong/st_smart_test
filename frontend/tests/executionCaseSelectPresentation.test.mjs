import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const executionsSource = read('../src/views/Executions.vue')
const interfacesSource = read('../src/views/Interfaces.vue')
const interfaceCasesSource = read('../src/views/InterfaceCases.vue')
const importDialogSource = read('../src/components/ImportDialog.vue')
const batchGenerationDialogSource = read('../src/components/BatchInterfaceCaseGenerationDialog.vue')
const dialogSource = read('../src/components/ExecutionCaseSelectDialog.vue')
const interfaceEditorSource = read('../src/components/InterfaceEditDialog.vue')
const caseDetailSource = read('../src/components/TestCaseEditDialog.vue')

assert.match(executionsSource, /ExecutionCaseSelectDialog/, '执行集页面应使用独立的选择用例组件')
assert.match(executionsSource, /getCasesByInterface/, '执行集页面仍应加载接口与用例树')
assert.match(executionsSource, /getCollectionTree/, '执行集页面应加载接口集统计信息')
assert.match(dialogSource, /CollectionNodeLabel/, '选择用例组件应复用公共接口集节点展示')
assert.match(dialogSource, /show-checkbox/, '选择用例仍应支持多选勾选')
assert.match(dialogSource, /全选/, '选择用例仍应保留全选操作')
assert.match(dialogSource, /checkedCaseIds\.length/, '选择用例应展示已选数量')
assert.match(dialogSource, /label="接口状态"/, '选择用例应提供接口状态筛选')
assert.match(dialogSource, /label="用例状态"/, '选择用例应提供用例状态筛选')
assert.match(dialogSource, /interfaceStatusProxy/, '接口状态筛选应由弹窗维护')
assert.match(dialogSource, /caseStatusProxy/, '用例状态筛选应由弹窗维护')
assert.match(dialogSource, /@change="handleFilterChange"/, '状态筛选变化应触发统一筛选处理')
assert.match(dialogSource, /width="min\(960px, calc\(100vw - 48px\)\)"/, '选择用例弹窗桌面端应适当加宽')
assert.match(dialogSource, /execution-case-select-filter-form/, '选择用例筛选项应使用统一筛选布局')
assert.match(dialogSource, /flex-wrap: nowrap/, '桌面端筛选项默认不应换行')
assert.match(dialogSource, /execution-case-select-filter-form[\s\S]*execution-case-select-toolbar__actions/, '筛选项和全选操作应位于同一工具栏')
assert.match(dialogSource, /toggleAllNodes\(!allVisibleCasesSelected\)/, '全选按钮应支持再次点击取消全选')
assert.match(dialogSource, /allVisibleCasesSelected \? '取消全选' : '全选'/, '全选按钮文案应跟随当前结果状态切换')
assert.match(dialogSource, /@media \(max-width: 960px\)[\s\S]*flex-wrap: wrap/, '窄屏下筛选项才允许自适应换行')
assert.match(dialogSource, /type === 'interface'/, '选择用例应继续展示接口节点')
assert.match(dialogSource, /type === 'case'/, '选择用例应继续展示用例节点')
assert.doesNotMatch(dialogSource, /data\.method/, '接口节点不应展示请求方法')
assert.match(dialogSource, /workflow_status/, '接口节点应展示接口状态')
assert.match(dialogSource, /workflow_status_label/, '接口节点应优先使用接口状态文案')
assert.match(dialogSource, /待处理/, '接口节点应支持待处理状态')
assert.match(dialogSource, /已处理/, '接口节点应支持已处理状态')
assert.match(dialogSource, /height: min\(420px, calc\(100vh - 280px\)\)/, '选择用例内容区应固定高度并在视口较小时收缩')
assert.doesNotMatch(dialogSource, /retainedIds/, '筛选后的已选用例不应保留不可见项')
assert.match(dialogSource, /collectCaseIds\(visibleFilteredTreeData\.value\)/, '全选应只覆盖当前筛选结果')
assert.match(dialogSource, /watch\(/, '筛选或选中集合变化后应同步树的可见勾选状态')
assert.match(dialogSource, /selectedCaseKeys/, '树的可见勾选状态应从完整已选用例集合恢复')
assert.match(dialogSource, /props\.checkedCaseIds/, '确认应使用父级维护的完整选中集合')
assert.match(executionsSource, /interfaceStatusFilter = ref\(''\)/, '执行集页面应维护接口状态筛选条件')
assert.match(executionsSource, /caseStatusFilter = ref\(''\)/, '执行集页面应维护用例状态筛选条件')
assert.match(executionsSource, /@filter="handleCaseTreeFilter"/, '执行集页面应在筛选变化时清空选择并刷新树')
assert.match(executionsSource, /checkedCaseIds\.value = \[\]/, '筛选条件变化后应清空已选用例')
assert.match(executionsSource, /workflow_status/, '执行集页面应按接口处理状态筛选')
assert.match(executionsSource, /confirm_status/, '执行集页面应按用例确认状态筛选')

const interfaceNodeSource = dialogSource.slice(
  dialogSource.indexOf("data.type === 'interface'"),
  dialogSource.indexOf("data.type === 'case'"),
)
const caseNodeSource = dialogSource.slice(
  dialogSource.indexOf("data.type === 'case'"),
  dialogSource.indexOf("data.type === 'case'", dialogSource.indexOf("data.type === 'case'") + 1),
)
assert.ok(
  interfaceNodeSource.indexOf('workflow_status') < interfaceNodeSource.indexOf('execution-case-select-interface-name'),
  '接口处理状态应展示在接口名称前面',
)
assert.ok(
  caseNodeSource.indexOf('confirm_status') < caseNodeSource.indexOf('execution-case-select-case-name'),
  '用例确认状态应展示在用例名称前面',
)
assert.match(dialogSource, /emit\('view-interface', data\)/, '点击接口节点应支持打开接口详情')
assert.match(dialogSource, /emit\('view-case', data\)/, '点击用例节点应支持打开用例详情')
assert.match(executionsSource, /@view-interface="openInterfaceDetail"/, '执行集页面应接收接口详情点击事件')
assert.match(executionsSource, /@view-case="openCaseDetail"/, '执行集页面应接收用例详情点击事件')
assert.match(executionsSource, /<InterfaceEditDialog/, '执行集页面应复用完整接口编辑弹窗')
assert.doesNotMatch(executionsSource, /<InterfaceDetailDialog/, '执行集页面不应继续使用简化接口详情弹窗')
assert.match(interfacesSource, /<InterfaceEditDialog/, '接口管理页应与执行集共用同一套接口编辑弹窗')
assert.match(interfaceCasesSource, /<InterfaceEditDialog/, '用例管理页应与接口管理页共用同一套接口编辑弹窗')
assert.doesNotMatch(interfaceCasesSource, /<el-dialog[\s\S]*title="编辑接口"/, '用例管理页不应保留独立的接口编辑弹窗')
assert.match(interfaceCasesSource, /@save="saveIface"/, '用例管理页的接口编辑应沿用统一保存回调')
assert.match(interfaceCasesSource, /body_schema_types/, '用例管理页打开接口详情时应保留请求体字段类型元数据')
assert.match(importDialogSource, /<InterfaceDetailDialog[\s\S]*:readonly="true"/, '导入预览中的接口详情应明确为只读')
assert.match(batchGenerationDialogSource, /<InterfaceDetailDialog[\s\S]*:readonly="true"/, 'AI生成预览中的接口详情应明确为只读')
assert.match(interfaceEditorSource, /InterfaceBasicFields/, '接口编辑弹窗应包含完整基础信息')
assert.match(interfaceEditorSource, /CollectionSingleSelect/, '接口编辑弹窗应支持所属接口集')
assert.match(interfaceEditorSource, /InterfaceRequestConfig/, '接口编辑弹窗应包含完整请求配置')
assert.match(interfaceEditorSource, /append-to-body/, '接口编辑弹窗应挂载到页面顶层，避免嵌套弹窗层级遮挡')
assert.match(interfaceEditorSource, /workflow_status/, '接口编辑弹窗应支持接口状态')
assert.match(executionsSource, /<TestCaseEditDialog/, '执行集页面应复用用例详情弹窗')
assert.match(executionsSource, /<TestCaseEditDialog[\s\S]*title="编辑用例"[\s\S]*:readonly="false"[\s\S]*:show-run="false"[\s\S]*@save="handleCaseDetailSave"/, '执行集中的用例详情应支持直接编辑并保存')
assert.match(caseDetailSource, /readonly: \{ type: Boolean, default: false \}/, '用例详情弹窗应支持只读模式')
assert.match(caseDetailSource, /showRun: \{ type: Boolean, default: true \}/, '用例编辑弹窗应支持按场景隐藏运行操作')
assert.match(caseDetailSource, /:disabled="props\.readonly"/, '用例只读模式不应允许修改表单')
assert.match(readFileSync(new URL('../src/components/InterfaceDetailDialog.vue', import.meta.url), 'utf8'), /readonly: \{ type: Boolean, default: false \}/, '接口详情弹窗应支持只读模式')

console.log('execution case selector detail presentation test ok')
