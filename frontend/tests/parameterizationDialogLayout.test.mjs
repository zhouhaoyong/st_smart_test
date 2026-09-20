import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const source = fs.readFileSync(path.resolve('src/views/ParameterSetDetail.vue'), 'utf8')
const api = fs.readFileSync(path.resolve('src/api/parameterSet.js'), 'utf8')

assert.match(source, /参数位置/)
assert.match(source, /multiple/)
assert.match(source, /全部（含请求头）/)
assert.doesNotMatch(source, /candIncludeHeaders/)
assert.match(source, /candLocations/)
assert.match(source, /@clear="clearCandidateLocations"/)
assert.match(source, /function clearCandidateLocations\(/)
assert.doesNotMatch(source, /selected\.length \? selected : \[\.\.\.defaultCandidateLocations\]/)
assert.match(api, /locations: options\.locations\.length \? options\.locations : \['none'\]/)
assert.match(api, /paramsSerializer: \{ indexes: null \}/)
assert.match(source, /参数位置：\{\{\s*parameterLocationLabel\(m\)\s*\}\}/)
assert.match(source, /class="param-target-card"/)
assert.match(source, /class="param-location-tag"/)
assert.match(source, /function isInterfaceGroupExpanded\(/)
assert.match(source, /return groupCount === 1/)
assert.match(source, /编辑参数/)
assert.match(source, /重新识别/)
assert.match(source, /parameterDrafts/)
assert.match(source, /hasUnidentifiedParameterDraftChanges/)
assert.match(source, /parameter_updates/)
assert.match(source, /parameter_set_id: psId\.value/)
assert.doesNotMatch(source, /<el-table-column label="创建来源"/)
assert.doesNotMatch(source, /<el-table-column label="类型来源"/)

const candidateToolbarStart = source.indexOf('<div class="candidate-query">')
const candidateToolbarEnd = source.indexOf('<el-tabs v-model="candidateActiveTab"', candidateToolbarStart)
const candidateToolbar = source.slice(candidateToolbarStart, candidateToolbarEnd)
assert.ok(candidateToolbar.indexOf('<el-input') < candidateToolbar.indexOf('<el-select'), '位置筛选应紧跟搜索输入框')
assert.ok(candidateToolbar.indexOf('<el-select') < candidateToolbar.indexOf('<el-button type="primary"'), '查询按钮应放在两个筛选项右侧')
assert.ok(candidateToolbar.indexOf('v-for="option in candidateLocationOptions"') < candidateToolbar.indexOf('label="全部（含请求头）"'), '全部选项应放在位置选项末尾')

console.log('parameterization dialog layout tests ok')
