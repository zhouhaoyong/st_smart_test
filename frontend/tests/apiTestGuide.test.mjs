import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { readFile } from 'node:fs/promises'

const projectPage = await readFile(new URL('../src/views/Projects.vue', import.meta.url), 'utf8')
const interfacesPage = await readFile(new URL('../src/views/Interfaces.vue', import.meta.url), 'utf8')
const interfaceCasesPage = await readFile(new URL('../src/views/InterfaceCases.vue', import.meta.url), 'utf8')
const guidePath = new URL('../src/components/ApiTestGuideDialog.vue', import.meta.url)
const guideExists = existsSync(guidePath)
const guideDialog = guideExists ? await readFile(guidePath, 'utf8') : ''
const workflowGuideBlock = interfacesPage.match(/<el-dialog[^>]*title="工作流指引"[\s\S]*?<\/el-dialog>/)?.[0] || ''
const statusGuidePane = workflowGuideBlock.match(/<el-tab-pane label="状态说明" name="status">([\s\S]*?)<\/el-tab-pane>/)?.[1] || ''

assert.match(projectPage, /使用指南/)
assert.match(projectPage, /ApiTestGuideDialog/)
assert.ok(guideExists, 'API 测试使用指南组件应该存在')
assert.match(guideDialog, /配置环境/)
assert.match(guideDialog, /导入接口文档/)
assert.match(guideDialog, /AI 生成用例/)
assert.match(guideDialog, /执行集/)
assert.match(guideDialog, /测试报告/)
const guideLabels = [...guideDialog.matchAll(/index:\s*'[^']+',\s*label:\s*'([^']+)'/g)].map(match => match[1])
assert.deepEqual(guideLabels, ['快速上手', '数据看板', '环境管理', '接口管理', '参数集管理', '执行集', '测试报告'])
assert.doesNotMatch(`${projectPage}\n${guideDialog}`, /URL\s*直接\s*导入/)
assert.match(workflowGuideBlock, /接口状态[\s\S]*待处理[\s\S]*已处理[\s\S]*用例状态[\s\S]*待确认[\s\S]*已确认/, '推荐工作流应解释接口和用例状态的含义')
assert.match(workflowGuideBlock, /<el-tabs v-model="workflowGuideTab"/, '推荐工作流应使用页签组织流程和状态说明')
assert.match(workflowGuideBlock, /<el-tab-pane label="工作流指引" name="workflow">/, '推荐工作流应保留为默认页签')
assert.match(workflowGuideBlock, /<el-tab-pane label="状态说明" name="status">/, '推荐工作流应提供状态说明页签')
assert.match(interfacesPage, /const workflowGuideTab = ref\('workflow'\)/, '每次打开引导时应默认展示推荐工作流')
assert.match(statusGuidePane, /接口状态/, '状态说明应包含接口状态')
assert.match(statusGuidePane, /待处理[\s\S]*接口定义待检查/, '状态说明应解释接口待处理颜色')
assert.match(statusGuidePane, /已处理[\s\S]*接口定义已检查/, '状态说明应解释接口已处理颜色')
assert.match(statusGuidePane, /用例状态/, '状态说明应包含用例状态')
assert.match(statusGuidePane, /待确认[\s\S]*参数、脚本和断言待检查/, '状态说明应解释用例待确认颜色')
assert.match(statusGuidePane, /已确认[\s\S]*用例已确认/, '状态说明应解释用例已确认颜色')
assert.match(statusGuidePane, /用例优先级[\s\S]*高[\s\S]*中[\s\S]*低/, '状态说明应解释用例优先级颜色')
assert.match(interfaceCasesPage, /function priorityTag\(priority\) \{[\s\S]*?return p === 'high' \? 'danger' : p === 'low' \? 'info' : 'warning'/, '用例管理页的中优先级应与执行集使用一致的橙色标签')
assert.match(workflowGuideBlock, /width="min\(680px, calc\(100vw - 48px\)\)"/, '推荐工作流弹窗应加宽并保留视口自适应')
assert.match(interfacesPage, /\.workflow-guide-list\s*\{[^}]*line-height:\s*1\.8;/, '推荐工作流列表应使用更舒适的正文行高')
assert.match(workflowGuideBlock, /版本迭代[\s\S]*待处理/, '推荐工作流应说明如何定位待处理接口')
assert.match(workflowGuideBlock, /设为[\s\S]*?已处理/, '推荐工作流应说明接口需要人工标记为已处理')
assert.match(workflowGuideBlock, /设为[\s\S]*?已确认/, '推荐工作流应说明用例需要人工标记为已确认')
assert.match(workflowGuideBlock, /待处理[\s\S]*待确认/, '推荐工作流应展示接口和用例的待处理状态')
assert.equal(
  (workflowGuideBlock.match(/workflow-guide-status__row/g) || []).length,
  2,
  '接口状态和用例状态应分两行展示',
)
assert.match(interfacesPage, /\.workflow-guide-status\s*\{[\s\S]*?flex-direction:\s*column;/, '状态区域应使用纵向布局避免标签挤在一行')
assert.match(interfacesPage, /\.workflow-guide-status__row\s*\{/, '状态区域应提供独立的行容器')
assert.match(workflowGuideBlock, /版本迭代[\s\S]*?<el-tag[^>]*>待处理<\/el-tag>/, '步骤文案应复用待处理状态标签')
assert.match(workflowGuideBlock, /手动标记为[\s\S]*?<el-tag[^>]*>已处理<\/el-tag>/, '步骤文案应复用已处理状态标签')
assert.match(workflowGuideBlock, /手动标记为[\s\S]*?<el-tag[^>]*>已确认<\/el-tag>/, '步骤文案应复用已确认状态标签')
assert.doesNotMatch(
  workflowGuideBlock,
  /“(待处理|已处理|待确认|已确认)”/,
  '状态标签旁不应重复使用文字引号',
)

console.log('apiTestGuide.test.mjs passed')
