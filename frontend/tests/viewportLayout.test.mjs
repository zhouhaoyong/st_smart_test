import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const layoutSource = readFileSync(new URL('../src/layout/index.vue', import.meta.url), 'utf8')
const interfacesSource = readFileSync(new URL('../src/views/Interfaces.vue', import.meta.url), 'utf8')
const interfaceCasesSource = readFileSync(new URL('../src/views/InterfaceCases.vue', import.meta.url), 'utf8')
const environmentsSource = readFileSync(new URL('../src/views/Environments.vue', import.meta.url), 'utf8')
const interfacesTemplate = interfacesSource.slice(0, interfacesSource.indexOf('<script'))
const interfaceTreeTemplate = interfacesTemplate.slice(0, interfacesTemplate.indexOf('<!-- 右侧接口列表 -->'))
const interfacesVisibleTemplate = interfacesTemplate.slice(
  interfacesTemplate.indexOf('<div class="interfaces-container">'),
  interfacesTemplate.indexOf('<!-- 接口集对话框 -->')
)
const interfaceListTemplate = interfacesTemplate.slice(
  interfacesTemplate.indexOf('<el-table'),
  interfacesTemplate.indexOf('</el-table>')
)

test('固定高度页面只让接口管理和用例内容区承担滚动', () => {
  assert.match(layoutSource, /'fixed-content-page':\s*isFixedContentPage/)
  assert.match(layoutSource, /const isFixedContentPage = computed\(\(\) => \['Environments', 'Interfaces', 'InterfaceCases'\]\.includes\(route\.name\)\)/)
  assert.match(layoutSource, /\.main\.fixed-content-page\s*\{[\s\S]*?overflow:\s*hidden;/)
  assert.match(interfaceCasesSource, /\.cases-main\s*\{[\s\S]*?overflow:\s*hidden;/)
  assert.match(interfaceCasesSource, /\.cases-sidebar\s*\{[\s\S]*?border:\s*1px\s+solid/)
  assert.match(interfaceCasesSource, /\.cases-main\s*\{[\s\S]*?border:\s*1px\s+solid/)
  assert.match(interfaceCasesSource, /\.sidebar-list,\s*\.cards-grid\s*\{[\s\S]*?scrollbar-color:/)
  assert.match(environmentsSource, /\.env-grid\s*\{[\s\S]*?scrollbar-color:/)
})

test('接口管理页的目录树和表格在卡片内部滚动', () => {
  assert.match(interfacesSource, /\.interfaces-container\s*\{[\s\S]*?display:\s*flex;/)
  assert.match(interfacesSource, /\.tree-card, \.list-card\s*\{[\s\S]*?height:\s*100%;[\s\S]*?min-height:\s*0;/)
  assert.match(interfacesSource, /\.tree-card\s*\{[\s\S]*?overflow:\s*hidden;/)
  assert.match(interfacesSource, /\.interfaces-container :deep\(\.el-col\)\s*\{[\s\S]*?height:\s*100%;/)
  assert.match(interfacesSource, /\.collection-tree\s*\{[\s\S]*?flex:\s*1[\s\S]*?overflow-y:\s*auto;/)
  assert.match(interfacesTemplate, /<div class="interface-table-scroll">\s*<el-table/)
  assert.match(interfacesTemplate, /<\/el-table>\s*<\/div>\s*<el-pagination/)
  assert.match(interfacesSource, /\.interface-table-scroll\s*\{[\s\S]*?flex:\s*1[\s\S]*?min-height:\s*0[\s\S]*?overflow:\s*auto;/)
  assert.match(interfacesSource, /\.interface-table-scroll\s*\{[\s\S]*?scrollbar-color:/)
  assert.match(interfacesSource, /\.collection-tree::\-webkit-scrollbar,\s*\.interface-table-scroll::\-webkit-scrollbar\s*\{[\s\S]*?width:/)
  assert.match(interfacesSource, /\.list-card\s*:deep\(\.el-pagination\)\s*\{[\s\S]*?flex-shrink:\s*0;/)
  assert.match(interfacesSource, /const handleViewAll[\s\S]*?treeRef\.value\.setCurrentKey\(null\)/)
  assert.doesNotMatch(interfaceTreeTemplate, /<el-tooltip/)
  assert.doesNotMatch(interfacesVisibleTemplate, /<el-tooltip/)
  assert.doesNotMatch(interfaceListTemplate, /show-overflow-tooltip/)
})

test('用例管理页的左右区域独立滚动，标题不随卡片列表滚动', () => {
  assert.match(interfaceCasesSource, /\.cases-layout\s*\{[\s\S]*?height:\s*100%;/)
  assert.match(interfaceCasesSource, /\.sidebar-list\s*\{[\s\S]*?flex:\s*1[\s\S]*?overflow-y:\s*auto;/)
  assert.match(interfaceCasesSource, /\.cases-main\s*\{[\s\S]*?display:\s*flex[\s\S]*?flex-direction:\s*column[\s\S]*?overflow:\s*hidden;/)
  assert.match(interfaceCasesSource, /\.cards-grid\s*\{[\s\S]*?flex:\s*1[\s\S]*?min-height:\s*0[\s\S]*?overflow-y:\s*auto;/)
  assert.match(interfaceCasesSource, /\.sidebar-list,\s*\.cards-grid\s*\{[\s\S]*?scrollbar-color:/)
})

test('环境页的卡片列表在可用高度内滚动，配置摘要标签相对控件行居中', () => {
  assert.match(environmentsSource, /class="env-summary-form-item"/)
  assert.match(environmentsSource, /\.env-page\s*\{[\s\S]*?min-height:\s*0;[\s\S]*?overflow:\s*hidden;/)
  assert.match(environmentsSource, /\.env-grid\s*\{[\s\S]*?flex:\s*1[\s\S]*?min-height:\s*0;[\s\S]*?overflow-y:\s*auto;/)
  assert.match(environmentsSource, /\.env-summary-form-item\s*:deep\(\.el-form-item__label\)\s*\{[\s\S]*?display:\s*flex;[\s\S]*?align-items:\s*center;/)
})
