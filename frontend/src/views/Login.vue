<template>
  <div class="login-page">
    <!-- 左侧品牌区 -->
    <div class="login-brand">
      <div class="brand-content">
        <div class="brand-logo">
          <svg width="56" height="56" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="nxGrad" x1="0" y1="40" x2="40" y2="0">
                <stop offset="0%" stop-color="#1677ff"/>
                <stop offset="100%" stop-color="#722ed1"/>
              </linearGradient>
            </defs>
            <path d="M24 4 L12 22 L18 22 L14 36 L30 18 L22 18 Z" fill="url(#nxGrad)"/>
          </svg>
        </div>
        <h1>智测</h1>
        <p class="brand-desc">测试与研发工具一体化平台</p>
        <div class="brand-features">
          <div class="feature-item">
            <div class="feature-icon"><el-icon :size="20"><Connection /></el-icon></div>
            <span>测试工作台</span>
          </div>
          <div class="feature-item">
            <div class="feature-icon"><el-icon :size="20"><VideoPlay /></el-icon></div>
            <span>API测试</span>
          </div>
          <div class="feature-item">
            <div class="feature-icon"><el-icon :size="20"><Postcard /></el-icon></div>
            <span>工具箱</span>
          </div>
          <div class="feature-item">
            <div class="feature-icon"><el-icon :size="20"><Guide /></el-icon></div>
            <span>导航管理</span>
          </div>
        </div>
      </div>
      <div class="brand-footer">
        <span v-if="!isRegister">没有账号？<a @click="toggleMode">立即注册</a></span>
        <span v-else>已有账号？<a @click="toggleMode">立即登录</a></span>
      </div>
    </div>

    <!-- 右侧表单区 -->
    <div class="login-form-area">
      <div class="form-card">
        <!-- 登录表单 -->
        <template v-if="!isRegister">
          <div class="form-header">
            <h2>欢迎回来</h2>
            <p>登录您的 智测 账号</p>
          </div>
          <el-form :model="loginForm" :rules="loginRules" ref="loginFormRef" size="large" @keyup.enter="handleLogin">
            <el-form-item prop="username">
              <el-input v-model="loginForm.username" placeholder="手机号" :prefix-icon="Phone" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="loginForm.password" type="password" placeholder="密码" :prefix-icon="Lock" show-password @keyup.enter="handleLogin" />
            </el-form-item>
            <div class="form-extra">
              <el-checkbox v-model="loginForm.remember_me">记住我</el-checkbox>
            </div>
            <el-button type="primary" style="width:100%;height:46px;font-size:16px" :loading="loading" :disabled="loading" @click="handleLogin" round>
              登 录
            </el-button>
          </el-form>
        </template>

        <!-- 注册表单 -->
        <template v-else>
          <div class="form-header">
            <h2>创建账号</h2>
            <p>加入 智测 平台</p>
          </div>
          <el-form :model="registerForm" :rules="registerRules" ref="registerFormRef" size="large" label-width="100px" @keyup.enter="handleRegister">
            <el-form-item label="手机号" prop="phone">
              <el-input v-model="registerForm.phone" placeholder="请输入11位手机号" :prefix-icon="Phone" maxlength="11" />
            </el-form-item>
            
            <el-form-item label="真实姓名" prop="real_name">
              <el-input v-model="registerForm.real_name" placeholder="请输入中文姓名" :prefix-icon="User" />
            </el-form-item>
            
            <el-form-item label="昵称" prop="nick_name">
              <el-input v-model="registerForm.nick_name" placeholder="可选（不超过50个字符）" :prefix-icon="UserFilled" />
            </el-form-item>
            
            <el-form-item label="性别" prop="gender">
              <el-select v-model="registerForm.gender" placeholder="请选择性别" style="width:100%">
                <el-option label="男" :value="1" /><el-option label="女" :value="2" /><el-option label="其他" :value="3" />
              </el-select>
            </el-form-item>
            
            <el-form-item label="部门" prop="department">
              <el-select v-model="registerForm.department" placeholder="请选择部门" style="width:100%">
                <el-option label="测试部门" :value="1" /><el-option label="开发部门" :value="2" />
                <el-option label="产品部门" :value="4" /><el-option label="运维部门" :value="3" />
                <el-option label="其他部门" :value="5" />
              </el-select>
            </el-form-item>
            
            <el-form-item label="密码" prop="password">
              <el-input v-model="registerForm.password" type="password" placeholder="至少6位，需包含大小写字母" :prefix-icon="Lock" show-password />
            </el-form-item>
            
            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input v-model="registerForm.confirmPassword" type="password" placeholder="请再次输入密码" :prefix-icon="Lock" show-password />
            </el-form-item>
            
            <el-button type="primary" style="width:100%;height:46px;font-size:16px;margin-top:8px" :loading="loading" :disabled="loading" @click="handleRegister" round>
              注 册
            </el-button>
          </el-form>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { register } from '@/api/auth'
import { ElMessage } from 'element-plus'
import { Phone, Lock, User, UserFilled, Connection, VideoPlay, Guide, Postcard } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const loginFormRef = ref(null)
const registerFormRef = ref(null)
const loading = ref(false)
const isRegister = ref(false)

const loginForm = reactive({ username: '', password: '', remember_me: false })
const registerForm = reactive({
  phone: '', real_name: '', nick_name: '', password: '',
  confirmPassword: '', gender: 1, department: 1
})

const loginRules = {
  username: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const validatePass = (rule, value, callback) => {
  if (!value) callback(new Error('请再次输入密码'))
  else if (value !== registerForm.password) callback(new Error('两次密码不一致'))
  else callback()
}

// 验证密码必须包含大小写字母
const validatePasswordStrength = (rule, value, callback) => {
  if (!value) {
    callback(new Error('请输入密码'))
  } else if (value.length < 6) {
    callback(new Error('密码长度至少6位'))
  } else if (!/[a-z]/.test(value)) {
    callback(new Error('密码必须包含小写字母'))
  } else if (!/[A-Z]/.test(value)) {
    callback(new Error('密码必须包含大写字母'))
  } else {
    callback()
  }
}

// 验证真实姓名只能是中文
const validateChineseName = (rule, value, callback) => {
  if (!value) {
    callback(new Error('请输入真实姓名'))
  } else if (!/^[\u4e00-\u9fa5]{2,20}$/.test(value)) {
    callback(new Error('真实姓名必须是2-20个中文字符'))
  } else {
    callback()
  }
}

const registerRules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的11位手机号', trigger: 'blur' }
  ],
  real_name: [
    { required: true, validator: validateChineseName, trigger: 'blur' }
  ],
  nick_name: [{ max: 50, message: '不超过50个字符', trigger: 'blur' }],
  password: [
    { required: true, validator: validatePasswordStrength, trigger: 'blur' }
  ],
  confirmPassword: [{ required: true, validator: validatePass, trigger: 'blur' }],
  gender: [{ required: true, message: '请选择性别', trigger: 'change' }],
  department: [{ required: true, message: '请选择部门', trigger: 'change' }]
}

const toggleMode = () => {
  isRegister.value = !isRegister.value
  loginFormRef.value?.resetFields()
  registerFormRef.value?.resetFields()
}

const handleLogin = async () => {
  // 入口同步占位，避免连点、回车连按等重复提交产生多次登录请求与重复登录日志。
  if (!loginFormRef.value || loading.value) return
  loading.value = true
  try {
    const valid = await loginFormRef.value.validate().catch(() => false)
    if (!valid) return
    const success = await userStore.userLogin(loginForm)
    if (success) router.push(route.query.redirect || '/dashboard')
  } finally {
    loading.value = false
  }
}

const handleRegister = async () => {
  if (!registerFormRef.value) return
  await registerFormRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const { confirmPassword, ...data } = registerForm
      await register(data)
      // 后端已返回成功消息，拦截器会自动显示，这里只切换界面
      toggleMode()
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-page {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* 左侧品牌区 */
.login-brand {
  flex: 0 0 480px;
  background: linear-gradient(135deg, #0d1117 0%, #161b22 40%, #1a2332 100%);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #fff;
  position: relative;
  overflow: hidden;
}
.login-brand::before {
  content: '';
  position: absolute;
  width: 600px; height: 600px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(22,119,255,0.15) 0%, transparent 70%);
  top: -200px; right: -150px;
  pointer-events: none;
}
.login-brand::after {
  content: '';
  position: absolute;
  width: 400px; height: 400px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(82,196,26,0.1) 0%, transparent 70%);
  bottom: -100px; left: -80px;
  pointer-events: none;
}
.brand-content {
  text-align: center;
  position: relative;
  z-index: 1;
}
.brand-logo { margin-bottom: 24px; color: #1677ff; }
.brand-content h1 {
  font-size: 38px; font-weight: 800; margin: 0 0 8px;
  background: linear-gradient(135deg, #1677ff, #52c41a);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.brand-desc { font-size: 16px; color: rgba(255,255,255,0.55); margin: 0 0 40px; }

.brand-features { display: flex; flex-direction: column; gap: 16px; }
.feature-item {
  display: flex; align-items: center; gap: 14px;
  font-size: 15px; color: rgba(255,255,255,0.7);
}
.feature-icon {
  width: 40px; height: 40px; border-radius: 10px;
  background: rgba(255,255,255,0.08);
  display: flex; align-items: center; justify-content: center;
  color: rgba(255,255,255,0.6);
}

.brand-footer {
  position: absolute; bottom: 36px; font-size: 14px; color: rgba(255,255,255,0.4);
  z-index: 1;
}
.brand-footer a { color: #1677ff; cursor: pointer; text-decoration: none; }
.brand-footer a:hover { text-decoration: underline; }

/* 右侧表单区 */
.login-form-area {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f7f8fa;
  overflow-y: auto;
  padding: 32px 20px;
}
.form-card {
  width: 460px;
  background: #fff;
  border-radius: 16px;
  padding: 48px 40px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.06);
}
.form-header { margin-bottom: 32px; }
.form-header h2 { margin: 0; font-size: 24px; font-weight: 700; color: #1a1a1a; }
.form-header p { margin: 6px 0 0; font-size: 14px; color: #8c8c8c; }
.form-extra { margin-bottom: 18px; display: flex; justify-content: space-between; }

/* 响应式 */

/* 移动端 */
@media (max-width: 900px) {
  .login-brand { display: none; }
  .login-form-area { padding: 24px 16px; align-items: flex-start; }
  .form-card { width: 100%; max-width: 400px; padding: 32px 24px; }
}

@media (max-height: 760px) {
  .login-form-area { align-items: flex-start; }
  .form-card { padding-top: 28px; padding-bottom: 28px; }
  .form-header { margin-bottom: 20px; }
}
</style>
