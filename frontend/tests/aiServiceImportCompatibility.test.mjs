import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../../backend/services/ai_service/__init__.py', import.meta.url), 'utf8')
const sharedImport = source.match(/from \._shared import \(([\s\S]*?)\n\)/)?.[1] || ''

assert.doesNotMatch(sharedImport, /_AI_CALL_STAGE_LABELS/)
assert.match(sharedImport, /_ai_call_stage_name/)

console.log('AI 服务公共层导入兼容性回归校验通过')
