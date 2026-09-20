import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const projectPage = await readFile(new URL('../src/views/TestWorkbenchProjects.vue', import.meta.url), 'utf8')
const guideDialog = await readFile(new URL('../src/views/test-workbench/components/TestWorkbenchGuideDialog.vue', import.meta.url), 'utf8')

assert.match(projectPage, /使用指南/)
assert.match(projectPage, /TestWorkbenchGuideDialog/)
assert.match(guideDialog, /系统与版本/)
assert.match(guideDialog, /需求管理/)
assert.match(guideDialog, /待我处理/)
assert.match(guideDialog, /待我验证/)
assert.match(guideDialog, /待解决[\s\S]*已解决[\s\S]*已验证关闭/)

console.log('testWorkbenchGuide.test.mjs passed')
