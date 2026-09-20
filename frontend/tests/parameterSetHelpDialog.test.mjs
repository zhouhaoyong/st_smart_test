import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const view = readFileSync(new URL('../src/views/ParameterSets.vue', import.meta.url), 'utf8')

assert.match(view, /使用说明/)
assert.match(view, /参数集怎么用？/)
assert.match(view, /创建参数集/)
assert.match(view, /添加参数/)
assert.match(view, /引用参数/)
assert.match(view, /\$\.key/)
assert.match(view, /运行时会读取当前参数值，修改 Value 后无需逐个修改接口和用例。/)
assert.match(view, /const pageSize = ref\(10\)/)
assert.match(view, /getParameterSets\(projectId\.value, page\.value, pageSize\.value, \{ name: searchKeyword\.value \}\)/)
assert.match(view, /:page-sizes="\[10, 50, 100\]"/)
assert.match(view, /@size-change="onPageSizeChange"/)
assert.doesNotMatch(view, /const filteredList = computed/)
assert.doesNotMatch(view, /class="usage-guide"/)
assert.doesNotMatch(view, /<strong>1\. 创建参数集<\/strong>/)
assert.doesNotMatch(view, /<strong>2\. 添加参数<\/strong>/)
assert.doesNotMatch(view, /<strong>3\. 使用参数<\/strong>/)

console.log('参数集使用说明按钮与弹窗文案回归契约通过')
