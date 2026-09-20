import assert from 'node:assert/strict'

import { formatBeijingDate, formatBeijingMinute, formatBeijingTime } from '../src/utils/beijingTime.js'

const value = '2024-01-01T16:30:45.000Z'

assert.equal(formatBeijingTime(value), '2024-01-02 00:30:45')
assert.equal(formatBeijingMinute(value), '2024-01-02 00:30')
assert.equal(formatBeijingDate(value), '2024-01-02')
assert.equal(formatBeijingMinute(''), '')
assert.equal(formatBeijingDate(null), '')

console.log('beijing time helpers passed')
