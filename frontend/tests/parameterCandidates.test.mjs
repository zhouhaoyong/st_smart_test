import assert from 'node:assert/strict'
import { candidateIgnoredReasonLabel, splitParameterCandidates } from '../src/utils/parameterCandidates.js'

const candidates = [
  { key: 'account_type', value: '1', type: 'int', candidate_status: 'normal', sources: [] },
  { key: 'needs_value', value: '', type: 'int', candidate_status: 'empty', sources: [] },
  { key: 'invalid_value', value: 'invalid_type', type: 'int', candidate_status: 'invalid', sources: [] },
  { key: 'conflict', value: '', type: '', candidate_status: 'type_conflict', sources: [] },
  { key: 'existing', value: 'old', type: 'string', candidate_status: 'normal', sources: [] },
]

const { visible, review, existing, invalid } = splitParameterCandidates(candidates, [{ key: 'existing' }])

assert.deepEqual(visible.map(item => item.key), ['account_type'])
assert.deepEqual(review.map(item => item.key), ['needs_value', 'conflict'])
assert.deepEqual(existing.map(item => item.key), ['existing'])
assert.deepEqual(invalid.map(item => item.key), ['invalid_value'])
assert.equal(review[0].ignored_reason, 'empty_value')
assert.equal(review[1].ignored_reason, 'type_conflict')
assert.equal(candidateIgnoredReasonLabel('existing'), '已存在')
assert.equal(candidateIgnoredReasonLabel('existing_value'), '值已存在')
assert.equal(candidateIgnoredReasonLabel('parameterized'), '已参数化')
assert.equal(candidateIgnoredReasonLabel('empty_value'), '待补充')
assert.equal(candidateIgnoredReasonLabel('type_conflict'), '类型冲突')

console.log('parameterCandidates tests ok')
