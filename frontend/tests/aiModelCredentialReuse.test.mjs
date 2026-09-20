import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const currentDir = path.dirname(fileURLToPath(import.meta.url))
const source = fs.readFileSync(
  path.resolve(currentDir, '../src/views/admin/AiModels.vue'),
  'utf8',
)
const capabilityStart = source.indexOf('async function testCapabilities()')
const draftStart = source.indexOf('const payload = {', capabilityStart)
const draftEnd = source.indexOf('res = await testAiModelCapabilitiesDraft(payload', draftStart)
assert.notEqual(capabilityStart, -1)
assert.notEqual(draftStart, -1)
assert.notEqual(draftEnd, -1)

const draftPayload = source.slice(draftStart, draftEnd)
assert.match(draftPayload, /model_id:\s*editingId\.value/)
assert.doesNotMatch(draftPayload, /savedApiKey/)

const capabilityResetStart = source.indexOf('function resetCapabilityStateForConfigChange()')
const capabilityResetEnd = source.indexOf('const connectivityLabel', capabilityResetStart)
assert.notEqual(capabilityResetStart, -1)
assert.notEqual(capabilityResetEnd, -1)

const modelWatcher = source.slice(capabilityResetStart, capabilityResetEnd)
assert.match(modelWatcher, /watch\(\s*\(\) => form\.value\.model/)
assert.match(modelWatcher, /!formVisible\.value/)
assert.match(modelWatcher, /resetCapabilityStateForConfigChange\(\)/)
assert.match(modelWatcher, /connectivityVerified\.value = false/)
assert.match(modelWatcher, /testedConnectionFingerprint\.value = \'\'/)
assert.match(modelWatcher, /editingReasoningStatus\.value = \'unknown\'/)
assert.match(modelWatcher, /editingUsageStatus\.value = \'unknown\'/)
assert.match(modelWatcher, /flush:\s*\'sync\'/)

console.log('AI model credential reuse and capability invalidation contracts passed')
