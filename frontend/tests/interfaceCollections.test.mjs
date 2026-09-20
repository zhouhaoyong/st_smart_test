import assert from 'node:assert/strict'
import {
  INTERFACE_COLLECTION_IMPORT_GUIDE,
  findCollectionPath,
  flattenCollectionTreeForSelect,
  formatCollectionPath,
} from '../src/utils/interfaceCollections.js'

const tree = [
  {
    id: 1,
    name: 'PC端',
    children: [
      { id: 2, name: '用户模块', children: [] },
      {
        id: 3,
        name: '订单模块',
        children: [{ id: 4, name: '退款接口', children: [] }],
      },
    ],
  },
  { id: 5, name: 'H5端', children: [] },
]

assert.equal(
  INTERFACE_COLLECTION_IMPORT_GUIDE,
  '建议按端或系统选择根目录，便于后续查找和执行用例'
)

assert.deepEqual(flattenCollectionTreeForSelect(tree), [
  { id: 1, label: 'PC端', raw: tree[0] },
  { id: 2, label: '    └ 用户模块', raw: tree[0].children[0] },
  { id: 3, label: '    └ 订单模块', raw: tree[0].children[1] },
  { id: 4, label: '        └ 退款接口', raw: tree[0].children[1].children[0] },
  { id: 5, label: 'H5端', raw: tree[1] },
])

assert.deepEqual(findCollectionPath(tree, 4).map(item => item.name), ['PC端', '订单模块', '退款接口'])
assert.equal(formatCollectionPath(tree, { id: 4, name: '退款接口' }), 'PC端 / 订单模块 / 退款接口')
assert.equal(formatCollectionPath(tree, { id: '4', name: '退款接口' }), 'PC端 / 订单模块 / 退款接口')
assert.equal(formatCollectionPath(tree, { id: 99, name: '已删除接口集' }), '已删除接口集')
assert.equal(formatCollectionPath(tree, null), '-')

console.log('interfaceCollections tests ok')
