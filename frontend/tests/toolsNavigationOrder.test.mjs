import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const layoutSource = readFileSync(new URL('../src/layout/ToolsLayout.vue', import.meta.url), 'utf8')
const appLayoutSource = readFileSync(new URL('../src/layout/index.vue', import.meta.url), 'utf8')
const routerSource = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const topBarSource = readFileSync(new URL('../src/layout/TopBar.vue', import.meta.url), 'utf8')
const generateSource = readFileSync(new URL('../src/views/tools/GenerateTools.vue', import.meta.url), 'utf8')

const groupItems = (key) => {
  const match = layoutSource.match(new RegExp(`key: '${key}',[\\s\\S]*?items: \\[([\\s\\S]*?)\\n    \\],`))
  assert.ok(match, `未找到工具分组：${key}`)
  return [...match[1].matchAll(/\{ path: '([^']+)', label: '([^']+)'/g)].map(([, path, label]) => ({ path, label }))
}

test('文本处理和生成工具按指定顺序展示', () => {
  assert.deepEqual(groupItems('text'), [
    { path: '/tools/markdown-preview', label: 'Markdown预览' },
    { path: '/tools/json-format', label: 'JSON格式化' },
    { path: '/tools/json-path-extractor', label: 'JSONPath提取' },
    { path: '/tools/text-diff', label: '文本对比' },
    { path: '/tools/translate', label: '多语言翻译' },
    { path: '/tools/url-codec', label: 'URL 编解码' },
    { path: '/tools/base64', label: 'Base64' },
    { path: '/tools/hash', label: '哈希' },
  ])
  assert.deepEqual(groupItems('generate'), [
    { path: '/tools/id-card', label: '身份证生成' },
    { path: '/tools/qrcode', label: '二维码生成' },
    { path: '/tools/timestamp', label: '时间戳' },
    { path: '/tools/xmind', label: 'XMind用例' },
    { path: '/tools/geocode', label: '地址转经纬度' },
  ])
})

test('工具箱默认进入 Markdown 预览并统一身份证生成文案', () => {
  assert.match(topBarSource, /<router-link to="\/tools" class="topbar-tab" :class="\{ active: isToolModule \}">/)
  assert.match(routerSource, /path: '\/tools',[\s\S]*?redirect: '\/tools\/markdown-preview'/)
  assert.match(layoutSource, /path: '\/tools\/id-card', label: '身份证生成'/)
  assert.match(appLayoutSource, /ToolIdCard: '身份证'/)
  assert.match(routerSource, /path: 'id-card',[\s\S]*?meta: \{ title: '身份证生成', toolTab: 'idcard' \}/)
  assert.match(generateSource, /<el-tab-pane label="身份证生成" name="idcard">/)
})

console.log('tools navigation order test ok')
