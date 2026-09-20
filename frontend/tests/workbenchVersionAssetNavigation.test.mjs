import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const listSource = readFileSync(new URL('../src/views/test-workbench/components/WorkbenchAssetListPage.vue', import.meta.url), 'utf8')
const requirementSource = readFileSync(new URL('../src/views/test-workbench/components/RequirementManagementPage.vue', import.meta.url), 'utf8')

assert.match(listSource, /查看资产/)
assert.match(listSource, /TestWorkbenchRequirements/)
assert.match(listSource, /TestWorkbenchCases/)
assert.match(listSource, /TestWorkbenchBugs/)
assert.match(listSource, /TestWorkbenchLegacy/)
// 版本资产跳转仍通过 query 带上 system_id / version_id
assert.match(listSource, /route\.query\.system_id/)
assert.match(listSource, /query: \{ system_id: version\.system_id, version_id: version\.id \}/)
// 落地页读取范围改为统一的 workbenchContext（顶部项目/系统/版本选择器），不再各自解析 route.query
assert.match(requirementSource, /inject\('workbenchContext'\)/)
assert.match(requirementSource, /version_id: scope\.value\.version_id/)
// 操作列固定在右侧，列宽随资产类型的按钮数量计算
assert.match(listSource, /label="操作" :width="operationColumnWidth" fixed="right"/)
assert.match(listSource, /\.asset-navigation-actions \{ display: flex; flex-wrap: nowrap;/)
assert.match(listSource, /flex-wrap: nowrap/)
assert.match(listSource, /white-space: nowrap/)
assert.match(listSource, /:style="\{ width: '100%' \}"/)

console.log('workbench version asset navigation test ok')
