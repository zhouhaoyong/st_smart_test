import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const reports = readFileSync(new URL('../src/views/Reports.vue', import.meta.url), 'utf8')

assert.match(reports, /<el-dialog[^>]+title="消息发送记录"[^>]+width="760px"[^>]+class="send-log-dialog"/)
assert.match(reports, /class="send-log-table"/)
assert.match(reports, /channelLabel\(row\.channel_name\)/)
assert.match(reports, /class="send-log-time"/)
assert.match(reports, /send-log-time[\s\S]*white-space:\s*nowrap/)
assert.match(reports, /dingtalk:\s*'钉钉'/)
assert.match(reports, /feishu:\s*'飞书'/)
assert.match(reports, /wecom:\s*'企业微信'/)

console.log('report send logs display test ok')
