import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/Executions.vue', import.meta.url), 'utf8')

assert.doesNotMatch(source, /<el-table-column prop="id" label="ID"/)
assert.match(source, /<el-table-column label="创建时间"/)
assert.match(source, /formatDate\(row\.created_at\)/)
assert.match(source, /<el-table :data="executionList"[\s\S]*?ref="execTableRef"/)
assert.match(source, /<template #empty><GlobalEmpty text="暂无数据" \/><\/template>/)
assert.match(source, /<el-table-column label="操作" width="160" fixed="right"/)
assert.match(source, /<el-table-column label="执行集名称"[\s\S]*?<el-link type="primary" @click="handleEdit\(row\)">\{\{ row\.name \}\}<\/el-link>/)
assert.match(source, /<el-table-column label="用例数" width="78" align="center">[\s\S]*?<el-link type="primary" underline="never" @click="handleEdit\(row\)">\{\{ row\.case_count \?\? 0 \}\}<\/el-link>/)
assert.match(source, /<el-tag[^>]+class="trigger-tag"[^>]+@click="handleEdit\(row\)"/)
assert.match(source, /<el-tag[^>]+style="cursor:pointer"[^>]+@click="handleEdit\(row\)">\{\{ row\.execution_mode/)
assert.match(source, /<el-button link type="primary" size="small" @click="handleEdit\(row\)">编辑<\/el-button>/)

console.log('执行集列表字段点击编辑入口、隐藏 ID 并保留创建时间展示回归校验通过')
