import assert from 'node:assert/strict'
import { buildAiUsageLogParams } from '../src/utils/aiUsageFilters.js'

assert.deepEqual(
  buildAiUsageLogParams({
    page: 2,
    pageSize: 50,
    scope: 'self',
    userName: '  周 ',
    phone: '',
    model: ' flash ',
    timeRange: ['2026-06-01', '2026-06-17'],
    includeStats: true,
  }),
  {
    page: 2,
    page_size: 50,
    scope: 'self',
    user_name: '周',
    model: 'flash',
    start_time: '2026-06-01 00:00:00',
    end_time: '2026-06-17 23:59:59',
    include_stats: true,
  },
)

assert.deepEqual(
  buildAiUsageLogParams({ page: 1, pageSize: 10, scope: 'all', userName: '', phone: '1500', includeStats: false }),
  {
    page: 1,
    page_size: 10,
    scope: 'all',
    phone: '1500',
    include_stats: false,
  },
)

assert.deepEqual(
  buildAiUsageLogParams({ timeRange: ['2026-06-17 09:30:00', '2026-06-17 18:45:30'] }),
  {
    page: 1,
    page_size: 10,
    scope: 'all',
    start_time: '2026-06-17 09:30:00',
    end_time: '2026-06-17 18:45:30',
  },
)

console.log('aiUsageFilters tests ok')
