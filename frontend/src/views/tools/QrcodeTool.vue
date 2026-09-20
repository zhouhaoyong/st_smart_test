<template>
  <div class="tool-page">
    <div class="page-header"><h2>二维码工具</h2></div>
    <el-tabs v-model="tab" type="border-card">
      <!-- === 生成 === -->
      <el-tab-pane label="生成" name="gen">
        <div class="panel-title">
          <span class="panel-label">输入内容</span>
          <CopyButton :value="input" label="复制" tooltip="复制输入内容" />
        </div>
        <el-input v-model="input" type="textarea" :rows="4" placeholder="输入网址或文本" />
        <div style="margin:12px 0;display:flex;gap:10px;flex-wrap:wrap;align-items:center">
          <span style="font-size:13px;color:#666">尺寸:</span>
          <el-slider v-model="size" :min="128" :max="512" :step="16" style="width:200px" />
          <span style="font-size:13px;color:#999">{{ size }}px</span>
          <el-button type="primary" @click="generate" :loading="loading">生成</el-button>
          <el-button @click="download" :disabled="!qrDataUrl">
            <el-icon :size="16"><Download /></el-icon> 下载
          </el-button>
          <el-button @click="clearGen">
            <el-icon :size="16"><Delete /></el-icon> 清空
          </el-button>
        </div>
        <div class="qr-preview" v-if="qrDataUrl">
          <img :src="qrDataUrl" :width="size" :height="size" alt="QR Code" />
          <div class="qr-tip">扫描二维码查看内容</div>
        </div>
        <div v-else class="qr-placeholder">输入内容后点击生成</div>
      </el-tab-pane>

      <!-- === 解析 === -->
      <el-tab-pane label="解析" name="decode">
        <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:16px">
          <el-upload :auto-upload="false" :show-file-list="false" accept="image/*" @change="onFileChange">
            <el-button type="primary">选择图片</el-button>
          </el-upload>
          <span style="font-size:13px;color:#999">或直接粘贴图片</span>
        </div>
        <div
          class="qr-decode-zone"
          @paste="onPaste"
          tabindex="0"
        >
          <canvas ref="canvasRef" style="display:none" />
          <div v-if="decodeResult !== null" class="decode-result">
            <div class="panel-title">
              <span class="panel-label">解析结果</span>
              <CopyButton :value="decodeResult" label="复制" tooltip="复制解析结果" />
            </div>
            <el-input v-model="decodeResult" type="textarea" :rows="3" readonly />
            <div style="margin-top:10px;display:flex;gap:10px">
              <el-button v-if="isUrl(decodeResult)" size="small" type="success" @click="openUrl(decodeResult)">
                <el-icon :size="16"><Link /></el-icon> 打开链接
              </el-button>
            </div>
          </div>
          <div v-else-if="decodeError" class="decode-error">
            <el-alert :title="decodeError" type="warning" show-icon :closable="false" />
          </div>
          <div v-else class="qr-placeholder">
            <p>在此区域粘贴图片（Ctrl+V）</p>
            <p style="font-size:12px;color:#c0c4cc">或点击上方按钮选择文件</p>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Delete, Link } from '@element-plus/icons-vue'
import QRCode from 'qrcode'
import jsQR from 'jsqr'
import CopyButton from '@/components/CopyButton.vue'

const tab = ref('gen')

// —— 生成 ——
const loading = ref(false)
const input = ref('')
const qrDataUrl = ref('')
const size = ref(256)

const generate = async () => {
  if (!input.value.trim()) { ElMessage.warning('请输入内容'); return }
  loading.value = true
  try {
    qrDataUrl.value = await QRCode.toDataURL(input.value, {
      width: size.value, margin: 2,
      color: { dark: '#000000', light: '#ffffff' },
    })
    ElMessage.success('生成成功')
  } catch (e) {
    ElMessage.error('生成失败: ' + e.message)
  }
  loading.value = false
}

const download = () => {
  const a = document.createElement('a')
  a.href = qrDataUrl.value; a.download = 'qrcode.png'; a.click()
  ElMessage.success('下载中')
}

const clearGen = () => { input.value = ''; qrDataUrl.value = '' }

// —— 解析 ——
const canvasRef = ref(null)
const decodeResult = ref(null)
const decodeError = ref('')

const decodeFromImage = (img) => {
  const canvas = canvasRef.value
  if (!canvas) return
  try {
    const maxW = 800
    let w = img.naturalWidth || img.width
    let h = img.naturalHeight || img.height
    if (w > maxW) { h = Math.round(h * maxW / w); w = maxW }
    canvas.width = w; canvas.height = h
    const ctx = canvas.getContext('2d')
    ctx.drawImage(img, 0, 0, w, h)
    const imageData = ctx.getImageData(0, 0, w, h)
    const code = jsQR(imageData.data, w, h)
    if (code) {
      decodeResult.value = code.data
      decodeError.value = ''
      ElMessage.success('解析成功')
      return
    }
    decodeResult.value = null
    decodeError.value = '未识别到二维码，请确保图片清晰且包含二维码'
  } catch {
    decodeResult.value = null
    decodeError.value = '图片解析失败，请更换图片后重试'
  }
}

const decodeBlob = (blob) => {
  if (!blob) return
  decodeError.value = ''
  decodeResult.value = null
  const img = new Image()
  const objectUrl = URL.createObjectURL(blob)
  const release = () => URL.revokeObjectURL(objectUrl)
  img.onload = () => {
    try { decodeFromImage(img) } finally { release() }
  }
  img.onerror = () => {
    release()
    decodeError.value = '图片读取失败，请更换图片后重试'
  }
  img.src = objectUrl
}

const onFileChange = (file) => decodeBlob(file.raw)

const onPaste = (e) => {
  const items = e.clipboardData?.items
  if (!items) return
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      decodeBlob(item.getAsFile())
      return
    }
  }
}

const isUrl = (s) => /^https?:\/\//i.test(s)
const openUrl = (url) => window.open(url, '_blank')
</script>

<style scoped>
.tool-page { }
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 22px; }
.panel-label { font-weight: 600; font-size: 14px; color: #595959; }
.panel-title { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin: 12px 0 8px; }
.panel-title :deep(.el-button) { padding: 2px 4px; min-height: 24px; }
.qr-preview { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 20px 0; }
.qr-tip { font-size: 13px; color: #999; }
.qr-placeholder { text-align: center; padding: 40px 0; color: #c0c4cc; font-size: 15px; }
.qr-decode-zone {
  border: 2px dashed #e0e0e0; border-radius: 10px; padding: 20px;
  min-height: 120px; display: flex; align-items: center; justify-content: center;
  outline: none; transition: border-color .2s;
}
.qr-decode-zone:focus { border-color: #1677ff; }
.decode-result { width: 100%; }
.decode-error { width: 100%; }
</style>
