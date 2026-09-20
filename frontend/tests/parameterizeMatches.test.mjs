import assert from 'node:assert/strict'
import { categorizeParameterMatches, isParameterMatchReplaceable } from '../src/utils/parameterizeMatches.js'

const groups = categorizeParameterMatches([
  {
    key: 'project_id',
    results: [
      {
        type: 'interface',
        id: 1,
        _flatMatches: [
          { value: '1', replaced: '$.project_id', _checked: true },
          { value: '$.project_id', replaced: '$.project_id', _checked: false },
          { value: '$.other_id', replaced: '$.project_id', _checked: false },
          { value: '', replaced: '$.project_id', _checked: true },
          { value: '{}', replaced: '$.project_id', _checked: true },
          { value: '[]', replaced: '$.project_id', _checked: true },
          { value: 'null', replaced: '$.project_id', _checked: true },
          { value: 'None', replaced: '$.project_id', _checked: true },
        ],
      },
    ],
  },
])

assert.equal(groups.pending.length, 1)
assert.equal(groups.parameterized.length, 1)
assert.equal(groups.conflict.length, 1)
assert.equal(groups.pending[0].results[0]._flatMatches[0]._checked, true)
assert.equal(groups.parameterized[0].results[0]._flatMatches[0]._checked, false)
assert.equal(groups.conflict[0].results[0]._flatMatches.length, 6)
assert.equal(groups.conflict[0].results[0]._flatMatches[0]._checked, false)
assert.equal(groups.conflict[0].results[0]._flatMatches[1]._checked, false)
assert.equal(groups.conflict[0].results[0]._flatMatches[1].conflict_kind, 'empty_value')
assert.equal(groups.conflict[0].results[0]._flatMatches[2]._checked, false)
assert.equal(groups.conflict[0].results[0]._flatMatches[2].conflict_kind, 'empty_object')
assert.equal(groups.conflict[0].results[0]._flatMatches[3]._checked, false)
assert.equal(groups.conflict[0].results[0]._flatMatches[3].conflict_kind, 'empty_array')
assert.equal(groups.conflict[0].results[0]._flatMatches[4]._checked, false)
assert.equal(groups.conflict[0].results[0]._flatMatches[4].conflict_kind, 'null_value')
assert.equal(groups.conflict[0].results[0]._flatMatches[5]._checked, false)
assert.equal(groups.conflict[0].results[0]._flatMatches[5].conflict_kind, 'null_value')
assert.equal(isParameterMatchReplaceable(groups.conflict[0].results[0]._flatMatches[0], 'project_id'), true)
assert.equal(isParameterMatchReplaceable(groups.parameterized[0].results[0]._flatMatches[0], 'project_id'), true)

const mismatchGroups = categorizeParameterMatches([
  {
    key: 'test1',
    results: [
      {
        type: 'testcase',
        id: 2,
        _flatMatches: [
          {
            value: '{"name": "zhy"}',
            replaced: '$.test1',
            conflict_reason: '类型不匹配：参数 test1 为 string，接口字段 body.test1 为 object',
            _checked: true,
          },
        ],
      },
    ],
  },
])

assert.equal(mismatchGroups.pending.length, 0)
assert.equal(mismatchGroups.conflict.length, 1)
assert.equal(mismatchGroups.conflict[0].results[0]._flatMatches[0]._checked, true)
assert.equal(isParameterMatchReplaceable(mismatchGroups.conflict[0].results[0]._flatMatches[0], 'test1'), true)
