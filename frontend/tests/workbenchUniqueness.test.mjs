import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const sharedSource = readFileSync(new URL('../../backend/api/v1/endpoints/test_workbench_routers/_shared.py', import.meta.url), 'utf8')
const structureSource = readFileSync(new URL('../../backend/api/v1/endpoints/test_workbench_routers/structure.py', import.meta.url), 'utf8')
const requirementSource = readFileSync(new URL('../../backend/api/v1/endpoints/test_workbench_routers/requirements.py', import.meta.url), 'utf8')
const testCaseSource = readFileSync(new URL('../../backend/api/v1/endpoints/test_workbench_routers/test_cases.py', import.meta.url), 'utf8')
const bugSource = readFileSync(new URL('../../backend/api/v1/endpoints/test_workbench_routers/bugs.py', import.meta.url), 'utf8')
const formSource = readFileSync(new URL('../src/views/test-workbench/components/WorkbenchAssetFormDialog.vue', import.meta.url), 'utf8')
const versionSchemaSource = readFileSync(new URL('../../backend/schemas/test_workbench.py', import.meta.url), 'utf8')
const assetListSource = readFileSync(new URL('../src/views/test-workbench/components/WorkbenchAssetListPage.vue', import.meta.url), 'utf8')
const testCasePageSource = readFileSync(new URL('../src/views/test-workbench/pages/WorkbenchTestCasePage.vue', import.meta.url), 'utf8')

assert.match(sharedSource, /async def ensure_project_unique_value/)
assert.match(structureSource, /TWSystem, data\.project_id, "name", data\.name, "系统名称"/)
assert.match(structureSource, /TWVersion, system\.project_id, "version_no", data\.version_no, "版本号"/)
assert.match(requirementSource, /TWRequirement, version\.project_id, "title", data\.title, "需求标题"/)
assert.match(testCaseSource, /TWTestCase, version\.project_id, "title", data\.title, "用例标题"/)
assert.match(bugSource, /TWBugRecord, version\.project_id, "title", data\.title, "Bug 标题"/)
assert.match(formSource, /assetType === 'legacy_item' \? '760px' : '620px'/)
assert.match(formSource, /white-space: nowrap/)
assert.match(formSource, /版本号低于当前项目已有最高版本/)
assert.match(formSource, /label="当前阶段" prop="current_stage"/)
assert.match(formSource, /current_stage: props\.assetType === 'version' \? \[\{ required: true, message: '请选择或输入当前阶段'/)
assert.match(versionSchemaSource, /class TWVersionCreate[\s\S]*?current_stage: str = Field\(min_length=1\)/)
// 编辑版本允许只改日期而不重传阶段，故 Update 里 current_stage 为可选
assert.match(versionSchemaSource, /class TWVersionUpdate[\s\S]*?current_stage: str \| None = None/)
assert.match(assetListSource, /isEditablePrimaryColumn\(column\)/)
assert.match(assetListSource, /class="editable-primary-field"/)
assert.match(assetListSource, /<el-button v-if="confirmTab === 'draft'" type="danger" plain/)
assert.doesNotMatch(testCasePageSource, /WorkbenchPageHeader/)

console.log('workbench uniqueness test ok')
