<template>
  <div class="page-wrap">
    <div class="admin-page-title"><h2>审计日志管理</h2></div>
    <div class="search-bar">
      <el-select v-model="searchForm.user_id" placeholder="全部用户" clearable style="width:140px">
        <el-option v-for="user in userList" :key="user.id" :label="user.real_name" :value="user.id" />
      </el-select>
      <el-select v-model="searchForm.module" multiple collapse-tags collapse-tags-tooltip placeholder="全部模块" clearable style="width:180px">
        <el-option v-for="item in moduleOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="searchForm.operation" multiple filterable collapse-tags collapse-tags-tooltip placeholder="全部操作" clearable style="width:220px">
        <el-option-group v-for="group in operationFilterGroups" :key="group.label" :label="group.label">
          <el-option v-for="item in group.options" :key="item.value" :label="item.label" :value="item.value" />
        </el-option-group>
      </el-select>
      <el-date-picker
        v-model="searchForm.dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        class="audit-date-range"
        style="width:260px"
      />
      <div class="search-actions">
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
        <el-button
          v-if="isSuperAdmin"
          type="danger"
          plain
          :disabled="!selectedIds.length"
          @click="handleBatchDelete"
        >批量删除<span v-if="selectedIds.length">（{{ selectedIds.length }}）</span></el-button>
        <el-button
          v-if="isSuperAdmin"
          type="danger"
          :disabled="!canDeleteAll"
          @click="handleDeleteAll"
        >全部删除<span v-if="hasLoaded">（{{ total }}）</span></el-button>
      </div>
    </div>

    <div class="log-card">
      <div class="log-card-hd">
        <span class="log-card-title">审计日志列表</span>
        <span class="log-card-total">
          {{ hasLoaded ? `查询结果：共 ${total} 条` : '请先查询' }}
          <template v-if="hasLoaded && filtersDirty">（筛选条件已修改，请点击查询）</template>
        </span>
      </div>
      <div class="log-card-body" v-loading="loading">
        <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" class="load-error">
          <el-button link type="danger" @click="loadAuditLogs">重试</el-button>
        </el-alert>
        <el-table :data="logList" stripe border size="small" class="log-table" empty-text=" " v-if="logList.length || loading" @selection-change="handleSelectionChange">
          <el-table-column type="selection" width="52" fixed="left" align="center" header-align="center" class-name="selection-column" header-class-name="selection-column" />
          <el-table-column label="操作用户" width="180">
            <template #default="{ row }">
              <el-button v-if="row.user_id" link type="primary" class="user-cell user-link" @click.stop="openUserDetail(row.user_id)">
                <span class="user-avatar-sm" :style="row.user_avatar ? {} : { background: avatarColor(row.user_id) }">
                  <img v-if="row.user_avatar" :src="row.user_avatar" :alt="`${row.user_name || '操作用户'}头像`" />
                  <span v-else>{{ row.user_name?.charAt(0) || '?' }}</span>
                </span>
                <span class="user-name-text">{{ row.user_name || '-' }}</span>
              </el-button>
              <div v-else class="user-cell">
                <span class="user-avatar-sm" :style="row.user_avatar ? {} : { background: avatarColor(row.user_id) }">
                  <img v-if="row.user_avatar" :src="row.user_avatar" :alt="`${row.user_name || '操作用户'}头像`" />
                  <span v-else>{{ row.user_name?.charAt(0) || '?' }}</span>
                </span>
                <span class="user-name-text">{{ row.user_name || '-' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="模块" width="130" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag :type="moduleTag(row.module)" size="small" effect="plain">{{ getModuleName(row.module) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作类型" width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag :type="operationTag(row.operation)" size="small" effect="plain">{{ getOperationName(row.operation) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作内容" min-width="520" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="content-text">{{ formatContent(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="IP地址" width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="ip-text">{{ row.ip_address || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作时间" width="180">
            <template #default="{ row }">
              <span class="time-text">{{ fullTime(row.created_at) }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && !logList.length" description="暂无审计日志" :image-size="60" />
      </div>
      <div class="log-card-ft">
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
    </div>
    <UserDialog v-model="detailVisible" :user-id="detailUserId" mode="view" />
  </div>
</template>

<script setup>
import { computed, ref, reactive, onMounted } from 'vue'
import { deleteAuditLogsAll, deleteAuditLogsBatch, getAuditLogs } from '@/api/audit'
import { getUsers } from '@/api/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { formatBeijingTime } from '@/utils/beijingTime'
import { resolveAiAuditFunctionLabel } from '@/utils/aiUsageLabels'
import {
  flattenOperationValues,
  formatAuditContent,
  getModuleName,
  getOperationName,
  moduleOptions,
  moduleTag,
  operationFilterGroups,
  operationTag,
} from '@/utils/auditContent'
import UserDialog from '@/components/UserDialog.vue'

const loading = ref(false)
const logList = ref([])
const userList = ref([])
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const hasLoaded = ref(false)
const selectedIds = ref([])
const errorMessage = ref('')
const detailVisible = ref(false)
const detailUserId = ref(null)
const userStore = useUserStore()
const isSuperAdmin = computed(() => !!userStore.userInfo?.is_superuser)

const searchForm = reactive({
  user_id: null,
  module: [],
  operation: [],
  dateRange: null
})

const cloneSearchForm = (form) => ({
  user_id: form.user_id,
  module: Array.isArray(form.module) ? [...form.module] : form.module ? [form.module] : [],
  operation: Array.isArray(form.operation) ? [...form.operation] : form.operation ? [form.operation] : [],
  dateRange: Array.isArray(form.dateRange) ? [...form.dateRange] : null,
})
const serializeSearchForm = (form) => JSON.stringify({
  user_id: form.user_id || null,
  module: Array.isArray(form.module) ? form.module : form.module ? [form.module] : [],
  operation: Array.isArray(form.operation) ? form.operation : form.operation ? [form.operation] : [],
  dateRange: Array.isArray(form.dateRange)
    ? form.dateRange.map(value => value?.valueOf?.() ?? value)
    : null,
})
const appliedSearchForm = ref(cloneSearchForm(searchForm))
const appliedSearchKey = ref(serializeSearchForm(appliedSearchForm.value))
const filtersDirty = computed(() => serializeSearchForm(searchForm) !== appliedSearchKey.value)
const canDeleteAll = computed(() => isSuperAdmin.value && hasLoaded.value && !filtersDirty.value && total.value > 0)

const avatarColors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#f5222d', '#faad14']
const avatarColor = (id) => avatarColors[(id || 0) % avatarColors.length]

const fullTime = (d) => d ? formatBeijingTime(d) : '-'
const openUserDetail = (userId) => {
  if (!userId) return
  detailUserId.value = Number(userId)
  detailVisible.value = true
}

const formatContent = (row) => formatAuditContent(row, resolveAiAuditFunctionLabel)

// 操作类型下拉里一个业务标签可能对应多个后端取值，查询前统一展开成取值数组。
const buildFilterParams = () => {
  const appliedForm = appliedSearchForm.value
  const params = {}
  if (appliedForm.user_id) params.user_id = appliedForm.user_id
  if (appliedForm.module?.length) params.module = appliedForm.module
  const operations = flattenOperationValues(appliedForm.operation)
  if (operations.length) params.operation = operations
  if (appliedForm.dateRange?.length === 2) {
    params.start_time = formatBeijingTime(appliedForm.dateRange[0])
    params.end_time = `${formatBeijingTime(appliedForm.dateRange[1]).slice(0, 10)} 23:59:59`
  }
  return params
}

const loadAuditLogs = async () => {
  hasLoaded.value = false
  loading.value = true
  errorMessage.value = ''
  try {
    const params = {
      ...buildFilterParams(),
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
    }
    const res = await getAuditLogs(params)
    logList.value = res.items || []
    total.value = res.total || 0
    selectedIds.value = []
  } catch (error) { errorMessage.value = error?.message || '审计日志加载失败，请重试' }
  finally {
    hasLoaded.value = true
    loading.value = false
  }
}

const onPageChange = (val) => { page.value = val; loadAuditLogs() }
const onPageSizeChange = (size) => { pageSize.value = size; page.value = 1; loadAuditLogs() }

const loadUsers = async () => {
  try {
    const res = await getUsers({ limit: 1000 })
    userList.value = res.items || res || []
  } catch { userList.value = [] }
}

const handleSearch = () => {
  appliedSearchForm.value = cloneSearchForm(searchForm)
  appliedSearchKey.value = serializeSearchForm(appliedSearchForm.value)
  page.value = 1
  loadAuditLogs()
}
const handleReset = () => {
  Object.assign(searchForm, { user_id: null, module: [], operation: [], dateRange: null })
  handleSearch()
}

const handleSelectionChange = (rows) => {
  selectedIds.value = rows.map(row => row.id)
}

const handleBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(`将删除已选的 ${selectedIds.value.length} 条审计日志，删除后无法在页面恢复，是否继续？`, '删除确认', {
      type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消',
    })
    const res = await deleteAuditLogsBatch(selectedIds.value)
    ElMessage.success(res?.message || '审计日志已删除')
    await loadAuditLogs()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') console.error('删除审计日志失败', error)
  }
}

const handleDeleteAll = async () => {
  try {
    await ElMessageBox.confirm(`将删除当前查询结果中的 ${total.value} 条审计日志，删除后无法在页面恢复，是否继续？`, '全部删除确认', {
      type: 'warning', confirmButtonText: '确认全部删除', cancelButtonText: '取消',
    })
    const res = await deleteAuditLogsAll(buildFilterParams())
    ElMessage.success(res?.message || '审计日志已删除')
    await loadAuditLogs()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') console.error('删除审计日志失败', error)
  }
}

onMounted(() => { loadAuditLogs(); loadUsers() })
</script>

<style scoped>
.page-wrap { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.page-desc { margin: 0 0 12px; font-size: 13px; color: #8c8c8c; flex-shrink: 0; }

.search-bar { flex-shrink: 0; display: flex; gap: 12px 10px; padding: 12px 16px; margin-bottom: 14px; flex-wrap: wrap; align-items: center; }
.search-actions { flex: 0 0 auto; display: flex; flex-wrap: nowrap; gap: 10px 12px; white-space: nowrap; }
.search-actions :deep(.el-button) { margin: 0; }
.search-bar :deep(.audit-date-range) { width: 260px !important; flex: 0 0 260px; }

.log-card {
  flex: 1; min-height: 0; display: flex; flex-direction: column;
  border: 1px solid #edf1f7; border-radius: 8px; background: #fff;
  overflow: hidden;
}
.log-card-hd {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; border-bottom: 1px solid #f0f0f0; flex-shrink: 0;
}
.log-card-title { font-size: 14px; font-weight: 600; color: #1f2937; }
.log-card-total { font-size: 13px; color: #909399; }
.log-card-body { flex: 1; min-height: 0; overflow: auto; }
.load-error { margin: 10px 0; }
.log-card-ft {
  display: flex; justify-content: flex-end;
  padding: 10px 20px; border-top: 1px solid #f0f0f0; flex-shrink: 0;
}

.log-table { width: 100%; table-layout: fixed; }
.log-table :deep(.el-table__header .cell) { white-space: nowrap; padding-left: 8px; padding-right: 8px; }
.log-table :deep(.el-table__cell .cell) { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-left: 8px; padding-right: 8px; }
.log-table :deep(.selection-column .cell) { display: flex; align-items: center; justify-content: center; }

.user-cell { display: flex; align-items: center; }
.user-link { width: 100%; justify-content: flex-start; margin: 0; padding: 0; overflow: hidden; }
.user-avatar-sm {
  width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  margin-right: 10px;
  font-size: 11px; font-weight: 700; color: #fff;
  overflow: hidden;
}
.user-avatar-sm img { width: 100%; height: 100%; object-fit: cover; }
.user-name-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.content-text { color: #303133; }
.ip-text { font-family: SFMono-Regular, Consolas, monospace; color: #8c8c8c; font-size: 12px; }
.time-text { white-space: nowrap; color: #606266; }
</style>
