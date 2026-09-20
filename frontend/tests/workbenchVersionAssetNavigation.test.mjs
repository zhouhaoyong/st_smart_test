import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const listSource = readFileSync(new URL('../src/views/test-workbench/components/WorkbenchAssetListPage.vue', import.meta.url), 'utf8')
const versionPage = readFileSync(new URL('../src/views/test-workbench/pages/WorkbenchVersionPage.vue', import.meta.url), 'utf8')
const requirementSource = readFileSync(new URL('../src/views/test-workbench/components/RequirementManagementPage.vue', import.meta.url), 'utf8')

assert.match(versionPage, /<WorkbenchAssetListPage asset-type="version"\s*\/>/)
assert.match(listSource, /assetType === 'version'/)
// 版本列表可通过路由 query 预选系统，并把筛选条件传给后端
assert.match(listSource, /system_id: props\.assetType === 'version' \? queryId\(route\.query\.system_id\) : undefined/)
assert.match(listSource, /@change="handleSystemChange"/)
assert.match(listSource, /system_id: props\.assetType === 'system' \? undefined : filters\.system_id/)
// 落地页读取范围改为统一的 workbenchContext（顶部项目/系统/版本选择器），不再各自解析 route.query
assert.match(requirementSource, /inject\('workbenchContext'\)/)
assert.match(requirementSource, /version_id: scope\.value\.version_id/)
// 操作列固定在右侧，列宽随资产类型的按钮数量计算
assert.match(listSource, /label="操作" :width="operationColumnWidth" fixed="right"/)
assert.match(listSource, /\.table-actions \{ display: flex;[\s\S]*white-space: nowrap;/)
assert.match(listSource, /white-space: nowrap/)
assert.match(listSource, /:style="\{ width: '100%' \}"/)

console.log('workbench version asset navigation test ok')
