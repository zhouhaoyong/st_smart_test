import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { removeCollectionAncestorsFromSelection } from '../src/utils/interfaceCollections.js'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const treeSource = read('../src/views/Interfaces.vue')
const collectionLabelSource = read('../src/components/CollectionNodeLabel.vue')
const executionsSource = read('../src/views/Executions.vue')
const collectionsSource = read('../../backend/services/collection_tree.py')
const interfacesSource = read('../../backend/api/v1/endpoints/interfaces.py')

assert.match(treeSource, /CollectionNodeLabel/, '目录树应展示后端返回的递归接口数量和状态')
assert.doesNotMatch(treeSource, /<CollectionNodeLabel :node="data" :truncate="false" \/>/, '左侧接口集目录不应允许名称换行')
assert.match(collectionLabelSource, /truncate: \{ type: Boolean, default: true \}/, '目录标签应支持按场景关闭单行截断')
assert.match(collectionLabelSource, /collection-node-label\.is-wrapped/, '关闭截断后目录标签应允许换行展示')
assert.match(treeSource, /v-model="collectionForm\.name"[^>]*maxlength="20"[^>]*show-word-limit/, '接口集名称输入应限制为 20 个字并展示字数')
assert.match(treeSource, /const scheduleCollectionLoad = \(collectionId\) =>/, '接口集切换应通过调度器刷新列表')
assert.match(treeSource, /requestAnimationFrame/, '接口集切换应让选中态先完成首帧绘制')
assert.match(treeSource, /cancelAnimationFrame/, '连续切换接口集时应取消过期的刷新任务')
assert.doesNotMatch(treeSource, /@node-click="handleNodeClick"/, '展开箭头不应复用树组件级节点选中事件')
assert.match(treeSource, /class="custom-tree-node"[^>]*@click\.stop="handleNodeClick\(data\)"/, '节点右侧内容应负责选中接口集')
assert.match(treeSource, /@click\.stop="handleCreateSubCollection\(data\)"/, '新增按钮不应触发节点选中')
assert.match(treeSource, /@click\.stop="handleEditCollection\(data\)"/, '编辑按钮不应触发节点选中')
assert.match(treeSource, /@click\.stop="handleDeleteCollection\(data\)"/, '删除按钮不应触发节点选中')
assert.doesNotMatch(treeSource, /node\.expanded = !node\.expanded/, '接口集点击不应重复反转树组件已处理的展开状态')
assert.match(
  treeSource,
  /:deep\(\.el-tree-node\.is-current > \.el-tree-node__content:hover\)[\s\S]*?background-color:\s*#e6f4ff !important/,
  '鼠标停留在选中接口集上时仍应保持选中态背景',
)
assert.match(treeSource, /removeCollectionAncestorsFromSelection/, '批量删除取消子目录时应同步取消所有上级目录')
assert.match(collectionsSource, /"interface_count": total_count/, '目录树父节点数量应包含子目录接口')
assert.match(interfacesSource, /Interface\.collection_id\.in_\(collection_ids\)/, '父目录筛选应包含所有后代目录')
assert.doesNotMatch(treeSource, /genCaseColId|genCaseCols|选择用例集/, '生成用例入口不应继续依赖旧用例集')
assert.doesNotMatch(executionsSource, /用例集名称|并行加载所有用例集/, '执行集选择器不应保留旧用例集文案或死代码')
assert.match(treeSource, /class="interface-name-text"[^>]*@click="handleEdit\(row\)"/, '接口名称应继续支持点击查看详情')
assert.doesNotMatch(treeSource, /<el-table-column label="接口名称\/URL" width="200" fixed="left" show-overflow-tooltip>/, '接口名称和 URL 列不应再弹出悬停提示')
assert.doesNotMatch(treeSource, /class="interface-name-url-cell" :title=/, '接口名称和 URL 单元格不应再设置悬停标题')

const selectionTree = [
  {
    id: 1,
    children: [
      {
        id: 2,
        children: [
          { id: 3 },
          { id: 4 },
        ],
      },
    ],
  },
]

assert.deepEqual(
  removeCollectionAncestorsFromSelection(selectionTree, 3, [1, 2, 4]),
  [4],
  '取消深层子目录后应移除全部祖先，但保留其他分支',
)

console.log('collection tree scope test ok')
