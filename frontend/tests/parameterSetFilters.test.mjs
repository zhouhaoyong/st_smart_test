import assert from 'node:assert/strict'
import { filterParameterItems } from '../src/utils/parameterSetFilters.js'

const items = [
  { display_name: '项目ID', key: 'project_id', value: '1' },
  { display_name: '用户名称', key: 'username', value: 'alice' },
  { display_name: '年龄', key: 'age', value: '18' },
]

assert.deepEqual(filterParameterItems(items, { name: '项目' }).map(item => item.key), ['project_id'])
assert.deepEqual(filterParameterItems(items, { key: 'user' }).map(item => item.key), ['username'])
assert.deepEqual(filterParameterItems(items, { value: '1' }).map(item => item.key), ['project_id', 'age'])
assert.deepEqual(filterParameterItems(items, { name: '用户', key: 'name', value: 'ali' }).map(item => item.key), ['username'])

console.log('parameterSetFilters tests ok')
