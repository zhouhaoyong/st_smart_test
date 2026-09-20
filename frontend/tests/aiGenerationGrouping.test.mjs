import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/components/BatchInterfaceCaseGenerationDialog.vue', import.meta.url), 'utf8')

assert.match(source, /class="case-preview-group-header"/)
assert.match(source, /casePreviewGroups/)
assert.match(source, /@click="toggleCasePreviewGroup\(group\.key\)"/)
assert.match(source, /expandedCasePreviewGroups = ref\(new Set\(\)\)/)
assert.match(source, /:aria-expanded="isCasePreviewGroupExpanded\(group\.key\)"/)
assert.match(source, /InterfaceDetailDialog/)
assert.match(source, /interfaceDetailVisible/)
assert.match(source, /function openInterfaceDetail\(iface\)/)
assert.doesNotMatch(source, /open-interface-detail/)
assert.match(source, /interfaceDetailVisible\.value = false/)
assert.match(source, /@click\.stop="openInterfaceDetail\(group\.iface\)"/)
assert.match(source, /class="case-preview-interface-detail"/)
assert.match(source, /class="case-preview-case-detail"/)
assert.match(source, /:style="casePreviewGroupStyle\(group\.key\)"/)
assert.match(source, /function casePreviewGroupStyle\(key\)/)
assert.match(source, /@save="onCaseSaved"/)
assert.match(source, /查看详情/)
assert.doesNotMatch(source, /打开详情/)
assert.doesNotMatch(source, /removeCase\(entry\.iface, entry\.caseIndex\)/)
