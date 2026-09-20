// 统一的 Markdown 渲染工具：marked 解析 + DOMPurify 消毒后再交给 v-html。
// 所有需要 v-html 渲染 Markdown 的地方都应改用此函数，避免各处直接 marked.parse
// 造成的 XSS 风险（用户 / AI 产出的内容都视为不可信）。
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// 渲染并消毒 Markdown。始终返回安全的 HTML 字符串，解析异常时降级为空。
export function renderMarkdown(content) {
  let html = ''
  try {
    html = marked.parse(content || '', { breaks: true, gfm: true }) || ''
  } catch {
    return ''
  }
  return DOMPurify.sanitize(html)
}

export default renderMarkdown
