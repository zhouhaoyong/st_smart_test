import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const view = readFileSync(new URL('../src/views/ParameterSetDetail.vue', import.meta.url), 'utf8')

assert.doesNotMatch(view, /class="usage-guide compact"/)
assert.doesNotMatch(view, /[🟢🟡🔵]/u)
assert.match(view, /参数引用：将接口或用例中的字面值替换为 \$\.key，运行时读取参数集中的当前值。/)
assert.match(view, /匹配规则：系统根据参数 Key 查找同名字段，并根据参数 Value 判断是否匹配/)
assert.match(view, /处理状态：“待参数化”表示可以执行替换；“已参数化”表示当前已经引用参数；“异常项”表示可能存在类型不匹配或引用冲突/)
assert.match(view, /参数位置：默认识别查询参数、路径参数和请求体；请求头默认不扫描，需要时开启“包含请求头”。/)
assert.match(view, /去参数化：可将已使用的 \$\.key 恢复为参数当前值，但不会删除参数本身。/)
assert.doesNotMatch(view, /把接口或用例中的可复用字面值替换为/)
assert.doesNotMatch(view, /从接口和用例中发现可复用参数；同一 Key 只保留一条正式候选/)
assert.match(view, /\.parameter-toolbar-row :deep\(\.el-button\)/)
assert.match(view, /\.parameter-toolbar-row :deep\(\.el-button\)[\s\S]*?height:\s*34px/)

console.log('参数化说明合并、去除 emoji 与工具栏按钮高度回归契约通过')
