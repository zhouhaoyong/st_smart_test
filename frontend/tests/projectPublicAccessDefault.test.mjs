import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const apiProjectsPage = readFileSync(new URL('../src/views/Projects.vue', import.meta.url), 'utf8')
const workbenchProjectsPage = readFileSync(new URL('../src/views/TestWorkbenchProjects.vue', import.meta.url), 'utf8')
const projectFormDialog = readFileSync(new URL('../src/components/ProjectFormDialog.vue', import.meta.url), 'utf8')

test('API 测试和测试工作台新建项目默认开启公开访问', () => {
  assert.match(apiProjectsPage, /const formData = reactive\(\{[^}]*is_public: true \}\)/s)
  assert.match(apiProjectsPage, /Object\.assign\(formData, \{[^}]*is_public: true \}\)/s)
  assert.match(workbenchProjectsPage, /const formData = reactive\(\{[^}]*is_public: true \}\)/s)
  assert.match(workbenchProjectsPage, /Object\.assign\(formData, \{[^}]*is_public: true \}\)/s)
})

test('API 测试和测试工作台项目页都保留响应式表单依赖', () => {
  for (const pageSource of [apiProjectsPage, workbenchProjectsPage]) {
    assert.match(pageSource, /import \{ ref, reactive, onMounted \} from 'vue'/)
  }
})

test('公开访问说明文案与开关保持清晰间距并支持换行', () => {
  assert.match(
    projectFormDialog,
    /<div class="public-access-row">\s*<el-switch v-model="formData\.is_public" size="large" \/>\s*<span class="form-tip">开启后其他人可只读访问<\/span>\s*<\/div>/s,
  )
  assert.match(
    projectFormDialog,
    /\.public-access-row\s*\{[\s\S]*?display:\s*flex;[\s\S]*?align-items:\s*center;[\s\S]*?gap:\s*12px;[\s\S]*?flex-wrap:\s*wrap;/s,
  )
  assert.match(projectFormDialog, /\.public-access-row \.form-tip\s*\{[\s\S]*?margin-top:\s*0;/s)
})

console.log('project public access default test ok')
