import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const parentSource = readFileSync(new URL('../src/views/TestWorkbench.vue', import.meta.url), 'utf8')
const listSource = readFileSync(new URL('../src/views/test-workbench/components/WorkbenchAssetListPage.vue', import.meta.url), 'utf8')

assert.match(parentSource, /assetListRefreshKey/)
assert.match(listSource, /watch\(assetListRefreshKey, loadAssets\)/)

console.log('workbench execution refresh test ok')
