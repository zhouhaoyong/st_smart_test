import assert from 'node:assert/strict'
import {
  getCollectionStatusType,
  getCollectionStatusHint,
} from '../src/utils/interfaceCollections.js'

assert.equal(
  getCollectionStatusType({ interface_count: 0 }),
  'empty',
  '没有接口的接口集应使用中性色',
)
assert.equal(
  getCollectionStatusType({ interface_count: 5, pending_interface_count: 1, done_interface_count: 4 }),
  'pending',
  '存在待处理接口时应使用警示色',
)
assert.equal(
  getCollectionStatusType({ interface_count: 5, pending_interface_count: 0, done_interface_count: 5 }),
  'done',
  '全部接口已处理时应使用成功色',
)
assert.equal(
  getCollectionStatusType({ interface_count: 5, pending_interface_count: 0, done_interface_count: 4 }),
  'pending',
  '状态汇总不完整时不能误显示为全部已处理',
)
assert.equal(
  getCollectionStatusHint({ interface_count: 5, pending_interface_count: 2 }),
  '共 5 个接口，其中 2 个待处理',
)
assert.equal(
  getCollectionStatusHint({ interface_count: 5, pending_interface_count: 0, done_interface_count: 5 }),
  '共 5 个接口，全部已处理',
)

console.log('collection tree status test ok')
