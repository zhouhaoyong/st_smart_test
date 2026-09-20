import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

const utilityPath = new URL('../src/utils/aiModelPreference.js', import.meta.url)
assert.equal(existsSync(utilityPath), true, 'AI 模型偏好工具必须存在')

const { pickPreferredAiModelId, readLastAiModelId, rememberAiModel } = await import(utilityPath)
const batchGenerationDialog = readFileSync(new URL('../src/components/BatchInterfaceCaseGenerationDialog.vue', import.meta.url), 'utf8')
const modelSelectionPanel = readFileSync(new URL('../src/views/test-workbench/components/AiModelSelectionPanel.vue', import.meta.url), 'utf8')
const modelPickerDialog = readFileSync(new URL('../src/components/AiModelPickerDialog.vue', import.meta.url), 'utf8')
const generationPickerDialog = readFileSync(new URL('../src/components/AiGenerationModePickerDialog.vue', import.meta.url), 'utf8')
const refinementComposable = readFileSync(new URL('../src/views/test-workbench/composables/useRequirementRefinement.js', import.meta.url), 'utf8')

const candidates = [{ id: 11 }, { id: 22 }]
assert.equal(pickPreferredAiModelId(candidates, null, 22), 22)
assert.equal(pickPreferredAiModelId(candidates, 11, 22), 11)
assert.equal(pickPreferredAiModelId(candidates, 99, 22), 22)
assert.equal(pickPreferredAiModelId(candidates, 99, 88), 11)

const storage = {
  values: new Map(),
  getItem(key) { return this.values.get(key) ?? null },
  setItem(key, value) { this.values.set(key, value) },
}
assert.equal(readLastAiModelId(storage), null)
rememberAiModel(22, storage)
assert.equal(readLastAiModelId(storage), '22')
rememberAiModel(null, storage)
assert.equal(readLastAiModelId(storage), '22')

assert.match(batchGenerationDialog, /pickPreferredAiModelId/)
assert.match(batchGenerationDialog, /readLastAiModelId/)
assert.match(modelSelectionPanel, /rememberAiModel/)
assert.match(modelPickerDialog, /pickPreferredAiModelId/)
assert.match(generationPickerDialog, /pickPreferredAiModelId/)
assert.match(refinementComposable, /pickPreferredAiModelId/)

console.log('AI model preference regression test ok')
