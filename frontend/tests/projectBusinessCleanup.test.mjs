import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const page = readFileSync(new URL('../src/views/test-workbench/pages/WorkbenchDashboardPage.vue', import.meta.url), 'utf8')

assert.match(page, /const cleanupBusy = computed\(\(\) => cleanupDialog\.loading \|\| clearing\.value\)/)
assert.match(page, /:show-close="!cleanupBusy"/)
assert.match(page, /:close-on-press-escape="!cleanupBusy"/)
assert.match(page, /<el-button :disabled="cleanupBusy" @click="cleanupDialog\.visible = false">取消<\/el-button>/)
assert.match(page, /<el-button v-if="cleanupDialog\.step > 0" :disabled="cleanupBusy"/)
assert.match(page, /const formatCleanupResult = summary =>/)
assert.match(page, /ElMessage\.success\(formatCleanupResult\(result\)\)/)
assert.match(page, /刷新失败，请手动刷新页面/)

console.log('project business cleanup interaction test ok')
