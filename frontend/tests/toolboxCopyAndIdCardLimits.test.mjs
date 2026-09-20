import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const copyButton = readFileSync(
  new URL('../src/components/CopyButton.vue', import.meta.url),
  'utf8',
)
const generateTools = readFileSync(
  new URL('../src/views/tools/GenerateTools.vue', import.meta.url),
  'utf8',
)

test('toolbox copy button has no hover tooltip while retaining an accessible label', () => {
  assert.doesNotMatch(copyButton, /<el-tooltip/)
  assert.match(copyButton, /:aria-label="tooltip"/)
})

test('ID card generation UI allows up to one hundred records', () => {
  assert.match(generateTools, /v-model="id\.form\.count" :min="1" :max="100"/)
})
