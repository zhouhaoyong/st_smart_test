<template>
  <div class="tool-page">
    <div class="page-header">
      <h2>用例工具</h2>
      <p class="page-desc">需求清单转 XMind，以及 XMind 转测试用例</p>
    </div>

    <el-tabs v-model="activeTab" class="xmind-tabs">

      <!-- ========== Tab 1: 需求转 XMind ========== -->
      <el-tab-pane label="需求转Xmind" name="generate">
        <!-- 使用说明 -->
        <el-alert type="info" :closable="false" style="margin-bottom: 16px;">
          <template #title>
            <strong>Excel 需求清单格式要求：</strong>
            必需列：所属模块、需求名称；可选列：需求描述、需求类型、优先级。生成 Xmind 后可在其中补充步骤和预期
          </template>
        </el-alert>

        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span><el-icon><Upload /></el-icon> 上传需求清单</span>
              <el-button size="default" @click="genDownloadSample">
                <el-icon><Download /></el-icon> 下载示例 Excel
              </el-button>
            </div>
          </template>

          <!-- 输入方式选择（预留扩展） -->
          <div style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 14px; color: #606266;">输入方式：</span>
            <el-radio-group v-model="gen.sourceType" size="small">
              <el-radio-button value="excel">Excel 文件</el-radio-button>
              <el-radio-button value="text" disabled>文本输入（即将支持）</el-radio-button>
              <el-radio-button value="markdown" disabled>Markdown（即将支持）</el-radio-button>
            </el-radio-group>
          </div>

          <!-- Excel 上传 -->
          <div v-if="gen.sourceType === 'excel'">
            <el-upload
              ref="genUploadRef"
              :auto-upload="false"
              :show-file-list="true"
              accept=".xlsx,.xls"
              :limit="1"
              :on-exceed="genOnExceed"
              :on-change="genOnFileChange"
              :on-remove="genOnFileRemove"
              drag
            >
              <el-icon :size="48" color="#1677ff"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                将 Excel 需求清单拖到此处，或 <em>点击选择文件</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">支持 .xlsx / .xls，最大 10MB。表头包含：所属模块、需求名称、需求描述（可选）、优先级（可选）</div>
              </template>
            </el-upload>

            <!-- XMind 根节点标题 -->
            <div style="margin-top: 12px; display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 14px; color: #606266;">根节点标题：</span>
              <el-input v-model="gen.rootTitle" placeholder="需求清单" style="width: 220px;" size="default" />
            </div>

            <div style="margin-top: 16px; display: flex; gap: 12px;">
              <el-button type="primary" :loading="gen.loading" :disabled="!gen.selectedFile" @click="genHandleGenerate">
                <el-icon><MagicStick /></el-icon> 生成 XMind
              </el-button>
              <el-button :disabled="!gen.selectedFile" @click="genHandleClear">清空</el-button>
            </div>
          </div>

          <!-- 未来扩展：文本/Markdown 输入 -->
          <div v-else style="padding: 40px 0; text-align: center; color: #909399;">
            此输入方式即将支持，请先使用 Excel 方式
          </div>
        </el-card>

        <!-- 生成结果提示 -->
        <el-card v-if="gen.resultMessage" style="margin-top: 16px;">
          <el-alert
            :title="gen.resultMessage"
            :type="gen.resultType"
            :closable="true"
            show-icon
            @close="gen.resultMessage = ''; gen.resultType = 'success'"
          />
          <div v-if="gen.warnings.length > 0" style="margin-top: 12px;">
            <div style="font-size: 14px; font-weight: 600; margin-bottom: 6px; color: #e6a23c;">
              解析警告（{{ gen.warnings.length }} 条）
            </div>
            <div v-for="(w, i) in gen.warnings" :key="i" style="font-size: 13px; color: #909399; padding: 2px 0;">
              {{ w }}
            </div>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- ========== Tab 2: XMind 转用例 ========== -->
      <el-tab-pane label="Xmind转用例" name="parse">
        <el-alert type="info" :closable="false" style="margin-bottom: 16px;">
          <template #title>
            <strong>XMind 文件结构要求：</strong>
            第1层 → 所属模块 &nbsp;|&nbsp;
            第2层 → 用例标题（可设置标签/标记/笔记）&nbsp;|&nbsp;
            第3层 → 步骤 &nbsp;|&nbsp;
            第4层 → 预期结果
          </template>
        </el-alert>

        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span><el-icon><Upload /></el-icon> 上传 XMind 文件</span>
              <el-button type="success" size="default" @click="parseDownloadTemplate">
                <el-icon><Download /></el-icon> 下载模板
              </el-button>
            </div>
          </template>

          <el-upload
            ref="parseUploadRef"
            :auto-upload="false"
            :show-file-list="true"
            accept=".xmind"
            :limit="1"
            :on-exceed="parseOnExceed"
            :on-change="parseOnFileChange"
            :on-remove="parseOnFileRemove"
            drag
          >
            <el-icon :size="48" color="#1677ff"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              将 XMind 文件拖到此处，或 <em>点击选择文件</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">仅支持 .xmind 文件，最大 10MB</div>
            </template>
          </el-upload>

          <div style="margin-top: 16px; display: flex; gap: 12px;">
            <el-button type="primary" :loading="parse.loading" :disabled="!parse.selectedFile" @click="parseHandleUpload">
              <el-icon><Search /></el-icon> 解析并预览
            </el-button>
            <el-button :disabled="!parse.selectedFile" @click="parseHandleClear">清空</el-button>
          </div>
        </el-card>

        <!-- 预览区 -->
        <el-card v-if="parse.rows.length > 0" style="margin-top: 16px;">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span><el-icon><List /></el-icon> 解析结果（共 {{ parse.rows.length }} 条）</span>
              <div style="display: flex; gap: 12px; align-items: center;">
                <span style="font-size: 14px; color: #666;">导出格式：</span>
                <el-radio-group v-model="parse.exportFormat" size="small">
                  <el-radio-button value="xlsx">
                    <el-icon><Document /></el-icon> Excel (.xlsx)
                  </el-radio-button>
                  <el-radio-button value="csv">
                    <el-icon><Tickets /></el-icon> CSV
                  </el-radio-button>
                </el-radio-group>
                <el-button type="primary" :loading="parse.exporting" @click="parseHandleExport">
                  <el-icon><Download /></el-icon> 下载
                </el-button>
              </div>
            </div>
          </template>

          <el-table :data="parse.rows" max-height="500" stripe border style="width: 100%">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="module" label="所属模块" min-width="120" />
            <el-table-column prop="title" label="用例标题" min-width="180" />
            <el-table-column prop="precondition" label="前置条件" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.precondition">{{ row.precondition }}</span>
                <span v-else style="color: #ccc;">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="case_type" label="用例类型" width="100" />
            <el-table-column prop="priority" label="优先级" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.priority" size="small" type="warning">{{ row.priority }}</el-tag>
                <span v-else style="color: #ccc;">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="step" label="步骤" min-width="250">
              <template #default="{ row }">
                <pre class="cell-pre">{{ row.step }}</pre>
              </template>
            </el-table-column>
            <el-table-column prop="expected" label="预期" min-width="250">
              <template #default="{ row }">
                <pre class="cell-pre">{{ row.expected }}</pre>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-empty
          v-if="!parse.loading && parse.rows.length === 0 && !parse.selectedFile"
          description="请先上传 XMind 文件"
          style="margin-top: 40px;"
        />
      </el-tab-pane>

    </el-tabs>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, UploadFilled, Search, Download, Document, Tickets, List, MagicStick } from '@element-plus/icons-vue'
import { uploadXmind } from '@/api/tools'

const activeTab = ref('generate')

// ====== Tab 1: 需求转 XMind ======
const gen = reactive({
  sourceType: 'excel',
  rootTitle: '',
  selectedFile: null,
  loading: false,
  resultMessage: '',
  resultType: 'success',
  warnings: [],
})

const genUploadRef = ref(null)

const genOnExceed = () => { ElMessage.warning('只能上传一个文件') }
const genOnFileChange = (file) => { gen.selectedFile = file.raw }
const genOnFileRemove = () => { gen.selectedFile = null }

const genHandleClear = () => {
  gen.selectedFile = null; gen.resultMessage = ''; gen.warnings = []
  genUploadRef.value?.clearFiles()
}

// 下载文件或处理错误。后端错误也返回 HTTP 200（UnifiedException）。
// 有效文件：zip/xmind/xlsx 必以 PK(0x50 0x4B) 开头。
async function _downloadOrError(response, filename) {
  const buf = await response.arrayBuffer()
  const bytes = new Uint8Array(buf)

  // 合法的 zip 系列文件（xmind/xlsx/docx 等都是 zip）→ 触发下载
  if (bytes.length >= 2 && bytes[0] === 0x50 && bytes[1] === 0x4B) {
    const blob = new Blob([buf])
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = filename
    document.body.appendChild(a); a.click(); document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
    return { downloaded: true }
  }

  // 不是 zip → 尝试解析错误信息
  const text = new TextDecoder().decode(bytes)
  // JSON 错误（后端 UnifiedException）
  try {
    const data = JSON.parse(text)
    if (data.code && data.code !== 200) {
      throw Object.assign(new Error(data.message || '请求失败'), { data: data.data })
    }
    return { json: data }
  } catch (e) {
    if (e.data !== undefined) throw e
  }
  // 非 JSON 也非 zip（如 nginx 纯文本错误）→ 直接报错
  throw new Error(text.slice(0, 200) || '未知错误')
}

const genHandleGenerate = async () => {
  if (!gen.selectedFile) return
  gen.loading = true; gen.resultMessage = ''; gen.warnings = []
  try {
    const token = localStorage.getItem('access_token')
    const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    // nginx 不支持中文文件名（Content-Disposition 头中的非 ASCII 字符会导致 500）
    const safeName = gen.selectedFile.name.replace(/[^\x00-\x7F]/g, '_') || 'file.xlsx'
    const safeFile = new File([gen.selectedFile], safeName, { type: gen.selectedFile.type })
    const formData = new FormData()
    formData.append('file', safeFile)
    formData.append('source_type', gen.sourceType)
    if (gen.rootTitle.trim()) formData.append('root_title', gen.rootTitle.trim())

    const response = await fetch(`${apiBase}/tools/xmind/generate`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData,
    })

    const baseName = gen.selectedFile.name.replace(/\.\w+$/, '')
    const result = await _downloadOrError(response, `${baseName}.xmind`)
    if (result.json) throw new Error(result.json.message || '生成失败')

    gen.resultType = 'success'
    gen.resultMessage = `XMind 文件已生成并开始下载（${baseName}.xmind）`
    ElMessage.success('生成成功，下载已开始')
  } catch (e) {
    gen.resultType = 'error'
    gen.resultMessage = e.message || '生成失败'
    gen.warnings = e.data?.warnings || []
  } finally {
    gen.loading = false
  }
}

const genDownloadSample = async () => {
  try {
    const token = localStorage.getItem('access_token')
    const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    const response = await fetch(`${apiBase}/tools/xmind/sample-excel`, {
      method: 'GET',
      headers: { 'Authorization': `Bearer ${token}` },
    })
    const result = await _downloadOrError(response, 'requirement_sample.xlsx')
    if (result.json) throw new Error(result.json.message || '下载失败')
    ElMessage.success('示例 Excel 下载已开始')
  } catch (e) {
    ElMessage.error(e.message || '示例 Excel 下载失败')
  }
}

// ====== Tab 2: XMind 转用例 ======
const parse = reactive({
  loading: false, exporting: false,
  selectedFile: null, rows: [], exportFormat: 'xlsx',
})

const parseUploadRef = ref(null)

const parseOnExceed = () => { ElMessage.warning('只能上传一个文件') }
const parseOnFileChange = (file) => { parse.selectedFile = file.raw }
const parseOnFileRemove = () => { parse.selectedFile = null }

const parseHandleClear = () => {
  parse.selectedFile = null; parse.rows = []
  parseUploadRef.value?.clearFiles()
}

const parseDownloadTemplate = async () => {
  try {
    const token = localStorage.getItem('access_token')
    const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    const response = await fetch(`${apiBase}/tools/xmind/template`, {
      method: 'GET',
      headers: { 'Authorization': `Bearer ${token}` },
    })
    const result = await _downloadOrError(response, 'xmind_template.xmind')
    if (result.json) throw new Error(result.json.message || '下载失败')
    ElMessage.success('模板下载已开始')
  } catch (e) {
    ElMessage.error(e.message || '模板下载失败')
  }
}

const parseHandleUpload = async () => {
  if (!parse.selectedFile) return
  parse.loading = true
  try {
    const res = await uploadXmind(parse.selectedFile)
    parse.rows = res.rows || []
    if (parse.rows.length === 0) {
      ElMessage.warning('未解析到数据，请检查 XMind 文件结构是否为4层')
    }
  } catch { parse.rows = [] }
  finally { parse.loading = false }
}

const parseHandleExport = async () => {
  if (parse.rows.length === 0) return
  parse.exporting = true
  try {
    const token = localStorage.getItem('access_token')
    const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    const response = await fetch(`${apiBase}/tools/xmind/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ rows: parse.rows, format: parse.exportFormat }),
    })
    const ext = parse.exportFormat === 'xlsx' ? 'xlsx' : 'csv'
    const result = await _downloadOrError(response, `testcases.${ext}`)
    if (result.json) throw new Error(result.json.message || '导出失败')
    ElMessage.success('下载成功')
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally { parse.exporting = false }
}
</script>

<style scoped>
.tool-page {}
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 22px; }
.page-header .page-desc { margin: 6px 0 0; font-size: 14px; color: #888; }
.cell-pre { margin: 0; padding: 0; font-family: inherit; font-size: 14px; white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto; }
.xmind-tabs :deep(.el-tabs__header) { margin-bottom: 4px; }
</style>
