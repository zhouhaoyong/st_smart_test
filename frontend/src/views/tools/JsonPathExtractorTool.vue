<template>
  <div class="jsonpath-extractor page">
    <section class="hero">
      <div class="hero-badge">JSONPath · API Response Inspector</div>
      <h1>接口响应 JSONPath 提取工具</h1>
      <p>
        面向接口联调、自动化测试与数据校验场景。将接口响应 JSON 粘贴到左侧输入区，系统会自动生成可交互的字段树；点击任意节点即可获得标准 JSONPath 表达式，例如
        <code>$.data.code</code>、<code>$.data.user.name</code>、<code>$.data.list[0].itemCode</code>。
      </p>
      <div class="hero-meta">
        <span>支持多层嵌套对象</span>
        <span>支持数组下标路径</span>
        <span>点击字段即时提取</span>
        <span>适合接口测试场景</span>
      </div>
    </section>

    <div class="layout">
      <section class="panel">
        <div class="panel-header">
          <div class="panel-title">
            <h2>接口响应输入区</h2>
            <p>请输入完整的接口响应 JSON 文本。建议直接粘贴后端返回值，系统会在服务端完成格式校验与结构解析。</p>
          </div>
          <div class="panel-tag">Input</div>
        </div>
        <div class="panel-body">
          <div class="toolbar">
            <button type="button" class="btn-primary" @click="parseJsonResponse">解析并生成字段树</button>
            <button type="button" class="btn-secondary" @click="formatEditorContent">格式化示例数据</button>
          </div>
          <textarea
            v-model="responseInput"
            placeholder='请输入接口响应 JSON，例如：
{
  "code": 200,
  "message": "success",
  "data": {
    "code": "OK",
    "user": {
      "name": "张三"
    }
  }
}'
          />
          <div v-if="errorMessage" class="error">{{ errorMessage }}</div>
          <div class="notice-grid">
            <div class="notice-card">
              <strong>字段提取规则</strong>
              <span>对象节点按 <code>$.a.b.c</code> 拼接，数组节点按 <code>$.list[0]</code> 拼接。</span>
            </div>
            <div class="notice-card">
              <strong>适用场景</strong>
              <span>接口自动化测试、断言字段提取、联调排查、接口文档核对。</span>
            </div>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div class="panel-title">
            <h2>JSONPath 提取结果</h2>
            <p>字段树由响应结构自动生成。点击任意字段节点后，右侧会展示标准 JSONPath 与字段值预览。</p>
          </div>
          <div class="panel-tag">Output</div>
        </div>
        <div class="panel-body">
          <div class="summary-grid">
            <div class="summary-card path">
              <span class="label">当前选中字段 JSONPath</span>
              <div class="value">{{ selectedPath }}</div>
            </div>
            <div class="summary-card">
              <span class="label">字段值预览</span>
              <div class="value">{{ selectedValue }}</div>
            </div>
          </div>
          <div class="tree-panel">
            <div class="tree-header">
              <strong>字段结构树</strong>
              <span>点击节点即可查看路径与字段值</span>
            </div>
            <div class="tree">
              <div v-if="parsing" class="placeholder">正在解析响应结构，请稍候...</div>
              <div v-else-if="!tree" class="placeholder">暂无解析结果，请先在左侧输入 JSON 并执行解析。</div>
              <ul v-else>
                <TreeNode :node="tree" @select="onNodeSelect" />
              </ul>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import request from '@/utils/request'
import TreeNode from './TreeNode.vue'

const responseInput = ref('')
const tree = ref(null)
const parsing = ref(false)
const selectedPath = ref('请先在下方字段树中选择目标节点')
const selectedValue = ref('暂无')
const errorMessage = ref('')

const defaultSample = {
  code: 200,
  message: 'success',
  traceId: 'TRACE-20260603-0001',
  data: {
    code: 'A1001',
    user: {
      id: 1,
      name: '张三',
      dept: '检验科',
    },
    list: [
      { itemCode: 'X1', value: 10 },
      { itemCode: 'X2', value: 20 },
    ],
  },
}

function formatValue(value) {
  if (value === null) return 'null'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

function onNodeSelect(node) {
  selectedPath.value = node.path
  selectedValue.value = formatValue(node.value)
}

async function parseJsonResponse() {
  errorMessage.value = ''
  parsing.value = true
  tree.value = null
  selectedPath.value = '请先在下方字段树中选择目标节点'
  selectedValue.value = '暂无'

  try {
    const result = await request.post('/tools/extract', { response: responseInput.value })
    tree.value = result.tree
  } catch (error) {
    errorMessage.value = error.data?.message || error.message || '请求失败'
  } finally {
    parsing.value = false
  }
}

function formatEditorContent() {
  try {
    const parsed = JSON.parse(responseInput.value)
    responseInput.value = JSON.stringify(parsed, null, 2)
    errorMessage.value = ''
  } catch {
    errorMessage.value = '当前输入内容不是合法 JSON，无法格式化。'
  }
}

onMounted(() => {
  responseInput.value = JSON.stringify(defaultSample, null, 2)
})
</script>

<style scoped>
.jsonpath-extractor {
  --bg: #0f172a;
  --panel: rgba(255, 255, 255, 0.92);
  --panel-soft: rgba(248, 250, 252, 0.92);
  --line: rgba(148, 163, 184, 0.28);
  --text: #0f172a;
  --subtext: #475569;
  --primary: #2563eb;
  --primary-dark: #1d4ed8;
  --success: #059669;
  --danger: #dc2626;
  --shadow: 0 20px 50px rgba(15, 23, 42, 0.18);

  min-height: 100vh;
  font-family: 'Microsoft YaHei', 'PingFang SC', Arial, sans-serif;
  color: var(--text);
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.3), transparent 30%),
    radial-gradient(circle at top right, rgba(14, 165, 233, 0.2), transparent 26%),
    linear-gradient(135deg, #e2e8f0 0%, #f8fafc 45%, #dbeafe 100%);
}

.jsonpath-extractor *,
.jsonpath-extractor *::before,
.jsonpath-extractor *::after {
  box-sizing: border-box;
}

.page {
  padding: 32px 24px 40px;
}

.hero {
  position: relative;
  overflow: hidden;
  margin-bottom: 24px;
  padding: 30px 32px;
  border: 1px solid rgba(255, 255, 255, 0.45);
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(37, 99, 235, 0.88));
  box-shadow: var(--shadow);
  color: #ffffff;
}

.hero::after {
  content: '';
  position: absolute;
  inset: auto -60px -80px auto;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  filter: blur(4px);
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  font-size: 12px;
  letter-spacing: 0.08em;
}

.hero h1 {
  margin: 16px 0 12px;
  font-size: 34px;
  line-height: 1.25;
  font-weight: 700;
}

.hero p {
  margin: 0;
  max-width: 820px;
  color: rgba(255, 255, 255, 0.82);
  font-size: 15px;
  line-height: 1.8;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 20px;
}

.hero-meta span {
  padding: 8px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.88);
  font-size: 13px;
}

.layout {
  display: grid;
  grid-template-columns: minmax(420px, 1.05fr) minmax(420px, 0.95fr);
  gap: 24px;
}

.panel {
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 24px;
  background: var(--panel);
  backdrop-filter: blur(10px);
  box-shadow: var(--shadow);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 24px 24px 0;
}

.panel-title h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
}

.panel-title p {
  margin: 8px 0 0;
  color: var(--subtext);
  font-size: 14px;
  line-height: 1.7;
}

.panel-tag {
  flex-shrink: 0;
  padding: 8px 12px;
  border-radius: 12px;
  background: rgba(37, 99, 235, 0.08);
  color: var(--primary);
  font-size: 12px;
  font-weight: 600;
}

.panel-body {
  padding: 20px 24px 24px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
}

button {
  border: none;
  border-radius: 14px;
  padding: 11px 18px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.2s ease, background 0.2s ease;
}

button:hover {
  transform: translateY(-1px);
}

.btn-primary {
  background: linear-gradient(135deg, var(--primary), #3b82f6);
  color: #fff;
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.28);
}

.btn-primary:hover {
  background: linear-gradient(135deg, var(--primary-dark), var(--primary));
}

.btn-secondary {
  background: #eef2ff;
  color: #3730a3;
}

textarea {
  width: 100%;
  min-height: 520px;
  resize: vertical;
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 18px;
  font-size: 14px;
  line-height: 1.8;
  font-family: Consolas, 'Courier New', monospace;
  color: #0f172a;
  background: rgba(255, 255, 255, 0.92);
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

textarea:focus {
  border-color: rgba(37, 99, 235, 0.45);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1);
}

.notice-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.notice-card {
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--panel-soft);
}

.notice-card strong {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
}

.notice-card span {
  display: block;
  color: var(--subtext);
  font-size: 13px;
  line-height: 1.7;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.summary-card {
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.94));
}

.summary-card .label {
  display: block;
  margin-bottom: 10px;
  color: var(--subtext);
  font-size: 13px;
  font-weight: 600;
}

.summary-card .value {
  color: var(--text);
  font-family: Consolas, 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.summary-card.path .value {
  color: var(--danger);
  font-weight: 700;
}

.tree-panel {
  border: 1px solid var(--line);
  border-radius: 20px;
  background: rgba(248, 250, 252, 0.88);
  overflow: hidden;
}

.tree-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.78);
}

.tree-header strong {
  font-size: 15px;
}

.tree-header span {
  color: var(--subtext);
  font-size: 12px;
}

.tree {
  max-height: 560px;
  overflow: auto;
  padding: 14px 16px 18px;
}

.tree > ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

.placeholder {
  padding: 28px 20px;
  text-align: center;
  color: var(--subtext);
  line-height: 1.8;
}

.error {
  margin-top: 12px;
  color: var(--danger);
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
}

@media (max-width: 1080px) {
  .layout {
    grid-template-columns: 1fr;
  }

  textarea {
    min-height: 380px;
  }
}

@media (max-width: 640px) {
  .page {
    padding: 18px 14px 24px;
  }

  .hero,
  .panel {
    border-radius: 18px;
  }

  .panel-header,
  .panel-body {
    padding-left: 16px;
    padding-right: 16px;
  }

  .summary-grid,
  .notice-grid {
    grid-template-columns: 1fr;
  }

  .hero h1 {
    font-size: 26px;
  }
}
</style>
