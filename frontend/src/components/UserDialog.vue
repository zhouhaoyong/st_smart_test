<template>
  <el-dialog v-model="visible" :title="isEdit ? '编辑用户' : '用户详情'" width="560px" destroy-on-close @closed="onClosed">
    <div v-loading="loading">
      <div class="ud-header" v-if="user">
        <div class="ud-avatar" :style="user.avatar ? {} : { background: avatarColor }">
          <img v-if="user.avatar" :src="user.avatar" :alt="`${user.real_name || '用户'}头像`" />
          <span v-else>{{ user.real_name?.charAt(0) || '?' }}</span>
        </div>
        <div class="ud-names">
          <strong>{{ user.real_name || '—' }}</strong>
          <span>ID: {{ user.id }}</span>
        </div>
      </div>
      <el-form :model="form" label-width="80px" class="ud-form" v-if="user">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="真实姓名">
              <el-input v-model="form.real_name" :disabled="!isEdit" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="昵称">
              <el-input v-model="form.nick_name" :disabled="!isEdit" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="手机号">
              <el-input v-model="form.phone" :disabled="!isEdit" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="部门">
              <el-select v-model="form.department" :disabled="!isEdit" style="width:100%">
                <el-option v-for="item in departmentOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-tag v-if="!isEdit" :type="form.is_active ? 'success' : 'danger'" size="small">{{ form.is_active ? '启用' : '禁用' }}</el-tag>
              <el-switch v-else v-model="form.is_active" active-text="启用" inactive-text="禁用" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="角色">
              <el-tag v-if="!isEdit" :type="form.is_superuser ? 'primary' : form.is_manager ? 'warning' : 'success'" size="small">
                {{ form.is_superuser ? '超级管理员' : form.is_manager ? '管理员' : '普通用户' }}
              </el-tag>
              <div v-else class="role-checks">
                <el-checkbox v-model="form.is_manager" :disabled="form.is_superuser">管理员</el-checkbox>
                <el-checkbox v-model="form.is_superuser">超级管理员</el-checkbox>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="登录次数">{{ user.login_count || 0 }}</el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="最后登录">{{ fmt(user.last_login_at) }}</el-form-item>
        <el-form-item label="注册时间">{{ fmt(user.created_at) }}</el-form-item>
      </el-form>
      <el-empty v-else-if="!loading" description="用户不存在" :image-size="48" />
    </div>
    <template #footer>
      <el-button @click="visible = false">{{ isEdit ? '取消' : '关闭' }}</el-button>
      <el-button v-if="isEdit" type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { getUser, updateUser } from '@/api/user'
import { formatBeijingMinute } from '@/utils/beijingTime'

const props = defineProps({
  modelValue: Boolean,
  userId: { type: Number, default: null },
  mode: { type: String, default: 'view', validator: v => ['edit', 'view'].includes(v) },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})
const isEdit = computed(() => props.mode === 'edit')

const loading = ref(false)
const saving = ref(false)
const user = ref(null)
const form = ref({})

const avatarColors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2']
const avatarColor = computed(() => avatarColors[(props.userId || 0) % avatarColors.length])

const departmentOptions = [
  { value: 1, label: '测试部门' },
  { value: 2, label: '开发部门' },
  { value: 4, label: '产品部门' },
  { value: 3, label: '运维部门' },
  { value: 5, label: '其他部门' },
]

function fmt(d) {
  if (!d) return '—'
  return formatBeijingMinute(d) || '-'
}

async function loadUser() {
  if (!props.userId) return
  loading.value = true
  try {
    const u = await getUser(props.userId)
    user.value = u
    form.value = {
      real_name: u.real_name || '',
      nick_name: u.nick_name || '',
      phone: u.phone || '',
      department: u.department ?? '',
      is_active: !!u.is_active,
      is_manager: !!u.is_manager,
      is_superuser: !!u.is_superuser,
    }
  } catch {
    user.value = null
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    // 保存成功的提示以后端返回的 message 为准，这里不再重复提示
    await updateUser(props.userId, form.value)
    emit('saved')
    visible.value = false
  } catch { /* handled by interceptor */ }
  finally { saving.value = false }
}

function onClosed() {
  user.value = null
  form.value = {}
}

watch(() => props.userId, (id) => { if (id && visible.value) loadUser() })
watch(visible, (v) => { if (v && props.userId) loadUser() })
</script>

<style scoped>
.ud-header { display: flex; align-items: center; gap: 14px; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid #f0f0f0; }
.ud-avatar { width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; color: #fff; flex-shrink: 0; overflow: hidden; }
.ud-avatar img { width: 100%; height: 100%; object-fit: cover; }
.ud-names { display: flex; flex-direction: column; gap: 2px; }
.ud-names strong { font-size: 16px; color: #1a1a1a; }
.ud-names span { font-size: 12px; color: #8c8c8c; }
.ud-form { margin-top: 4px; }
.role-checks { display: flex; gap: 12px; align-items: center; }
</style>
