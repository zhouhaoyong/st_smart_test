import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const usersSource = read('../src/views/Users.vue')
const endpointSource = read('../../backend/api/v1/endpoints/users.py')

assert.match(usersSource, /gender: 1/)
assert.match(endpointSource, /gender: int = 1/)

console.log('添加用户默认性别回归校验通过')
