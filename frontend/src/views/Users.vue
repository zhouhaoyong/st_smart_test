<template>
  <div class="page-wrap">
    <div class="admin-page-title"><h2>平台用户管理</h2></div>
    <div class="search-area">
      <el-form :model="searchForm" inline>
        <el-form-item label="手机号">
          <el-input v-model="searchForm.phone" placeholder="模糊搜索" clearable style="width:120px" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="真实姓名">
          <el-input v-model="searchForm.real_name" placeholder="模糊搜索" clearable style="width:120px" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="部门">
          <el-select v-model="searchForm.department" placeholder="全部" clearable style="width:120px">
            <el-option label="测试部门" :value="1" /><el-option label="开发部门" :value="2" />
            <el-option label="产品部门" :value="4" /><el-option label="运维部门" :value="3" /><el-option label="其他部门" :value="5" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.is_active" placeholder="全部" clearable style="width:90px">
            <el-option label="启用" :value="true" /><el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="searchForm.role" placeholder="全部" clearable style="width:120px">
            <el-option label="超级管理员" value="superuser" />
            <el-option label="管理员" value="manager" />
            <el-option label="普通用户" value="normal" />
          </el-select>
        </el-form-item>
        <el-form-item class="search-actions">
          <div class="search-action-buttons">
            <el-button @click="handleSearch">查询</el-button>
            <el-button @click="handleReset">重置</el-button>
          </div>
        </el-form-item>
        <el-form-item>
          <el-button @click="roleHelpVisible = true">角色说明</el-button>
        </el-form-item>
        <el-form-item v-if="canCreateUser(userStore.userInfo)">
          <el-button type="primary" @click="handleAdd">添加用户</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="scroll-area" v-loading="loading">
      <el-table :data="userList" stripe>
        <el-table-column prop="id" label="ID" width="64" class-name="id-cell" />
        <el-table-column prop="real_name" label="真实姓名" min-width="110" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" underline="never" @click.stop="openUserDetail(row)">{{ row.real_name || '-' }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="手机号" min-width="145" show-overflow-tooltip />
        <el-table-column prop="nick_name" label="昵称" min-width="110" show-overflow-tooltip>
          <template #default="{ row }">{{ row.nick_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="department" label="部门" min-width="110" show-overflow-tooltip>
          <template #default="{ row }">{{ deptMap[row.department] || row.department }}</template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" size="small" @change="(v) => handleToggleActive(row, v)" :disabled="!canToggleUser(userStore.userInfo, row)" />
          </template>
        </el-table-column>
        <el-table-column prop="role" label="角色" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_superuser ? 'primary' : row.is_manager ? 'warning' : 'success'" size="small">
              {{ row.is_superuser ? '超级管理员' : row.is_manager ? '管理员' : '普通用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="login_count" label="登录次数" width="90" align="center" />
        <el-table-column prop="last_login_at" label="最后登录" min-width="165" show-overflow-tooltip>
          <template #default="{ row }">{{ row.last_login_at ? (formatBeijingMinute(row.last_login_at) || '-') : '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="注册时间" min-width="165" show-overflow-tooltip>
          <template #default="{ row }">{{ row.created_at ? (formatBeijingMinute(row.created_at) || '-') : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button v-if="canManageUser(userStore.userInfo, row)" link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button v-if="canDeleteUser(userStore.userInfo, row)" link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pagination-area" v-if="total > 0">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, sizes, prev, pager, next"
        :page-sizes="[10, 50, 100]"
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
    </div>

    <UserDialog v-model="detailVisible" :user-id="detailUserId" mode="view" />

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '添加用户'" width="520px" destroy-on-close>
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="100px">
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入11位手机号" :disabled="isEdit" maxlength="11" />
        </el-form-item>
        
        <el-form-item label="真实姓名" prop="real_name">
          <el-input v-model="form.real_name" placeholder="请输入中文姓名" />
        </el-form-item>
        
        <el-form-item label="昵称" prop="nick_name">
          <el-input v-model="form.nick_name" placeholder="可选（不超过50个字符）" />
        </el-form-item>
        
        <el-form-item label="性别" prop="gender">
          <el-select v-model="form.gender" style="width:100%">
            <el-option label="男" :value="1" /><el-option label="女" :value="2" /><el-option label="其他" :value="3" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="部门" prop="department">
          <el-select v-model="form.department" style="width:100%">
            <el-option label="测试部门" :value="1" /><el-option label="开发部门" :value="2" />
            <el-option label="产品部门" :value="4" /><el-option label="运维部门" :value="3" /><el-option label="其他部门" :value="5" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="!isEdit" label="角色">
          <el-select v-model="form.role" style="width:100%">
            <el-option label="普通用户" value="normal" />
            <el-option label="管理员" value="manager" />
            <el-option label="超级管理员" value="superuser" />
          </el-select>
        </el-form-item>
        
        <el-form-item v-if="!isEdit" label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="至少6位，需包含大小写字母" show-password />
        </el-form-item>
        
        <el-form-item v-if="!isEdit" label="确认密码" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" placeholder="请再次输入密码" show-password />
        </el-form-item>
        
        <el-divider v-if="isEdit" />
        
        <el-row v-if="isEdit" :gutter="16">
          <el-col v-if="canToggleUser(userStore.userInfo, form)" :span="8">
            <el-form-item label="状态">
              <el-switch v-model="form.is_active" size="small" />
            </el-form-item>
          </el-col>
          <el-col v-if="userStore.userInfo?.is_superuser" :span="8">
            <el-form-item label="管理员">
              <el-switch v-model="form.is_manager" size="small" :disabled="form.is_superuser || form.id === userStore.userInfo?.id" />
            </el-form-item>
          </el-col>
          <el-col v-if="userStore.userInfo?.is_superuser" :span="8">
            <el-form-item label="超级管理员">
              <el-switch v-model="form.is_superuser" size="small" :disabled="form.id === userStore.userInfo?.id" @change="handleSuperuserChange" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item v-if="isEdit && canResetUserPassword(userStore.userInfo, form)" label="密码管理">
          <el-button type="danger" size="default" @click="handleResetClick" :loading="pwdLoading">重置密码</el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>

    <!-- 角色说明 -->
    <el-dialog v-model="roleHelpVisible" title="角色说明" width="1180px" destroy-on-close>
      <div class="role-help">
        <p class="role-help-intro">平台角色决定系统功能权限，部门只表示组织归属，不会自动授予权限。项目创建人权限按项目规则另行叠加。</p>
        <el-tabs v-model="roleHelpTab" class="role-help-tabs">
          <el-tab-pane label="测试工作台" name="workbench">
            <el-table :data="roleHelpTables.workbench.rows" border max-height="520" class="role-help-table">
              <el-table-column
                v-for="column in roleHelpTables.workbench.columns"
                :key="column.prop"
                :prop="column.prop"
                :label="column.label"
                :width="column.width"
                :min-width="column.minWidth"
              />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="API 测试" name="api">
            <el-table :data="roleHelpTables.api.rows" border max-height="520" class="role-help-table">
              <el-table-column
                v-for="column in roleHelpTables.api.columns"
                :key="column.prop"
                :prop="column.prop"
                :label="column.label"
                :width="column.width"
                :min-width="column.minWidth"
              />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="工具箱" name="tools">
            <el-table :data="roleHelpTables.tools.rows" border max-height="520" class="role-help-table">
              <el-table-column
                v-for="column in roleHelpTables.tools.columns"
                :key="column.prop"
                :prop="column.prop"
                :label="column.label"
                :width="column.width"
                :min-width="column.minWidth"
              />
            </el-table>
            <p class="role-help-tab-note">工具箱是通用工具模块，登录用户均可使用，不授予项目或平台管理权限。</p>
          </el-tab-pane>
          <el-tab-pane label="导航管理" name="navigation">
            <el-table :data="roleHelpTables.navigation.rows" border max-height="520" class="role-help-table">
              <el-table-column
                v-for="column in roleHelpTables.navigation.columns"
                :key="column.prop"
                :prop="column.prop"
                :label="column.label"
                :width="column.width"
                :min-width="column.minWidth"
              />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="管理中心" name="management">
            <el-table :data="roleHelpTables.management.rows" border max-height="520" class="role-help-table">
              <el-table-column
                v-for="column in roleHelpTables.management.columns"
                :key="column.prop"
                :prop="column.prop"
                :label="column.label"
                :width="column.width"
                :min-width="column.minWidth"
              />
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>

    <!-- 密码重置结果弹窗 -->
    <el-dialog v-model="pwdDialogVisible" title="密码已重置" width="420px" :close-on-click-modal="false">
      <div class="pwd-result">
        <el-icon :size="48" color="#67c23a"><SuccessFilled /></el-icon>
        <p class="pwd-result-title">新密码已生成</p>
        <div class="pwd-display">
          <code class="pwd-text">{{ newPassword }}</code>
          <el-button type="primary" size="small" @click="copyPassword" :icon="DocumentCopy">复制</el-button>
        </div>
        <el-alert type="warning" :closable="false" show-icon style="margin-top:12px">
          请妥善保管新密码，关闭后将无法再次查看
        </el-alert>
      </div>
      <template #footer>
        <el-button type="primary" @click="pwdDialogVisible = false">我知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { SuccessFilled, DocumentCopy } from '@element-plus/icons-vue'
import { formatBeijingMinute } from '@/utils/beijingTime'
import { getUsers, updateUser, resetUserPassword, createUser, deleteUser } from '@/api/user'
import request from '@/utils/request'
import UserDialog from '@/components/UserDialog.vue'
import { useUserStore } from '@/stores/user'
import { canCreateUser, canManageUser, canResetUserPassword, canToggleUser, canDeleteUser } from '@/utils/permission'
import { copyToClipboard } from '@/utils/clipboard'

const loading = ref(false)
const userList = ref([])
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const submitLoading = ref(false)
const pwdLoading = ref(false)
const pwdDialogVisible = ref(false)
const newPassword = ref('')
const detailVisible = ref(false)
const detailUserId = ref(null)
const roleHelpVisible = ref(false)
const roleHelpTab = ref('workbench')
const deptMap = { 1: '测试部门', 2: '开发部门', 4: '产品部门', 3: '运维部门', 5: '其他部门' }
const userStore = useUserStore()

const projectRoleColumns = [
  { prop: 'operation', label: '操作', width: '210' },
  { prop: 'owner', label: '项目创建人', width: '150' },
  { prop: 'superAdmin', label: '超级管理员（非项目创建人）', minWidth: '210' },
  { prop: 'manager', label: '管理员（非项目创建人）', minWidth: '190' },
  { prop: 'normal', label: '普通用户（非项目创建人）', minWidth: '190' },
]

const roleColumns = [
  { prop: 'operation', label: '操作', width: '280' },
  { prop: 'superAdmin', label: '超级管理员', minWidth: '220' },
  { prop: 'manager', label: '管理员', minWidth: '220' },
  { prop: 'normal', label: '普通用户', minWidth: '220' },
]

const roleHelpTables = {
  workbench: {
    columns: projectRoleColumns,
    rows: [
      { operation: '创建项目', owner: '可以', superAdmin: '可以', manager: '可以', normal: '可以' },
      { operation: '查看公开项目', owner: '可以', superAdmin: '可以', manager: '可以', normal: '可以' },
      { operation: '查看私有项目', owner: '可以', superAdmin: '可以', manager: '不可以', normal: '不可以' },
      { operation: '编辑、删除公开项目', owner: '可以', superAdmin: '可以', manager: '不可以', normal: '不可以' },
      { operation: '编辑、删除私有项目', owner: '可以', superAdmin: '可以', manager: '不可以', normal: '不可以' },
      { operation: '复制公开项目', owner: '可以', superAdmin: '可以', manager: '可以', normal: '可以复制公开内容' },
      { operation: '复制私有项目', owner: '可以', superAdmin: '可以', manager: '不可以', normal: '不可以' },
      { operation: '管理公开项目资产', owner: '管理全部', superAdmin: '管理全部', manager: '管理全部', normal: '查看全部、维护本人资产' },
      { operation: '管理私有项目资产', owner: '管理全部', superAdmin: '管理全部', manager: '不可以', normal: '不可以' },
      { operation: '查看公开项目数据看板', owner: '可以', superAdmin: '可以', manager: '可以', normal: '可以' },
      { operation: '查看私有项目数据看板', owner: '可以', superAdmin: '可以', manager: '不可以', normal: '不可以' },
      { operation: '清空公开项目数据', owner: '不可以', superAdmin: '可以', manager: '不可以', normal: '不可以' },
      { operation: '清空私有项目数据', owner: '可以', superAdmin: '可以', manager: '不可以', normal: '不可以' },
      { operation: '使用测试工作台 AI', owner: '可以', superAdmin: '可以', manager: '可以', normal: '可以' },
    ],
  },
  api: {
    columns: projectRoleColumns,
    rows: [
      { operation: '创建项目', owner: '可以', superAdmin: '可以', manager: '可以', normal: '可以' },
      { operation: '查看公开项目', owner: '可以', superAdmin: '可以', manager: '可以', normal: '可以' },
      { operation: '查看私有项目', owner: '可以', superAdmin: '可以', manager: '不可以', normal: '不可以' },
      { operation: '编辑、删除公开项目', owner: '可以', superAdmin: '可以', manager: '不可以', normal: '不可以' },
      { operation: '编辑、删除私有项目', owner: '可以', superAdmin: '可以', manager: '不可以', normal: '不可以' },
      { operation: '复制公开项目', owner: '可以', superAdmin: '可以', manager: '可以', normal: '不可以' },
      { operation: '复制私有项目', owner: '可以', superAdmin: '可以', manager: '不可以', normal: '不可以' },
      { operation: '管理公开项目接口资产', owner: '管理全部', superAdmin: '管理全部', manager: '管理全部', normal: '查看列表/汇总，详情受限' },
      { operation: '管理私有项目接口资产', owner: '管理全部', superAdmin: '管理全部', manager: '不可以', normal: '不可以' },
      { operation: '执行接口测试', owner: '可以', superAdmin: '可以', manager: '可以', normal: '不可以' },
      { operation: '查看操作记录', owner: '可以', superAdmin: '查看全部', manager: '查看全部', normal: '查看全部' },
      { operation: '清空公开项目数据', owner: '不可以', superAdmin: '可以', manager: '不可以', normal: '不可以' },
      { operation: '清空私有项目数据', owner: '可以', superAdmin: '可以', manager: '不可以', normal: '不可以' },
      { operation: '使用 API 测试 AI', owner: '可以', superAdmin: '全部项目', manager: '公开及本人私有项目', normal: '仅本人创建项目' },
    ],
  },
  tools: {
    columns: roleColumns,
    rows: [
      { operation: '使用工具箱功能', superAdmin: '可以', manager: '可以', normal: '可以' },
    ],
  },
  navigation: {
    columns: roleColumns,
    rows: [
      { operation: '查看全局导航', superAdmin: '可以', manager: '可以', normal: '可以' },
      { operation: '新增个人应用入口', superAdmin: '可以', manager: '可以', normal: '可以，归本人' },
      { operation: '编辑、删除本人应用入口', superAdmin: '可以', manager: '可以', normal: '可以' },
      { operation: '编辑、删除他人应用入口', superAdmin: '可以', manager: '可以', normal: '不可以' },
      { operation: '批量处理应用入口', superAdmin: '可以', manager: '可以', normal: '仅限本人应用' },
      { operation: '配置全局系统导航', superAdmin: '可以', manager: '可以', normal: '不可以' },
    ],
  },
  management: {
    columns: roleColumns,
    rows: [
      { operation: '个人资料', superAdmin: '管理本人', manager: '管理本人', normal: '管理本人' },
      { operation: '平台用户管理', superAdmin: '全部管理', manager: '不可管理', normal: '不可管理' },
      { operation: '平台模型', superAdmin: '查看、管理、使用', manager: '查看、使用', normal: '查看、使用' },
      { operation: '本人模型', superAdmin: '管理本人', manager: '管理本人', normal: '管理本人' },
      { operation: '他人模型', superAdmin: '查看受限信息', manager: '不可访问', normal: '不可访问' },
      { operation: 'AI 用量和调用记录', superAdmin: '查看全部、清理全部', manager: '查看本人', normal: '查看本人' },
      { operation: '消息渠道、消息模板、执行策略', superAdmin: '全部管理', manager: '全部管理', normal: '不可管理' },
      { operation: '平台治理审计日志', superAdmin: '查看、管理全部', manager: '不可访问', normal: '不可访问' },
      { operation: '平台数据清理', superAdmin: '可以，需二次确认', manager: '不可以', normal: '不可以' },
      { operation: '问题反馈', superAdmin: '查看全部、提醒、回复、解决、删除全部', manager: '提交、查看、跟进、删除本人', normal: '提交、查看、跟进、删除本人' },
    ],
  },
}

const searchForm = reactive({ phone: '', real_name: '', department: null, is_active: null, role: null })

const form = reactive({ 
  id: null, 
  phone: '', 
  real_name: '', 
  nick_name: '', 
  gender: 1,
  department: 1, 
  password: '',
  confirmPassword: '',
  role: 'normal',
  is_active: true, 
  is_manager: false, 
  is_superuser: false 
})

// 密码验证
const validatePass = (rule, value, callback) => {
  if (!value) callback(new Error('请再次输入密码'))
  else if (value !== form.password) callback(new Error('两次密码不一致'))
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

const formRules = {
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

const loadUsers = async () => {
  loading.value = true
  try {
    const params = {
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
    }
    if (searchForm.phone) params.phone = searchForm.phone
    if (searchForm.real_name) params.real_name = searchForm.real_name
    if (searchForm.department) params.department = searchForm.department
    if (searchForm.is_active !== null && searchForm.is_active !== '') params.is_active = searchForm.is_active
    if (searchForm.role) params.role = searchForm.role
    const res = await getUsers(params)
    userList.value = res?.items || res || []
    total.value = res?.total || 0
  } catch { userList.value = [] }
  finally { loading.value = false }
}

const onPageChange = (val) => {
  page.value = val
  loadUsers()
}

const onPageSizeChange = (size) => {
  pageSize.value = size
  page.value = 1
  loadUsers()
}

const handleSearch = () => {
  page.value = 1
  loadUsers()
}

const handleReset = () => {
  Object.assign(searchForm, { phone: '', real_name: '', department: null, is_active: null, role: null })
  page.value = 1
  loadUsers()
}

const handleToggleActive = async (row, val) => {
  try {
    await ElMessageBox.confirm(
      `确认${val ? '启用' : '禁用'}用户「${row.real_name}」？`,
      `${val ? '启用' : '禁用'}确认`,
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { row.is_active = !val; return }
  try {
    await request({ url: `/users/${row.id}/toggle-active`, method: 'post' })
  } catch (e) {
    row.is_active = !val
  }
}

const handleDelete = async (row) => {
  if (!canDeleteUser(userStore.userInfo, row)) return
  try {
    await ElMessageBox.confirm(
      `确认删除已禁用用户「${row.real_name}」？删除后账号及其模型将不可恢复。`,
      '高危删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteUser(row.id)
    ElMessage.success('用户删除成功')
    await loadUsers()
  } catch { }
}

const openUserDetail = (row) => {
  detailUserId.value = row.id
  detailVisible.value = true
}

const handleEdit = (row) => {
  if (!canManageUser(userStore.userInfo, row)) return
  isEdit.value = true
  Object.assign(form, {
    id: row.id, phone: row.phone, real_name: row.real_name, nick_name: row.nick_name || '',
    gender: row.gender, department: row.department, is_active: row.is_active,
    is_manager: row.is_manager, is_superuser: row.is_superuser,
    role: row.is_superuser ? 'superuser' : row.is_manager ? 'manager' : 'normal',
    password: '',
    confirmPassword: ''
  })
  dialogVisible.value = true
  // 清除之前的验证错误
  setTimeout(() => formRef.value?.clearValidate(), 100)
}

const handleAdd = () => {
  if (!canCreateUser(userStore.userInfo)) return
  isEdit.value = false
  Object.assign(form, {
    id: null,
    phone: '',
    real_name: '',
    nick_name: '',
    gender: 1,
    department: 1,
    password: '',
    confirmPassword: '',
    role: 'normal',
    is_active: true,
    is_manager: false,
    is_superuser: false
  })
  dialogVisible.value = true
  // 清除之前的验证错误
  setTimeout(() => formRef.value?.clearValidate(), 100)
}

const handleSuperuserChange = (value) => {
  if (value) form.is_manager = false
}

const handleResetClick = async () => {
  pwdLoading.value = true
  try {
    const res = await resetUserPassword(form.id)
    newPassword.value = res.password || ''
    pwdDialogVisible.value = true
    // 自动复制到剪贴板
    try {
      if (await copyToClipboard(newPassword.value)) ElMessage.success('新密码已自动复制到剪贴板')
    } catch { /* 浏览器不支持自动复制 */ }
  } catch { }
  finally { pwdLoading.value = false }
}

const copyPassword = async () => {
  try {
    if (await copyToClipboard(newPassword.value)) ElMessage.success('已复制到剪贴板')
    else ElMessage.warning('复制失败，请手动复制')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitLoading.value = true
    try {
      if (isEdit.value) {
        // 编辑模式
        await updateUser(form.id, {
          real_name: form.real_name, nick_name: form.nick_name || null,
          gender: form.gender, department: form.department,
          is_active: form.is_active, is_manager: form.is_manager, is_superuser: form.is_superuser,
        })
      } else {
        // 新增模式
        const { confirmPassword, role, ...data } = form
        data.is_superuser = role === 'superuser'
        data.is_manager = role === 'manager'
        await createUser(data)
      }
      dialogVisible.value = false
      loadUsers()
    } finally { submitLoading.value = false }
  })
}

onMounted(() => { loadUsers() })
</script>

<style scoped>
.page-wrap { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; flex-shrink: 0; margin-bottom: 16px; }
.page-title h2 { margin: 0 0 6px; font-size: 20px; font-weight: 600; color: #1a1a1a; }
.page-desc { font-size: 15px; color: #8c8c8c; }

.search-area { flex-shrink: 0; background: #fff; border: 1px solid #f0f0f0; border-radius: 12px; padding: 12px 16px; margin-bottom: 12px; }
.search-area .el-form { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 12px 10px; margin-bottom: 0; }
.search-area :deep(.el-form-item) { margin: 0; }
.search-actions { flex: 0 0 auto; min-width: 0; }
.search-action-buttons { display: flex; flex-wrap: wrap; gap: 10px 12px; }
.search-action-buttons :deep(.el-button) { margin: 0; }

.role-help-intro { margin: 0 0 14px; color: #606266; font-size: 14px; line-height: 1.7; }
.role-help-tabs :deep(.el-tabs__content) { overflow: visible; }
.role-help-table :deep(.cell) { white-space: normal; line-height: 1.7; word-break: break-word; }
.role-help-tab-note { margin: 12px 0 0; color: #909399; font-size: 13px; line-height: 1.7; }

.scroll-area { flex: 1; overflow-y: auto; min-height: 0; background: #fff; border: 1px solid #f0f0f0; border-radius: 12px; padding: 4px; }
.scroll-area :deep(.el-table__body-wrapper) { overflow-y: auto; }

.pagination-area { flex-shrink: 0; display: flex; justify-content: flex-end; padding: 12px 0 0; }

/* 统一操作列背景色 */
:deep(.el-table__fixed-right) {
  box-shadow: none !important;
}
:deep(.el-table__fixed-right-patch) {
  background: transparent !important;
}
:deep(.el-table__fixed-right .el-table__row) {
  background: inherit !important;
}
:deep(.el-table__fixed-right .el-table__row:hover) {
  background: inherit !important;
}
.page-desc { font-size: 15px; color: #8c8c8c; }

.pwd-result { text-align: center; padding: 10px 0; }
.pwd-result-title { font-size: 18px; font-weight: 600; color: #1a1a1a; margin: 12px 0 16px; }
.pwd-display { display: flex; gap: 10px; align-items: center; justify-content: center; margin: 16px 0; }
.pwd-text { background: #f5f5f5; padding: 10px 16px; border-radius: 6px; font-family: SFMono-Regular, Consolas, monospace; font-size: 18px; letter-spacing: 2px; border: 1px dashed #d9d9d9; }

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
