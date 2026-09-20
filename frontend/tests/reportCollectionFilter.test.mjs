import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const reports = read('../src/views/Reports.vue')
const panel = read('../src/components/CollectionCascadePanel.vue')
const endpoint = read('../../backend/api/v1/endpoints/reports.py')

assert.match(reports, /<el-form-item label="接口集"/, '报告筛选应展示接口集字段标签')
assert.match(reports, /<el-form-item label="用例名称"/, '报告筛选应展示用例名称字段标签')
assert.match(reports, /<el-form-item label="状态"/, '报告筛选应展示状态字段标签')
assert.match(reports, /class="report-filter-item[^>]*"/, '报告筛选项应使用统一的表单项布局')
assert.match(reports, /<el-cascader/, '报告筛选应使用统一的级联选择框')
assert.match(reports, /placeholder="全部接口集"/, '报告筛选应使用统一的默认提示')
assert.match(reports, /collapse-tags/, '报告筛选应折叠多个选中标签')
assert.match(reports, /checkStrictly: true/, '报告筛选应允许独立选择父级与子级')
assert.match(reports, /multiple: true/, '报告筛选应支持多选接口集')
assert.match(reports, /collection-node-label__count.*el-color-warning/, '报告接口集数量应使用橙色提示')
assert.match(reports, /const groupCollectionFilter = ref\(\[\]\)/, '报告接口集筛选应保存多个选中值')
assert.match(reports, /interface_collection_ids/, '报告查询应提交多个接口集 ID')
assert.match(reports, /groupCollectionFilter\.value\.join\(['"]?,['"]?\)/, '报告查询应把多选值编码为接口参数')
assert.match(reports, /collection_tree/, '报告接口集选项应使用树形数据')
assert.match(reports, /groupCollectionFilter\.value = \[\]/, '报告筛选重置应清空多选值')
assert.doesNotMatch(reports, /CollectionCascadePanel/, '报告筛选不应使用与图2不一致的自定义弹层')
assert.match(reports, /\.report-filter-item\s*\{[^}]*height:\s*32px/, '报告筛选项应统一控件高度')

assert.match(panel, /multiple: \{ type: Boolean/, '共享级联面板应支持多选模式')
assert.match(panel, /role="checkbox"|multiple \? 'checkbox'/, '共享级联面板应保留复选框语义')
assert.match(panel, /selectedIds/, '共享级联面板应维护多个选中接口集')

assert.match(endpoint, /interface_collection_ids: str \| None = None/, '报告接口应接收多个接口集 ID')
assert.match(endpoint, /get_descendant_collection_ids/, '报告接口应展开选中接口集的所有后代')
assert.match(endpoint, /Interface\.collection_id\.in_\(/, '报告接口应按展开后的接口集集合过滤')
assert.match(endpoint, /"collection_tree"\s*:/, '报告接口应返回树形接口集选项')

console.log('report collection filter contract test ok')
