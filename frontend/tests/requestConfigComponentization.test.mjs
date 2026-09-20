import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  extractPathParameterNames,
  syncPathParametersFromUrl,
  syncUrlFromPathParameters,
  validatePathParameterUrl,
} from '../src/utils/pathParameterSync.js'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')

const interfaces = read('../src/views/Interfaces.vue')
const interfaceCases = read('../src/views/InterfaceCases.vue')
const detailDialog = read('../src/components/InterfaceDetailDialog.vue')
const sharedInterfaceEditor = read('../src/components/InterfaceEditDialog.vue')
const testCaseEditDialog = read('../src/components/TestCaseEditDialog.vue')
const requestConfig = read('../src/components/RequestConfigTabs.vue')
const paramEditTable = read('../src/components/ParamEditTable.vue')
const interfaceBasicFields = read('../src/components/InterfaceBasicFields.vue')

const curlDetailEditor = interfaces.match(
  /<!-- cURL 接口编辑弹窗 -->([\s\S]*?)<!-- 导入对话框 -->/
)?.[1] || ''
assert.match(interfaces, /<InterfaceEditDialog[\s\S]*:model="interfaceForm"/)
assert.match(interfaceCases, /<InterfaceEditDialog[\s\S]*:model="ifaceForm"/)
assert.match(sharedInterfaceEditor, /<InterfaceBasicFields[\s\S]*:form="props\.model"/)
assert.doesNotMatch(
  sharedInterfaceEditor,
  /<el-tab-pane label="查询参数"|<el-tab-pane label="路径参数"|<el-tab-pane label="请求体"|<el-tab-pane label="请求头"/
)

assert.match(detailDialog, /<RequestConfigTabs[\s\S]*:model="currentInterface"/)
assert.match(testCaseEditDialog, /<RequestConfigTabs[\s\S]*:model="model"/)
assert.doesNotMatch(detailDialog, /<el-table :data="currentInterface\.(query_params|path_params|headers)"/)

assert.match(curlDetailEditor, /<RequestConfigTabs[\s\S]*:model="curlDetailItem"/)
assert.doesNotMatch(curlDetailEditor, /<el-table :data="curlDetailItem\.(query_params|path_params|headers)"/)

assert.match(sharedInterfaceEditor, /<InterfaceRequestConfig[\s\S]*:model="props\.model"/)
assert.match(curlDetailEditor, /<InterfaceBasicFields[\s\S]*:form="curlDetailItem"/)
assert.match(sharedInterfaceEditor, /<InterfaceBasicFields[\s\S]*:form="props\.model"/)
assert.match(interfaceBasicFields, /label="接口名称"/)
assert.match(interfaceBasicFields, /label="请求方法"/)
assert.match(interfaceBasicFields, /label="URL"/)

for (const slot of ['body-toolbar-extra', 'body-content', 'body-after', 'headers-content']) {
  assert.match(requestConfig, new RegExp(`name="${slot}"`), `请求配置区域应提供 ${slot} 插槽`)
}

assert.deepEqual(extractPathParameterNames('/api/users/{id}/posts/{slug}/{id}'), ['id', 'slug'])
assert.equal(validatePathParameterUrl('/api/users/{id}}').valid, false, '多余花括号应被识别')
assert.equal(validatePathParameterUrl('/api/users/{id}/posts').valid, true)

const syncedParams = syncPathParametersFromUrl('/api/users/{id}/posts/{slug}', [
  { key: 'id', value: '42', description: '用户 ID' },
])
assert.deepEqual(syncedParams.map(item => item.key), ['id', 'slug'])
assert.equal(syncedParams[0].value, '42', 'URL 同步时应保留已有参数值')
assert.equal(syncedParams[1].required, true, '从 URL 识别出的路径参数默认必填')

assert.equal(
  syncUrlFromPathParameters('/api/users/{id}', [{ key: 'id' }], [{ key: 'user_id' }]),
  '/api/users/{user_id}',
)
assert.equal(
  syncUrlFromPathParameters('/api/users/{id}', [{ key: 'id' }], []),
  '/api/users',
)
assert.equal(
  syncUrlFromPathParameters('/api/users', [], [{ key: 'id' }]),
  '/api/users/{id}',
)
assert.equal(
  syncPathParametersFromUrl('/api/users/{user_id}', [{ key: 'id', value: '42' }])[0].value,
  '42',
  'URL 直接改名时应保留对应路径参数值',
)

assert.match(requestConfig, /watch\(\(\) => props\.model\?\.url/)
assert.match(requestConfig, /watch\(\(\) => props\.model\?\.path_params/)
assert.match(requestConfig, /deep:\s*true/)
assert.match(requestConfig, /暂无路径参数，请在 URL 中输入 \{参数名\}/)
assert.match(requestConfig, /<p v-if="pathParameterValidationMessage" class="path-parameter-validation"[\s\S]*<el-tabs v-model="tab"/)
assert.match(paramEditTable, /<el-button link type="primary" :icon="Plus" @click="addRow">\{\{ addLabel \}\}<\/el-button>/)

console.log('request config componentization structure test ok')
