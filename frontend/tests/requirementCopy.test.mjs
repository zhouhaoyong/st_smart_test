import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const requirementPreview = readFileSync(
  new URL('../src/views/test-workbench/components/RequirementPreviewDrawer.vue', import.meta.url),
  'utf8',
)
const mergedPreview = readFileSync(
  new URL('../src/views/test-workbench/components/MergedRequirementDetailDrawer.vue', import.meta.url),
  'utf8',
)

assert.match(requirementPreview, /const copySource = computed\(\(\) => isCompleted\.value \? props\.detail\?\.markdown_content \|\| '' : props\.detail\?\.original_content \|\| ''\)/)
assert.match(requirementPreview, /@click="copyRequirement"/)
assert.match(mergedPreview, /const copySource = computed\(\(\) => props\.drawer\.data\?\.markdown_content \|\| ''\)/)
// 合并需求详情改成「编辑 / 实时预览」双栏后，复制正文按钮统一走 copyPreviewContent
assert.match(mergedPreview, /@click="copyPreviewContent"/)
assert.match(mergedPreview, /@click="copyEditingContent"/)

console.log('requirement copy source test ok')
