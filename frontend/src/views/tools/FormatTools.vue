<template>
  <div class="tool-page">
    <div class="page-header">
      <h2>{{ pageTitle }}</h2>
      <el-button v-if="activeTab === 'markdown'" type="primary" plain @click="markdownExamplesVisible = true">
        <el-icon><Document /></el-icon>
        常见语法示例
      </el-button>
    </div>
    <el-card>
      <el-tabs v-model="activeTab" class="format-tabs">
        <el-tab-pane label="JSON" name="json">
          <div class="split-editor">
            <section class="editor-panel">
              <div class="panel-title">
                <span class="panel-label">输入</span>
                <CopyButton :value="json.input" label="复制" tooltip="复制输入内容" />
              </div>
              <el-input
                v-model="json.input"
                type="textarea"
                :rows="16"
                placeholder='粘贴 JSON 字符串，例如：{"name":"智测","version":"1.0"}'
                @input="jsonClearInputResult"
              />
            </section>
            <section class="editor-panel">
              <div class="panel-title">
                <span class="panel-label">输出</span>
                <CopyButton :value="json.output" label="复制" tooltip="复制结果" />
              </div>
              <el-input v-model="json.output" type="textarea" :rows="16" readonly placeholder="结果" class="json-output" />
            </section>
          </div>
          <div class="action-bar">
            <el-button type="primary" @click="jsonFormat" :loading="json.loading">
              <el-icon :size="16"><Operation /></el-icon> 格式化
            </el-button>
            <el-button @click="jsonCompress" :loading="json.loading">
              <el-icon :size="16"><Switch /></el-icon> 压缩
            </el-button>
            <el-button type="success" @click="jsonValidate" :loading="json.loading">
              <el-icon :size="16"><CircleCheck /></el-icon> 校验
            </el-button>
            <el-button @click="jsonClear"><el-icon :size="16"><Delete /></el-icon> 清空</el-button>
          </div>
          <div v-if="json.error" class="json-error">
            <el-alert :title="json.error" type="error" show-icon :closable="false" />
          </div>
          <div v-if="json.stats" class="json-stats">{{ json.stats }}</div>
        </el-tab-pane>

        <el-tab-pane label="Markdown" name="markdown">
          <div class="md-layout">
            <el-card class="md-card" shadow="never">
              <template #header><span class="panel-label">编辑</span></template>
              <textarea
                ref="mdTextareaRef"
                v-model="md.input"
                class="md-textarea"
                placeholder="输入 Markdown 文本..."
                spellcheck="false"
                @scroll="onEditorScroll"
              />
            </el-card>
            <el-card class="md-card" shadow="never">
              <template #header>
                <div style="display:flex;align-items:center;justify-content:space-between">
                  <span class="panel-label">预览</span>
                  <CopyButton :value="mdRendered" label="复制 HTML" tooltip="复制 HTML" />
                </div>
              </template>
              <div class="md-preview-wrapper">
                <div ref="mdPreviewRef" class="md-preview" v-html="mdRendered" @scroll="onPreviewScroll" />
                <div v-if="mdToc.length > 0" class="md-toc">
                  <div class="md-toc-title">目录</div>
                  <a
                    v-for="(item, i) in mdToc"
                    :key="i"
                    :class="['md-toc-item', `md-toc-level-${item.level}`]"
                    :title="item.text"
                    @click.prevent="mdScrollToHeading(item.id)"
                  >{{ item.text }}</a>
                </div>
              </div>
            </el-card>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
    <el-dialog
      v-model="markdownExamplesVisible"
      class="markdown-example-dialog"
      title="常见语法示例"
      width="min(1100px, 92vw)"
      top="5vh"
    >
      <p class="markdown-example-intro">左侧查看 Markdown 源码，右侧查看渲染效果；示例仅供查看，不会修改当前编辑内容。</p>
      <div class="markdown-example-layout">
        <section class="markdown-example-panel">
          <div class="markdown-example-panel-title">示例源码</div>
          <textarea
            ref="markdownExampleSourceRef"
            class="markdown-example-source"
            :value="markdownSyntaxExample"
            readonly
            spellcheck="false"
            @scroll="onMarkdownExampleSourceScroll"
          />
        </section>
        <section class="markdown-example-panel">
          <div class="markdown-example-panel-title">预览效果</div>
          <div
            ref="markdownExamplePreviewRef"
            class="markdown-example-preview"
            v-html="markdownSyntaxRendered"
            @scroll="onMarkdownExamplePreviewScroll"
          />
        </section>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, Operation, Switch, CircleCheck, Delete } from '@element-plus/icons-vue'
import CopyButton from '@/components/CopyButton.vue'
import { renderMarkdown } from '@/utils/markdown'
import { getEditorScrollTopForHeading, getSyncedScrollTopByRatio } from '@/utils/markdownScrollSync'

const activeTab = ref('json')
const route = useRoute()
const pageTitle = computed(() => route.meta.title || '格式处理')

watch(
  () => route.meta.toolTab,
  (tab) => {
    activeTab.value = tab || 'json'
  },
  { immediate: true },
)

const json = reactive({ input: '', output: '', error: '', stats: '', loading: false })

const countNodes = (obj, depth = 0) => {
  if (obj === null || typeof obj !== 'object') return 1
  let count = depth === 0 ? 1 : 0
  for (const val of Object.values(obj)) count += countNodes(val, depth + 1)
  return count
}

const jsonProcess = (action) => {
  if (!json.input.trim()) { ElMessage.warning('请输入 JSON'); return }
  json.loading = true
  setTimeout(() => {
    try {
      const obj = JSON.parse(json.input)
      json.output = action === 'compress' ? JSON.stringify(obj) : JSON.stringify(obj, null, 2)
      json.error = ''
      json.stats = action === 'compress'
        ? `压缩成功 - ${json.output.length.toLocaleString()} 字符`
        : `格式化成功 - ${countNodes(obj)} 个节点, ${json.output.length.toLocaleString()} 字符`
      ElMessage.success(action === 'compress' ? '压缩成功' : '格式化成功')
    } catch (e) {
      json.error = `解析错误: ${e.message}`
      json.output = ''
      json.stats = ''
    }
    json.loading = false
  }, 50)
}

const jsonFormat = () => jsonProcess('format')
const jsonCompress = () => jsonProcess('compress')

const jsonValidate = () => {
  if (!json.input.trim()) { ElMessage.warning('请输入 JSON'); return }
  json.loading = true
  setTimeout(() => {
    try {
      const obj = JSON.parse(json.input)
      json.output = JSON.stringify(obj, null, 2)
      json.error = ''
      json.stats = `JSON 校验通过 - ${countNodes(obj)} 个节点`
      ElMessage.success('JSON 格式正确')
    } catch (e) {
      const msg = e.message
      const posMatch = msg.match(/position\s+(\d+)/i) || msg.match(/at line (\d+) column (\d+)/i)
      let detail = msg
      if (posMatch) {
        const pos = parseInt(posMatch[1])
        const lines = json.input.substring(0, pos).split('\n')
        const line = lines.length
        const col = pos - json.input.substring(0, pos).lastIndexOf('\n')
        detail = `第 ${line} 行, 第 ${col} 列: ${msg}`
      }
      json.error = detail
      json.output = ''
      json.stats = ''
      ElMessage.error('JSON 格式错误')
    }
    json.loading = false
  }, 50)
}

const jsonClear = () => { json.input = ''; json.output = ''; json.error = ''; json.stats = '' }
const jsonClearInputResult = () => { json.error = ''; json.stats = '' }

const markdownSample = `# 智测

欢迎使用 **Markdown 预览** 工具。

## 功能

- 实时预览
- GitHub 风格 Markdown
- 代码高亮

\`\`\`js
console.log('Hello, 智测！')
\`\`\`

> 智测 - 综合性开发工具平台`

const markdownSyntaxExample = `# Markdown 语法示例

欢迎使用 **Markdown 预览** 工具。下面集中展示常见的 Markdown 与 GitHub Flavored Markdown（GFM）写法。

## 1. 标题与段落

# 一级标题
## 二级标题
### 三级标题
#### 四级标题
##### 五级标题
###### 六级标题

这是一个普通段落。Markdown 会自动处理连续文本和段落间距。

这一行末尾有两个空格  
因此会强制换行；也可以使用 HTML 换行标签<br>继续下一行。

---

## 2. 字体与行内语法

- **粗体文字**
- *斜体文字*
- ***粗斜体文字***
- ~~删除线文字~~
- \`行内代码\`
- [普通链接](https://www.example.com "链接标题")
- <https://www.example.com>
- <markdown@example.com>
- \*转义特殊字符，不会变成斜体\*
- 使用反斜杠转义：\\ \\* \\_ \\# \\[ \\]

快捷键示例：<kbd>Ctrl</kbd> + <kbd>S</kbd>

## 3. 链接与图片

这是一个[带标题的链接](https://www.example.com "Example 网站")。

也可以使用引用式链接：[智测官网][smart-test]。

[smart-test]: https://www.example.com "智测示例链接"

![智测图标](/favicon.svg "智测图标")

## 4. 无序列表

- 第一项
- 第二项
  - 二级项目
  - 二级项目中的内容
    - 三级项目
- 第三项

也可以使用其他符号：

* 星号项目
* 仍然是同一类列表

+ 加号项目
+ 仍然是同一类列表

## 5. 有序列表

1. 第一步：准备数据
2. 第二步：调用接口
   1. 校验请求参数
   2. 发送请求
3. 第三步：检查响应

## 6. 任务列表

- [x] 完成 Markdown 解析
- [x] 完成实时预览
- [ ] 增加更多示例
- [ ] 发布到生产环境

## 7. 引用

> 这是一段普通引用。
>
> Markdown 适合编写接口说明、测试报告和项目文档。
>
> > 这是嵌套引用。
> >
> > 可以在引用中继续使用 **粗体**、\`代码\` 和列表：
> >
> > - 引用中的列表项
> > - 另一个列表项

## 8. 表格

| 字段 | 类型 | 是否必填 | 说明 |
| :--- | :---: | :---: | ---: |
| name | string | 是 | 用户名称 |
| age | number | 否 | 用户年龄 |
| enabled | boolean | 否 | 是否启用 |

表格中也可以使用 **粗体**、\`代码\` 和[链接](https://www.example.com)。

## 9. 代码块

JavaScript：

\`\`\`js
const request = {
  method: 'GET',
  url: '/api/users',
  enabled: true,
}

console.log(request)
\`\`\`

JSON：

\`\`\`json
{
  "name": "智测",
  "version": "1.0.0",
  "features": ["API 测试", "Markdown 预览"]
}
\`\`\`

Python：

\`\`\`python
def greet(name: str) -> str:
    return f"Hello, {name}!"

print(greet("Markdown"))
\`\`\`

Shell：

\`\`\`bash
docker compose up -d --build
\`\`\`

无语言标记的代码块：

    这是缩进四个空格的代码块
    可以保留空格和换行

## 10. 分隔线与特殊字符

下面是三种常见的分隔线写法：

---

***

___

特殊字符：\*星号\*、\_下划线\_、\#井号、\[方括号\]、\|竖线。

## 11. 行内 HTML

Markdown 也支持部分行内 HTML，例如：<mark>高亮文字</mark>、<sub>下标</sub>、<sup>上标</sup>。

<details>
<summary>点击展开更多说明</summary>

这是一个 HTML details 区块。最终内容仍会经过安全过滤。

</details>

## 12. 综合示例

### 接口说明：获取用户信息

> 用于根据用户 ID 获取用户详情。

**请求方法：** \`GET\`

**请求地址：** \`/api/users/{id}\`

**请求参数：**

| 参数 | 位置 | 类型 | 示例 |
| --- | --- | --- | --- |
| id | Path | number | 10001 |
| token | Header | string | Bearer ****** |

**响应示例：**

\`\`\`json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 10001,
    "name": "张三"
  }
}
\`\`\`

- [x] 返回 HTTP 200
- [x] 返回用户信息
- [ ] 增加异常场景断言

---

> 智测 - 综合性开发工具平台`


const markdownSyntaxRendered = computed(() => renderMarkdown(markdownSyntaxExample))
const markdownExamplesVisible = ref(false)
const markdownExampleSourceRef = ref(null)
const markdownExamplePreviewRef = ref(null)
let markdownExampleScrollRaf = 0
const markdownExampleIgnoreScrollFrom = new Set()
let markdownExampleIgnoreScrollTimer = null

const md = reactive({
  input: markdownSample,
})

const mdPreviewRef = ref(null)
const mdTextareaRef = ref(null)
let mdScrollRaf = 0
let mdIgnoreScrollFrom = new Set()
let mdIgnoreScrollTimer = null

const mdRendered = computed(() => {
  const html = renderMarkdown(md.input)
  // 给每个标题注入 id 用于目录锚点跳转
  let idx = 0
  return html.replace(/<(h[1-3])>/g, (_, tag) => {
    idx++
    return `<${tag} id="md-heading-${idx}">`
  })
})

// 从原始 Markdown 提取标题生成目录
const mdToc = computed(() => {
  const headings = []
  const lines = md.input.split('\n')
  let idx = 0
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const m = line.match(/^(#{1,3})\s+(.+)/)
    if (m) {
      idx++
      headings.push({ level: m[1].length, text: m[2].trim(), line: i, id: `md-heading-${idx}` })
    }
  }
  // 给每个标题分配与 mdRendered 中一致的 id
  return headings
})

function _mdMaxScroll(el) {
  return Math.max(0, (el?.scrollHeight || 0) - (el?.clientHeight || 0))
}

function _mdClamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function _mdLineHeight() {
  const ta = mdTextareaRef.value
  if (!ta) return 22
  return parseFloat(getComputedStyle(ta).lineHeight) || 22
}

function _mdHeadingTop(container, heading) {
  if (!container || !heading?.id) return null
  const el = container.querySelector(`#${heading.id}`)
  if (!el) return null
  const containerRect = container.getBoundingClientRect()
  const elRect = el.getBoundingClientRect()
  return container.scrollTop + elRect.top - containerRect.top
}

function _mdPreviewTopFromEditor() {
  const ta = mdTextareaRef.value
  const pv = mdPreviewRef.value
  if (!ta || !pv) return 0
  return getSyncedScrollTopByRatio({
    sourceScrollTop: ta.scrollTop,
    sourceScrollHeight: ta.scrollHeight,
    sourceClientHeight: ta.clientHeight,
    targetScrollHeight: pv.scrollHeight,
    targetClientHeight: pv.clientHeight,
  })
}

function _mdEditorTopFromPreview() {
  const pv = mdPreviewRef.value
  const ta = mdTextareaRef.value
  if (!pv || !ta) return 0
  return getSyncedScrollTopByRatio({
    sourceScrollTop: pv.scrollTop,
    sourceScrollHeight: pv.scrollHeight,
    sourceClientHeight: pv.clientHeight,
    targetScrollHeight: ta.scrollHeight,
    targetClientHeight: ta.clientHeight,
  })
}

function _setSyncedScroll(targetName, target, scrollTop) {
  if (!target) return
  const nextTop = _mdClamp(scrollTop, 0, _mdMaxScroll(target))
  if (Math.abs(target.scrollTop - nextTop) < 1) return
  mdIgnoreScrollFrom.add(targetName)
  target.scrollTop = nextTop
  if (mdIgnoreScrollTimer) clearTimeout(mdIgnoreScrollTimer)
  mdIgnoreScrollTimer = setTimeout(() => {
    mdIgnoreScrollFrom.clear()
  }, 80)
}

function _syncMarkdownScroll(source) {
  const ta = mdTextareaRef.value
  const pv = mdPreviewRef.value
  if (!ta || !pv) return
  if (mdScrollRaf) cancelAnimationFrame(mdScrollRaf)
  mdScrollRaf = requestAnimationFrame(() => {
    if (source === 'editor') {
      _setSyncedScroll('preview', pv, _mdPreviewTopFromEditor())
    } else {
      _setSyncedScroll('editor', ta, _mdEditorTopFromPreview())
    }
  })
}

function _setMarkdownExampleScroll(targetName, target, scrollTop) {
  if (!target) return
  const maxScroll = _mdMaxScroll(target)
  const nextTop = _mdClamp(scrollTop, 0, maxScroll)
  if (Math.abs(target.scrollTop - nextTop) < 1) return
  markdownExampleIgnoreScrollFrom.add(targetName)
  target.scrollTop = nextTop
  if (markdownExampleIgnoreScrollTimer) clearTimeout(markdownExampleIgnoreScrollTimer)
  markdownExampleIgnoreScrollTimer = setTimeout(() => {
    markdownExampleIgnoreScrollFrom.clear()
  }, 80)
}

function _syncMarkdownExampleScroll(source) {
  const sourceEl = source === 'source' ? markdownExampleSourceRef.value : markdownExamplePreviewRef.value
  const targetEl = source === 'source' ? markdownExamplePreviewRef.value : markdownExampleSourceRef.value
  const targetName = source === 'source' ? 'preview' : 'source'
  if (!sourceEl || !targetEl) return
  if (markdownExampleScrollRaf) cancelAnimationFrame(markdownExampleScrollRaf)
  markdownExampleScrollRaf = requestAnimationFrame(() => {
    const scrollTop = getSyncedScrollTopByRatio({
      sourceScrollTop: sourceEl.scrollTop,
      sourceScrollHeight: sourceEl.scrollHeight,
      sourceClientHeight: sourceEl.clientHeight,
      targetScrollHeight: targetEl.scrollHeight,
      targetClientHeight: targetEl.clientHeight,
    })
    _setMarkdownExampleScroll(targetName, targetEl, scrollTop)
  })
}

const onMarkdownExampleSourceScroll = () => {
  if (markdownExampleIgnoreScrollFrom.has('source')) {
    markdownExampleIgnoreScrollFrom.delete('source')
    return
  }
  _syncMarkdownExampleScroll('source')
}

const onMarkdownExamplePreviewScroll = () => {
  if (markdownExampleIgnoreScrollFrom.has('preview')) {
    markdownExampleIgnoreScrollFrom.delete('preview')
    return
  }
  _syncMarkdownExampleScroll('preview')
}

const mdScrollToHeading = (id) => {
  const heading = mdToc.value.find((item) => item.id === id)
  const pv = mdPreviewRef.value
  const ta = mdTextareaRef.value
  if (!heading || !pv || !ta) return
  const previewTop = _mdHeadingTop(pv, heading)
  if (previewTop !== null) _setSyncedScroll('preview', pv, previewTop)
  _setSyncedScroll('editor', ta, getEditorScrollTopForHeading({ headingLine: heading.line, lineHeight: _mdLineHeight() }))
}

// ---- scroll sync ----
const onEditorScroll = () => {
  if (mdIgnoreScrollFrom.has('editor')) {
    mdIgnoreScrollFrom.delete('editor')
    return
  }
  _syncMarkdownScroll('editor')
}

const onPreviewScroll = () => {
  if (mdIgnoreScrollFrom.has('preview')) {
    mdIgnoreScrollFrom.delete('preview')
    return
  }
  _syncMarkdownScroll('preview')
}
</script>

<style scoped>
.page-header { margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.page-header h2 { margin: 0; font-size: 22px; }
.markdown-example-intro { margin: 0 0 12px; color: #909399; font-size: 13px; line-height: 1.6; }
.markdown-example-dialog :deep(.el-dialog__body) { overflow: hidden; }
.markdown-example-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
  height: calc(90vh - 125px);
  min-height: 420px;
}
.markdown-example-panel {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  overflow: hidden;
}
.markdown-example-panel-title {
  flex: none;
  padding: 10px 12px;
  color: #606266;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
  font-size: 13px;
  font-weight: 600;
}
.markdown-example-source {
  display: block;
  flex: 1;
  width: 100%;
  min-height: 0;
  padding: 12px;
  color: #303133;
  background: #fff;
  border: none;
  outline: none;
  resize: none;
  font-family: SFMono-Regular, Consolas, Monaco, monospace;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre;
  overflow: auto;
  box-sizing: border-box;
}
.markdown-example-preview {
  flex: 1;
  min-height: 0;
  padding: 12px 16px;
  color: #303133;
  background: #fff;
  font-size: 14px;
  line-height: 1.7;
  overflow: auto;
}
.markdown-example-preview :deep(h1) { font-size: 24px; margin: 16px 0 8px; }
.markdown-example-preview :deep(h2) { font-size: 20px; margin: 14px 0 6px; }
.markdown-example-preview :deep(h3) { font-size: 17px; margin: 12px 0 4px; }
.markdown-example-preview :deep(p) { margin: 6px 0; }
.markdown-example-preview :deep(code) { background: #f5f5f5; padding: 2px 6px; border-radius: 4px; font-size: 12px; }
.markdown-example-preview :deep(pre) { background: #f5f7fa; padding: 12px 16px; border-radius: 6px; overflow-x: auto; }
.markdown-example-preview :deep(blockquote) { border-left: 3px solid #1677ff; padding-left: 12px; margin: 8px 0; color: #666; }
.markdown-example-preview :deep(ul), .markdown-example-preview :deep(ol) { padding-left: 20px; }
.markdown-example-preview :deep(table) { border-collapse: collapse; width: 100%; margin: 8px 0; }
.markdown-example-preview :deep(th), .markdown-example-preview :deep(td) { border: 1px solid #e8e8e8; padding: 6px 10px; text-align: left; }
.markdown-example-preview :deep(th) { background: #fafafa; font-weight: 600; }
.panel-label { font-weight: 600; font-size: 14px; color: #595959; }
.panel-title { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.panel-title :deep(.el-button) { padding: 2px 4px; min-height: 24px; }
.split-editor { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 20px; }
.editor-panel { min-width: 0; }
.editor-panel :deep(.el-textarea__inner) {
  font-family: SFMono-Regular, Consolas, Monaco, monospace;
  font-size: 13px;
  line-height: 1.6;
}
.action-bar { margin: 14px 0; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; justify-content: center; }
.json-output { font-family: SFMono-Regular, Consolas, Monaco, monospace; font-size: 13px; }
.json-error { margin-bottom: 12px; white-space: pre-wrap; }
.json-stats { margin-top: 8px; font-size: 12px; color: #909399; text-align: right; }
.format-tabs :deep(.el-tabs__header) { display: none; }
.md-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; align-items: start; min-height: 0; }

/* 去掉卡片默认内边距，让编辑区和预览区贴边 */
.md-card :deep(.el-card__body) { padding: 0; }

/* ---- 编辑区 ---- */
.md-textarea {
  display: block;
  width: 100%;
  height: calc(100vh - 280px);
  min-height: 400px;
  padding: 12px 16px;
  font-family: SFMono-Regular, Consolas, monospace;
  font-size: 14px;
  line-height: 1.6;
  color: #303133;
  border: none;
  outline: none;
  resize: none;
  overflow: auto;
  white-space: pre;
  tab-size: 2;
  background: #fff;
  box-sizing: border-box;
}
.md-textarea::placeholder { color: #c0c4cc; }

/* 预览区：内边距和滚动 */
.md-preview-wrapper {
  display: flex; gap: 0;
  height: calc(100vh - 280px);
  min-height: 400px;
  min-width: 0;
  overflow: hidden;
}
.md-preview {
  flex: 1;
  padding: 12px 16px;
  font-size: 15px; line-height: 1.8; color: #303133;
  overflow: auto;
}
.md-toc {
  width: 150px; flex-shrink: 0;
  padding: 12px 8px 12px 16px;
  border-left: 1px solid #ebeef5;
  overflow-y: auto;
}
.md-toc-title { font-size: 13px; font-weight: 600; color: #909399; margin-bottom: 8px; }
.md-toc-item {
  display: block; font-size: 12px; line-height: 1.6; color: #606266;
  padding: 2px 0; cursor: pointer; text-decoration: none;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  transition: color .15s;
}
.md-toc-item:hover { color: #1677ff; }
.md-toc-level-1 { font-weight: 600; }
.md-toc-level-2 { padding-left: 8px; }
.md-toc-level-3 { padding-left: 16px; font-size: 11px; color: #909399; }
.md-preview :deep(h1) { font-size: 24px; margin: 16px 0 8px; }
.md-preview :deep(h2) { font-size: 20px; margin: 14px 0 6px; }
.md-preview :deep(h3) { font-size: 17px; margin: 12px 0 4px; }
.md-preview :deep(p) { margin: 6px 0; }
.md-preview :deep(code) { background: #f5f5f5; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
.md-preview :deep(pre) { background: #f5f7fa; padding: 12px 16px; border-radius: 8px; overflow-x: auto; }
.md-preview :deep(blockquote) { border-left: 3px solid #1677ff; padding-left: 12px; margin: 8px 0; color: #666; }
.md-preview :deep(ul), .md-preview :deep(ol) { padding-left: 20px; }
.md-preview :deep(li) { margin: 2px 0; }
.md-preview :deep(table) { border-collapse: collapse; width: 100%; margin: 8px 0; }
.md-preview :deep(th), .md-preview :deep(td) { border: 1px solid #e8e8e8; padding: 6px 12px; text-align: left; }
.md-preview :deep(th) { background: #fafafa; font-weight: 600; }
@media (max-width: 900px) {
  .split-editor,
  .md-layout,
  .markdown-example-layout { grid-template-columns: 1fr; }
  .markdown-example-dialog :deep(.el-dialog__body) { overflow: auto; }
  .markdown-example-layout { height: auto; }
  .markdown-example-panel { min-height: 360px; }
  .markdown-example-source,
  .markdown-example-preview { flex: none; height: 360px; }
}
@media (max-width: 600px) {
  .page-header { align-items: flex-start; flex-direction: column; }
}
</style>
