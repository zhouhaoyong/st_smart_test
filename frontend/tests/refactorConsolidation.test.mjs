import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const testDir = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(testDir, '..')

const readSource = (...segments) => fs.readFileSync(path.join(projectRoot, ...segments), 'utf8')

const testWorkbenchApi = readSource('src', 'api', 'testWorkbench.js')
assert.match(testWorkbenchApi, /from ['"]@\/api\/aiStream['"]|from ['"]\.\/aiStream\.js['"]|from ['"]@\/api\/aiStream\.js['"]|from ['"]\.\/aiStream['"]/, '需求工作台接口应复用统一流式请求入口')
assert.doesNotMatch(testWorkbenchApi, /getReader\(\)|streamWorkbenchRequirementAiRaw/, '需求工作台接口不应继续维护第二套流式解析器')

for (const file of [
  ['src', 'views', 'Environments.vue'],
  ['src', 'views', 'Users.vue'],
  ['src', 'views', 'feedback', 'index.vue'],
  ['src', 'views', 'admin', 'AiModels.vue'],
  ['src', 'views', 'test-workbench', 'composables', 'useRequirementRefinement.js'],
]) {
  const source = readSource(...file)
  assert.doesNotMatch(source, /navigator\.clipboard\?*\.writeText|navigator\.clipboard\.writeText/, `${file.join('/')} 应复用统一剪贴板工具`)
}

console.log('refactor consolidation contract passed')
