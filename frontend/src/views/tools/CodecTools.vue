<template>
  <div class="tool-page">
    <div class="page-header"><h2>{{ pageTitle }}</h2></div>
    <el-card>
      <el-tabs v-model="activeTab" class="codec-tabs">
        <el-tab-pane label="Base64" name="base64">
          <div class="split-editor">
            <section class="editor-panel">
              <div class="panel-title">
                <span class="panel-label">输入</span>
                <CopyButton :value="b64.input" label="复制" tooltip="复制输入内容" />
              </div>
              <el-input v-model="b64.input" type="textarea" :rows="12" placeholder="输入文本或 Base64 字符串" />
            </section>
            <div class="action-bar">
              <el-button type="primary" @click="b64Encode" :loading="b64.loading">
                编码 Encode
              </el-button>
              <el-button @click="b64Decode" :loading="b64.loading">
                解码 Decode
              </el-button>
              <el-button @click="b64Clear">清空</el-button>
            </div>
            <section class="editor-panel">
              <div class="panel-title">
                <span class="panel-label">输出</span>
                <CopyButton :value="b64.output" label="复制" tooltip="复制结果" />
              </div>
              <el-input v-model="b64.output" type="textarea" :rows="12" readonly placeholder="结果" />
            </section>
          </div>
          <div v-if="b64.error" class="error-block">
            <el-alert :title="b64.error" type="error" show-icon :closable="false" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="URL" name="url">
          <div class="split-editor">
            <section class="editor-panel">
              <div class="panel-title">
                <span class="panel-label">输入</span>
                <CopyButton :value="url.input" label="复制" tooltip="复制输入内容" />
              </div>
              <el-input v-model="url.input" type="textarea" :rows="12" placeholder="输入要编码或解码的文本" />
            </section>
            <div class="action-bar">
              <el-button type="primary" @click="urlProcess('encode')" :loading="url.loading">编码 Encode</el-button>
              <el-button @click="urlProcess('decode')" :loading="url.loading">解码 Decode</el-button>
              <el-button @click="urlClear">清空</el-button>
            </div>
            <section class="editor-panel">
              <div class="panel-title">
                <span class="panel-label">输出</span>
                <CopyButton :value="url.output" label="复制" tooltip="复制结果" />
              </div>
              <el-input v-model="url.output" type="textarea" :rows="12" readonly placeholder="结果" />
            </section>
          </div>
        </el-tab-pane>

        <el-tab-pane label="哈希" name="hash">
          <div class="split-editor">
            <section class="editor-panel">
              <div class="panel-title">
                <span class="panel-label">输入</span>
                <CopyButton :value="hash.input" label="复制" tooltip="复制输入内容" />
              </div>
              <el-input v-model="hash.input" type="textarea" :rows="12" placeholder="输入要计算哈希的文本" />
            </section>
            <div class="action-bar">
              <el-select v-model="hash.algorithm" style="width:130px" size="default">
                <el-option label="MD5" value="MD5" />
                <el-option label="SHA-1" value="SHA-1" />
                <el-option label="SHA-256" value="SHA-256" />
                <el-option label="SHA-384" value="SHA-384" />
                <el-option label="SHA-512" value="SHA-512" />
              </el-select>
              <el-button type="primary" @click="hashCompute" :loading="hash.loading">计算</el-button>
              <el-button @click="hashClear">清空</el-button>
            </div>
            <section class="editor-panel">
              <div class="panel-title">
                <span class="panel-label">输出</span>
                <CopyButton :value="hash.output" label="复制" tooltip="复制结果" />
              </div>
              <el-input v-model="hash.output" type="textarea" :rows="12" readonly placeholder="哈希值" class="hash-output" />
            </section>
          </div>
          <div v-if="hash.error" class="error-block">
            <el-alert :title="hash.error" type="error" show-icon :closable="false" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import CopyButton from '@/components/CopyButton.vue'

const activeTab = ref('base64')
const route = useRoute()
const pageTitle = computed(() => route.meta.title || '编解码工具')

watch(
  () => route.meta.toolTab,
  (tab) => {
    activeTab.value = tab || 'base64'
  },
  { immediate: true },
)

const b64 = reactive({ input: '', output: '', error: '', loading: false })

const bytesToBinary = (bytes) => {
  const chunkSize = 0x8000
  let binary = ''
  for (let start = 0; start < bytes.length; start += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(start, start + chunkSize))
  }
  return binary
}

const b64Encode = () => {
  if (!b64.input.trim()) { ElMessage.warning('请输入文本'); return }
  b64.loading = true
  setTimeout(() => {
    try {
      const bytes = new TextEncoder().encode(b64.input)
      b64.output = btoa(bytesToBinary(bytes))
      b64.error = ''
      ElMessage.success('编码成功')
    } catch (e) {
      b64.error = e.message
      b64.output = ''
    }
    b64.loading = false
  }, 30)
}

const b64Decode = () => {
  if (!b64.input.trim()) { ElMessage.warning('请输入 Base64'); return }
  b64.loading = true
  setTimeout(() => {
    try {
      const binary = atob(b64.input.trim())
      const bytes = Uint8Array.from(binary, c => c.charCodeAt(0))
      b64.output = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
      b64.error = ''
      ElMessage.success('解码成功')
    } catch {
      try {
        b64.output = atob(b64.input.trim())
        b64.error = ''
        ElMessage.success('解码成功（Latin-1）')
      } catch {
        b64.error = '解码失败：不是有效的 Base64 字符串'
        b64.output = ''
      }
    }
    b64.loading = false
  }, 30)
}

const b64Clear = () => { b64.input = ''; b64.output = ''; b64.error = '' }

const url = reactive({ input: '', output: '', loading: false })

const urlProcess = async (action) => {
  if (!url.input.trim()) { ElMessage.warning('请输入文本'); return }
  url.loading = true
  try {
    const res = await request({ url: '/tools/url-codec', method: 'post', data: { text: url.input, action } })
    url.output = res.result || ''
  } catch {} finally {
    url.loading = false
  }
}

const urlClear = () => { url.input = ''; url.output = '' }

const hash = reactive({ input: '', output: '', error: '', loading: false, algorithm: 'SHA-256' })

const md5Add = (x, y) => {
  const lsw = (x & 0xffff) + (y & 0xffff)
  const msw = (x >> 16) + (y >> 16) + (lsw >> 16)
  return (msw << 16) | (lsw & 0xffff)
}

const md5Rotate = (num, count) => (num << count) | (num >>> (32 - count))
const md5Cmn = (q, a, b, x, s, t) => md5Add(md5Rotate(md5Add(md5Add(a, q), md5Add(x, t)), s), b)
const md5Ff = (a, b, c, d, x, s, t) => md5Cmn((b & c) | ((~b) & d), a, b, x, s, t)
const md5Gg = (a, b, c, d, x, s, t) => md5Cmn((b & d) | (c & (~d)), a, b, x, s, t)
const md5Hh = (a, b, c, d, x, s, t) => md5Cmn(b ^ c ^ d, a, b, x, s, t)
const md5Ii = (a, b, c, d, x, s, t) => md5Cmn(c ^ (b | (~d)), a, b, x, s, t)

const md5BytesToWords = (bytes) => {
  const words = []
  for (let i = 0; i < bytes.length; i += 1) {
    words[i >> 2] = (words[i >> 2] || 0) | (bytes[i] << ((i % 4) * 8))
  }
  words[bytes.length >> 2] = (words[bytes.length >> 2] || 0) | (0x80 << ((bytes.length % 4) * 8))
  words[((((bytes.length + 8) >> 6) + 1) * 16) - 2] = bytes.length * 8
  return words
}

const md5WordToHex = (word) => {
  let hex = ''
  for (let i = 0; i < 4; i += 1) {
    hex += ((word >> (i * 8)) & 0xff).toString(16).padStart(2, '0')
  }
  return hex
}

const md5 = (text) => {
  const x = md5BytesToWords(new TextEncoder().encode(text))
  let a = 0x67452301
  let b = 0xefcdab89
  let c = 0x98badcfe
  let d = 0x10325476

  for (let i = 0; i < x.length; i += 16) {
    const olda = a
    const oldb = b
    const oldc = c
    const oldd = d

    a = md5Ff(a, b, c, d, x[i], 7, 0xd76aa478)
    d = md5Ff(d, a, b, c, x[i + 1], 12, 0xe8c7b756)
    c = md5Ff(c, d, a, b, x[i + 2], 17, 0x242070db)
    b = md5Ff(b, c, d, a, x[i + 3], 22, 0xc1bdceee)
    a = md5Ff(a, b, c, d, x[i + 4], 7, 0xf57c0faf)
    d = md5Ff(d, a, b, c, x[i + 5], 12, 0x4787c62a)
    c = md5Ff(c, d, a, b, x[i + 6], 17, 0xa8304613)
    b = md5Ff(b, c, d, a, x[i + 7], 22, 0xfd469501)
    a = md5Ff(a, b, c, d, x[i + 8], 7, 0x698098d8)
    d = md5Ff(d, a, b, c, x[i + 9], 12, 0x8b44f7af)
    c = md5Ff(c, d, a, b, x[i + 10], 17, 0xffff5bb1)
    b = md5Ff(b, c, d, a, x[i + 11], 22, 0x895cd7be)
    a = md5Ff(a, b, c, d, x[i + 12], 7, 0x6b901122)
    d = md5Ff(d, a, b, c, x[i + 13], 12, 0xfd987193)
    c = md5Ff(c, d, a, b, x[i + 14], 17, 0xa679438e)
    b = md5Ff(b, c, d, a, x[i + 15], 22, 0x49b40821)

    a = md5Gg(a, b, c, d, x[i + 1], 5, 0xf61e2562)
    d = md5Gg(d, a, b, c, x[i + 6], 9, 0xc040b340)
    c = md5Gg(c, d, a, b, x[i + 11], 14, 0x265e5a51)
    b = md5Gg(b, c, d, a, x[i], 20, 0xe9b6c7aa)
    a = md5Gg(a, b, c, d, x[i + 5], 5, 0xd62f105d)
    d = md5Gg(d, a, b, c, x[i + 10], 9, 0x02441453)
    c = md5Gg(c, d, a, b, x[i + 15], 14, 0xd8a1e681)
    b = md5Gg(b, c, d, a, x[i + 4], 20, 0xe7d3fbc8)
    a = md5Gg(a, b, c, d, x[i + 9], 5, 0x21e1cde6)
    d = md5Gg(d, a, b, c, x[i + 14], 9, 0xc33707d6)
    c = md5Gg(c, d, a, b, x[i + 3], 14, 0xf4d50d87)
    b = md5Gg(b, c, d, a, x[i + 8], 20, 0x455a14ed)
    a = md5Gg(a, b, c, d, x[i + 13], 5, 0xa9e3e905)
    d = md5Gg(d, a, b, c, x[i + 2], 9, 0xfcefa3f8)
    c = md5Gg(c, d, a, b, x[i + 7], 14, 0x676f02d9)
    b = md5Gg(b, c, d, a, x[i + 12], 20, 0x8d2a4c8a)

    a = md5Hh(a, b, c, d, x[i + 5], 4, 0xfffa3942)
    d = md5Hh(d, a, b, c, x[i + 8], 11, 0x8771f681)
    c = md5Hh(c, d, a, b, x[i + 11], 16, 0x6d9d6122)
    b = md5Hh(b, c, d, a, x[i + 14], 23, 0xfde5380c)
    a = md5Hh(a, b, c, d, x[i + 1], 4, 0xa4beea44)
    d = md5Hh(d, a, b, c, x[i + 4], 11, 0x4bdecfa9)
    c = md5Hh(c, d, a, b, x[i + 7], 16, 0xf6bb4b60)
    b = md5Hh(b, c, d, a, x[i + 10], 23, 0xbebfbc70)
    a = md5Hh(a, b, c, d, x[i + 13], 4, 0x289b7ec6)
    d = md5Hh(d, a, b, c, x[i], 11, 0xeaa127fa)
    c = md5Hh(c, d, a, b, x[i + 3], 16, 0xd4ef3085)
    b = md5Hh(b, c, d, a, x[i + 6], 23, 0x04881d05)
    a = md5Hh(a, b, c, d, x[i + 9], 4, 0xd9d4d039)
    d = md5Hh(d, a, b, c, x[i + 12], 11, 0xe6db99e5)
    c = md5Hh(c, d, a, b, x[i + 15], 16, 0x1fa27cf8)
    b = md5Hh(b, c, d, a, x[i + 2], 23, 0xc4ac5665)

    a = md5Ii(a, b, c, d, x[i], 6, 0xf4292244)
    d = md5Ii(d, a, b, c, x[i + 7], 10, 0x432aff97)
    c = md5Ii(c, d, a, b, x[i + 14], 15, 0xab9423a7)
    b = md5Ii(b, c, d, a, x[i + 5], 21, 0xfc93a039)
    a = md5Ii(a, b, c, d, x[i + 12], 6, 0x655b59c3)
    d = md5Ii(d, a, b, c, x[i + 3], 10, 0x8f0ccc92)
    c = md5Ii(c, d, a, b, x[i + 10], 15, 0xffeff47d)
    b = md5Ii(b, c, d, a, x[i + 1], 21, 0x85845dd1)
    a = md5Ii(a, b, c, d, x[i + 8], 6, 0x6fa87e4f)
    d = md5Ii(d, a, b, c, x[i + 15], 10, 0xfe2ce6e0)
    c = md5Ii(c, d, a, b, x[i + 6], 15, 0xa3014314)
    b = md5Ii(b, c, d, a, x[i + 13], 21, 0x4e0811a1)
    a = md5Ii(a, b, c, d, x[i + 4], 6, 0xf7537e82)
    d = md5Ii(d, a, b, c, x[i + 11], 10, 0xbd3af235)
    c = md5Ii(c, d, a, b, x[i + 2], 15, 0x2ad7d2bb)
    b = md5Ii(b, c, d, a, x[i + 9], 21, 0xeb86d391)

    a = md5Add(a, olda)
    b = md5Add(b, oldb)
    c = md5Add(c, oldc)
    d = md5Add(d, oldd)
  }

  return [a, b, c, d].map(md5WordToHex).join('')
}

const hashCompute = async () => {
  if (!hash.input) { ElMessage.warning('请输入文本'); return }
  hash.loading = true
  try {
    if (hash.algorithm === 'MD5') {
      hash.output = md5(hash.input)
    } else {
      const enc = new TextEncoder().encode(hash.input)
      const buf = await crypto.subtle.digest(hash.algorithm, enc)
      hash.output = Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('')
    }
    hash.error = ''
    ElMessage.success(`${hash.algorithm} 计算完成`)
  } catch (e) {
    hash.error = e.message
    hash.output = ''
  }
  hash.loading = false
}

const hashClear = () => { hash.input = ''; hash.output = ''; hash.error = '' }
</script>

<style scoped>
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 22px; }
.panel-label { font-weight: 600; font-size: 14px; color: #595959; }
.panel-title { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.panel-title :deep(.el-button) { padding: 2px 4px; min-height: 24px; }
.split-editor {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 128px minmax(0, 1fr);
  gap: 18px;
  align-items: stretch;
}
.editor-panel { min-width: 0; }
.editor-panel :deep(.el-textarea__inner) {
  font-family: SFMono-Regular, Consolas, Monaco, monospace;
  font-size: 13px;
  line-height: 1.6;
}
.action-bar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  justify-content: center;
  padding-top: 26px;
}
.action-bar :deep(.el-button) {
  width: 120px;
  justify-content: center;
  margin-left: 0 !important;
}
.action-bar :deep(.el-select) { width: 120px !important; }
.error-block { margin-bottom: 12px; }
.hash-output { font-family: SFMono-Regular, Consolas, monospace; font-size: 14px; }
.codec-tabs :deep(.el-tabs__header) { display: none; }
@media (max-width: 900px) {
  .split-editor { grid-template-columns: 1fr; }
  .action-bar { padding-top: 0; }
}
</style>
