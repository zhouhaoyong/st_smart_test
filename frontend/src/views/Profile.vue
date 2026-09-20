<template>
  <div class="profile-container">
    <div class="admin-page-title">
      <h2>个人中心</h2>
    </div>
    <el-card>
      <el-tabs v-model="activeTab">
        <!-- 基本信息 -->
        <el-tab-pane label="基本信息" name="info">
          <div class="basic-info-role">
            <el-tag :type="roleTagType" effect="light">{{ roleLabel }}</el-tag>
          </div>
          <el-form :model="profileForm" label-width="100px" style="max-width: 500px">
            <el-form-item label="头像">
              <div class="avatar-section">
                <el-upload
                  :http-request="onFileSelect"
                  :show-file-list="false"
                  accept="image/*"
                  class="avatar-upload-wrap"
                >
                  <div class="avatar-preview">
                    <img v-if="profileForm.avatar" :src="profileForm.avatar" class="avatar-img-round" />
                    <div v-else class="avatar-letter" :style="{ background: avatarBgColor, color: '#fff' }">
                      {{ avatarLetter }}
                    </div>
                    <div class="avatar-overlay">
                      <el-icon :size="22"><Camera /></el-icon>
                      <span>更换头像</span>
                    </div>
                  </div>
                </el-upload>
              </div>
            </el-form-item>
            <el-form-item label="手机号">
              <el-input v-model="profileForm.phone" disabled />
              <span class="form-hint">手机号作为登录账号，不可修改</span>
            </el-form-item>
            <el-form-item label="真实姓名">
              <el-input v-model="profileForm.real_name" placeholder="请输入真实姓名" />
            </el-form-item>
            <el-form-item label="昵称">
              <el-input v-model="profileForm.nick_name" placeholder="请输入昵称" />
            </el-form-item>
            <el-form-item label="性别">
              <el-select v-model="profileForm.gender">
                <el-option :value="1" label="男" />
                <el-option :value="2" label="女" />
                <el-option :value="3" label="其他" />
              </el-select>
            </el-form-item>
            <el-form-item label="部门">
              <el-select v-model="profileForm.department">
                <el-option :value="1" label="测试部门" />
                <el-option :value="2" label="开发部门" />
                <el-option :value="4" label="产品部门" />
                <el-option :value="3" label="运维部门" />
                <el-option :value="5" label="其他部门" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleUpdateProfile" :loading="saving">保存修改</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 安全设置 -->
        <el-tab-pane label="修改密码" name="password">
          <el-form :model="pwdForm" :rules="pwdRules" ref="pwdFormRef" label-width="120px" style="max-width: 450px">
            <el-form-item label="原密码" prop="old_password">
              <el-input v-model="pwdForm.old_password" type="password" show-password />
            </el-form-item>
            <el-form-item label="新密码" prop="new_password">
              <el-input v-model="pwdForm.new_password" type="password" show-password />
            </el-form-item>
            <el-form-item label="确认密码" prop="confirm_password">
              <el-input v-model="pwdForm.confirm_password" type="password" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleChangePassword" :loading="changingPwd">修改密码</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

      </el-tabs>
    </el-card>

    <!-- 头像裁剪弹窗 -->
    <el-dialog v-model="showCrop" title="编辑头像" width="480px" :close-on-click-modal="false" @closed="cropImage=null">
      <div v-if="cropImage" class="crop-area">
        <div class="crop-canvas-wrap" ref="cropWrap">
          <canvas ref="cropCanvas" @mousedown="onCropStart" @mousemove="onCropMove" @mouseup="onCropEnd" @mouseleave="onCropEnd" />
        </div>
        <div class="crop-controls">
          <span class="crop-label">缩放</span>
          <el-slider v-model="cropScale" :min="1" :max="3" :step="0.01" @input="drawCrop" />
          <span class="crop-label" style="margin-left:12px">{{ Math.round(cropScale * 100) }}%</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="showCrop = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="confirmCrop">确认裁剪</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UserFilled, Camera } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { formatBeijingMinute } from '@/utils/beijingTime'
import { getProfile, updateProfile, changePassword } from '@/api/user'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const activeTab = ref('info')
const saving = ref(false)

const profileForm = reactive({
  phone: '', real_name: '', nick_name: '', gender: 3, department: 1, avatar: '', role: 'user'
})

const roleLabels = { super_admin: '超级管理员', manager: '管理员', user: '普通用户' }
const roleLabel = computed(() => roleLabels[profileForm.role] || '普通用户')
const roleTagType = computed(() => ({ super_admin: 'primary', manager: 'warning', user: 'success' }[profileForm.role] || 'success'))

// 用户头像：根据真实姓名首字母生成
const avatarLetter = computed(() => {
  const name = profileForm.real_name
  return name ? name.charAt(0).toUpperCase() : '用'
})

// 头像背景色：根据用户ID生成固定颜色（与其他地方保持一致）
const avatarBgColors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#f5222d', '#faad14']
const avatarBgColor = computed(() => {
  const userId = userStore.userInfo?.id || 0
  return avatarBgColors[userId % avatarBgColors.length]
})

const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })
const pwdFormRef = ref(null)
const changingPwd = ref(false)
const pwdRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { 
      validator: (_, value, callback) => {
        if (!value) {
          callback(new Error('请输入新密码'))
        } else if (value.length < 6) {
          callback(new Error('密码长度至少6位'))
        } else if (!/[a-z]/.test(value)) {
          callback(new Error('密码必须包含小写字母'))
        } else if (!/[A-Z]/.test(value)) {
          callback(new Error('密码必须包含大写字母'))
        } else {
          callback()
        }
      }, 
      trigger: 'blur' 
    }
  ],
  confirm_password: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: (_, v, cb) => v === pwdForm.new_password ? cb() : cb(new Error('两次输入不一致')), trigger: 'blur' },
  ],
}

const formatDate = (d) => d ? formatBeijingMinute(d) || '-' : '-'

const loadProfile = async () => {
  try {
    const data = await getProfile()
    Object.assign(profileForm, {
      phone: data.phone, real_name: data.real_name, nick_name: data.nick_name || '',
      gender: data.gender, department: data.department, avatar: data.avatar || '', role: data.role || 'user',
    })
  } catch { /* ignore */ }
}

const handleUpdateProfile = async () => {
  // 验证真实姓名格式
  if (!profileForm.real_name || !/^[\u4e00-\u9fa5]{2,20}$/.test(profileForm.real_name)) {
    ElMessage.error('真实姓名必须是2-20个中文字符')
    return
  }
  if (profileForm.nick_name && profileForm.nick_name.length > 50) {
    ElMessage.error('昵称不能超过50个字符')
    return
  }
  saving.value = true
  try {
    await updateProfile({
      real_name: profileForm.real_name,
      nick_name: profileForm.nick_name || null,
      gender: profileForm.gender,
      department: profileForm.department,
    })
    // 后端已返回成功消息，拦截器会处理
    await userStore.getUserInfo()
  } catch { /* 错误已在拦截器提示 */ }
  finally { saving.value = false }
}

const handleChangePassword = async () => {
  if (!pwdFormRef.value) return
  await pwdFormRef.value.validate(async (valid) => {
    if (!valid) return
    changingPwd.value = true
    try {
      await changePassword({
        old_password: pwdForm.old_password,
        new_password: pwdForm.new_password,
        confirm_password: pwdForm.confirm_password,
      })
      // 后端已返回成功消息，拦截器会自动显示
      Object.assign(pwdForm, { old_password: '', new_password: '', confirm_password: '' })
    } finally { changingPwd.value = false }
  })
}

// --- 头像裁剪 ---
const showCrop = ref(false)
const uploading = ref(false)
const cropImage = ref(null)
const cropCanvas = ref(null)
const cropWrap = ref(null)
const cropScale = ref(1)
let cropOffsetX = 0, cropOffsetY = 0, dragging = false, dragX = 0, dragY = 0
let cropImgEl = null  // 预加载的图片对象，避免重复创建
let rafId = 0
const CROP_SIZE = 280
const OUTPUT_SIZE = 200

function getCropDrawRect(canvasSize) {
  const baseScale = Math.max(CROP_SIZE / cropImgEl.width, CROP_SIZE / cropImgEl.height)
  const displayScale = baseScale * cropScale.value
  const drawWidth = cropImgEl.width * displayScale
  const drawHeight = cropImgEl.height * displayScale
  return {
    x: canvasSize / 2 - drawWidth / 2 + cropOffsetX,
    y: canvasSize / 2 - drawHeight / 2 + cropOffsetY,
    width: drawWidth,
    height: drawHeight,
  }
}

async function onFileSelect({ file }) {
  if (!file.type.startsWith('image/')) { ElMessage.error('仅支持图片文件'); return }
  if (file.size > 5 * 1024 * 1024) { ElMessage.error('图片大小不能超过 5MB'); return }
  const reader = new FileReader()
  reader.onload = async (e) => {
    cropImage.value = e.target.result
    // 预加载图片对象
    cropImgEl = new Image()
    await new Promise(r => { cropImgEl.onload = r; cropImgEl.src = e.target.result })
    cropScale.value = 1
    cropOffsetX = 0; cropOffsetY = 0
    showCrop.value = true
    await nextTick()
    drawCrop()
  }
  reader.readAsDataURL(file)
}

function drawCrop() {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(() => {
    const canvas = cropCanvas.value
    if (!canvas || !cropImgEl) return
    const wrap = cropWrap.value
    const size = Math.min(wrap.clientWidth, 400)
    canvas.width = size; canvas.height = size
    const ctx = canvas.getContext('2d')

    ctx.fillStyle = '#333'; ctx.fillRect(0, 0, size, size)

    const cx = size / 2
    const cy = size / 2
    const radius = CROP_SIZE / 2
    const rect = getCropDrawRect(size)
    ctx.drawImage(cropImgEl, rect.x, rect.y, rect.width, rect.height)

    // 蒙层
    ctx.fillStyle = 'rgba(0,0,0,0.5)'
    ctx.beginPath()
    ctx.rect(0, 0, size, size)
    ctx.arc(cx, cy, radius, 0, Math.PI * 2, true)
    ctx.fill('evenodd')

    ctx.strokeStyle = '#fff'; ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(cx, cy, radius, 0, Math.PI * 2)
    ctx.stroke()
  })
}

function onCropStart(e) {
  dragging = true; dragX = e.offsetX; dragY = e.offsetY
}
function onCropMove(e) {
  if (!dragging) return
  cropOffsetX += e.offsetX - dragX
  cropOffsetY += e.offsetY - dragY
  dragX = e.offsetX; dragY = e.offsetY
  drawCrop()
}
function onCropEnd() { dragging = false }

async function confirmCrop() {
  if (!cropImgEl) return
  const canvas = document.createElement('canvas')
  canvas.width = OUTPUT_SIZE; canvas.height = OUTPUT_SIZE
  const ctx = canvas.getContext('2d')
  const previewSize = cropCanvas.value?.width || 1
  const rect = getCropDrawRect(previewSize)
  const cropLeft = previewSize / 2 - CROP_SIZE / 2
  const cropTop = previewSize / 2 - CROP_SIZE / 2
  const sx = (cropLeft - rect.x) * (cropImgEl.width / rect.width)
  const sy = (cropTop - rect.y) * (cropImgEl.height / rect.height)
  const sw = CROP_SIZE * (cropImgEl.width / rect.width)
  const sh = CROP_SIZE * (cropImgEl.height / rect.height)
  ctx.clearRect(0, 0, OUTPUT_SIZE, OUTPUT_SIZE)
  ctx.save()
  ctx.beginPath()
  ctx.arc(OUTPUT_SIZE / 2, OUTPUT_SIZE / 2, OUTPUT_SIZE / 2, 0, Math.PI * 2)
  ctx.clip()
  ctx.drawImage(cropImgEl, sx, sy, sw, sh, 0, 0, OUTPUT_SIZE, OUTPUT_SIZE)
  ctx.restore()

  canvas.toBlob(async (blob) => {
    if (!blob) { ElMessage.error('处理失败'); return }
    uploading.value = true
    try {
      const fd = new FormData()
      fd.append('file', blob, 'avatar.png')
      const res = await request({ url: '/users/avatar/upload', method: 'post', data: fd, headers: { 'Content-Type': 'multipart/form-data' }, skipSuccessToast: true })
      if (res && res.avatar) {
        profileForm.avatar = res.avatar
        userStore.userInfo.avatar = res.avatar
        localStorage.setItem('user_info', JSON.stringify(userStore.userInfo))
        ElMessage.success('头像更新成功')
      }
      showCrop.value = false
    } catch {} finally { uploading.value = false }
  }, 'image/png')
}

onMounted(() => {
  loadProfile()
})
</script>

<style scoped>
.profile-container {
  max-width: 720px;
  margin: 0 auto;
  padding: 20px 0;
}
.profile-container :deep(.el-card) { border-radius: 12px; }
.profile-container :deep(.el-tabs__header) { margin-bottom: 24px; }
.profile-container :deep(.el-tabs__item) { font-size: 16px; }
.basic-info-role { display: flex; justify-content: flex-end; margin: 12px 0 4px; padding-right: 16px; }
.profile-container :deep(.el-form-item) { margin-bottom: 26px; }
.form-hint { color: #909399; font-size: 12px; display: block; margin-top: 4px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.card-header h3 { margin: 0; }

/* 头像区 */
.avatar-section { display: flex; align-items: center; gap: 20px; }
.avatar-preview {
  width: 100px; height: 100px; border-radius: 50%; overflow: hidden; cursor: pointer;
  position: relative; flex-shrink: 0; border: 3px solid #f0f0f0;
}
.avatar-img-round { width: 100%; height: 100%; object-fit: cover; }
.avatar-letter { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 42px; font-weight: 700; }
.avatar-overlay {
  position: absolute; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 4px; color: #fff; font-size: 12px; opacity: 0; transition: opacity .2s;
}
.avatar-preview:hover .avatar-overlay { opacity: 1; }

.avatar-upload-wrap { flex-shrink: 0; }
.avatar-upload-wrap :deep(.el-upload) { display: block; }

/* 裁剪弹窗 */
.crop-area { text-align: center; }
.crop-canvas-wrap { width: 100%; max-width: 400px; margin: 0 auto 16px; }
.crop-canvas-wrap canvas { width: 100%; border-radius: 50%; cursor: grab; }
.crop-canvas-wrap canvas:active { cursor: grabbing; }
.crop-controls { display: flex; align-items: center; gap: 8px; padding: 0 16px; }
.crop-label { font-size: 13px; color: #666; white-space: nowrap; }
.crop-controls :deep(.el-slider) { flex: 1; }

/* 弹窗：自适应屏幕高度 */
:deep(.el-dialog) { display: flex; flex-direction: column; max-height: min(90vh, 750px); }
:deep(.el-dialog__body) { flex: 1; overflow-y: auto; padding: 20px 28px; }

/* 移动端适配 */
@media (max-width: 768px) {
  .el-row { flex-direction: column !important; }
  .el-row .el-col { max-width: 100% !important; flex: 0 0 100% !important; margin-bottom: 12px; }
  .el-dialog { width: 95vw !important; max-width: 95vw !important; }
  .el-table { font-size: 13px; overflow-x: auto; display: block; }
  .el-pagination { justify-content: center !important; }
  .card-header, .list-header, .tree-header { flex-direction: column; align-items: flex-start; gap: 8px; }
  .header-actions, .tree-header-actions { flex-wrap: wrap; }
}
</style>
