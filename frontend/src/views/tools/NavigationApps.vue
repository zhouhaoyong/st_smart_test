<template>
  <div class="navigation-apps">
    <div class="page-header">
      <div>
        <h2>导航管理</h2>
        <p>按系统维护常用应用入口，支持多地址快速跳转</p>
      </div>
    </div>

    <div class="navigation-workspace">
      <aside class="system-sidebar">
        <div class="sidebar-head">
          <div class="sidebar-title">系统导航</div>
          <el-button class="config-button" link type="primary" :icon="Setting" @click="openSystemConfig">
            系统配置
          </el-button>
        </div>
        <el-input
          v-model="systemKeyword"
          class="system-search"
          placeholder="搜索系统"
          clearable
          :prefix-icon="Search"
          @keyup.enter="handleSystemSearch"
          @clear="resetSystemSearch"
        />
        <div class="system-search-actions">
          <el-button size="small" type="primary" :icon="Search" @click="handleSystemSearch">查询</el-button>
          <el-button size="small" :icon="Refresh" @click="resetSystemSearch">重置</el-button>
        </div>
        <div v-loading="systemNavLoading" class="system-nav-list">
          <button
            class="system-nav-item"
            :class="{ active: activeView === 'apps' && selectedSystemId === null }"
            @click="selectAllSystems"
          >
            <span class="system-name">全部</span>
            <span class="system-count">{{ allAppCount }}</span>
          </button>
          <button
            v-for="system in visibleSystems"
            :key="system.id"
            class="system-nav-item"
            :class="{ active: activeView === 'apps' && selectedSystemId === system.id }"
            @click="selectSystem(system)"
          >
            <span class="system-name">{{ system.name }}</span>
            <span class="system-meta">
              <span class="system-count">{{ system.app_count || 0 }}</span>
            </span>
          </button>
          <div v-if="initialLoadFailed" class="system-nav-error">
            加载失败
            <el-button link type="primary" @click="loadInitialNavigationData">重新加载</el-button>
          </div>
        </div>
        <el-pagination
          class="system-pagination"
          small
          background
          layout="sizes, prev, next"
          :page-size="systemPageSize"
          :current-page="systemPage"
          :page-sizes="[10, 50, 100]"
          :total="systemTotal"
          @size-change="handleSystemSizeChange"
          @current-change="handleSystemPageChange"
        />
      </aside>

      <main class="content-panel">
        <template v-if="activeView === 'systems'">
          <div class="content-title-row">
            <div>
              <h3>系统配置</h3>
              <p>维护左侧系统导航，配置完成后应用可以归属到对应系统</p>
            </div>
            <el-button v-if="canManageSystems" type="primary" :icon="Plus" @click="handleCreateSystem">新增系统</el-button>
          </div>

          <div class="system-config-toolbar">
            <el-input
              v-model="systemConfigKeyword"
              placeholder="按系统名称搜索"
              clearable
              :prefix-icon="Search"
              style="width: 260px"
              @keyup.enter="handleSystemConfigSearch"
            />
            <el-select
              v-model="systemConfigStatus"
              placeholder="状态"
              clearable
              style="width: 140px"
            >
              <el-option label="启用" :value="true" />
              <el-option label="停用" :value="false" />
            </el-select>
            <el-button type="primary" :icon="Search" @click="handleSystemConfigSearch">查询</el-button>
            <el-button :icon="Refresh" @click="resetSystemConfigSearch">重置</el-button>
          </div>

          <div class="table-panel">
            <el-table
              :data="configSystems"
              v-loading="systemsLoading"
              stripe
              height="100%"
              table-layout="fixed"
              style="width: 100%"
              :header-cell-style="{ whiteSpace: 'nowrap' }"
            >
              <template #empty>
                <GlobalEmpty text="暂无数据" />
              </template>
              <el-table-column prop="name" label="系统名称" min-width="150" show-overflow-tooltip />
              <el-table-column prop="app_count" label="应用数" width="90" align="center" />
              <el-table-column prop="is_active" label="状态" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain">
                    {{ row.is_active ? '启用' : '停用' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="sort_order" label="排序" width="90" align="center" />
              <el-table-column prop="creator_name" label="创建人" width="120" show-overflow-tooltip />
              <el-table-column prop="updated_at" label="更新时间" width="160">
                <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="150" fixed="right" align="center">
                <template #default="{ row }">
                  <div v-if="canManageSystems" class="operation-actions">
                    <el-button link type="primary" size="small" :icon="EditPen" @click="handleEditSystem(row)">编辑</el-button>
                    <el-button
                      link
                      type="danger"
                      size="small"
                      :icon="Delete"
                      @click="handleDeleteSystem(row)"
                    >
                      删除
                    </el-button>
                  </div>
                  <span v-else class="empty-cell">-</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <el-pagination
            class="navigation-pagination"
            background
            layout="total, sizes, prev, pager, next, jumper"
            :page-size="systemConfigPageSize"
            :current-page="systemConfigPage"
            :page-sizes="[10, 50, 100]"
            :total="systemConfigTotal"
            @size-change="handleSystemConfigSizeChange"
            @current-change="handleSystemConfigPageChange"
          />
        </template>

        <template v-else>
          <el-form :inline="true" class="search-form" @submit.prevent>
            <div class="filter-group">
              <el-form-item label="应用名称">
                <el-input
                  v-model="searchName"
                  placeholder="模糊搜索"
                  clearable
                  style="width: 220px"
                  @keyup.enter="handleSearch"
                />
              </el-form-item>
              <el-form-item label="创建人">
                <el-select
                  v-model="searchCreatedBy"
                  placeholder="全部"
                  clearable
                  filterable
                  style="width: 180px"
                  @visible-change="handleCreatorDropdownVisible"
                >
                  <el-option
                    v-for="user in creatorOptions"
                    :key="user.id"
                    :label="user.real_name"
                    :value="user.id"
                  />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
                <el-button :icon="Refresh" @click="resetSearch">重置</el-button>
              </el-form-item>
            </div>
            <div class="toolbar-actions">
              <el-button
                :icon="FolderOpened"
                :disabled="!hasSelectedApps"
                :loading="batchOperationLoading"
                @click="openBatchMove"
              >
                {{ selectedCount ? `批量移动（${selectedCount}）` : '批量移动' }}
              </el-button>
              <el-button
                type="danger"
                plain
                :icon="Delete"
                :disabled="!hasSelectedApps"
                :loading="batchOperationLoading"
                @click="handleBatchDelete"
              >
                {{ selectedCount ? `批量删除（${selectedCount}）` : '批量删除' }}
              </el-button>
              <el-button class="create-button" type="primary" :icon="Plus" @click="handleCreate">新增应用</el-button>
            </div>
          </el-form>

          <div class="table-panel">
            <el-table
              ref="appTableRef"
              :data="list"
              v-loading="loading"
              stripe
              height="100%"
              table-layout="fixed"
              style="width: 100%"
              :header-cell-style="{ whiteSpace: 'nowrap' }"
              :default-sort="{ prop: 'updated_at', order: 'descending' }"
              @selection-change="handleSelectionChange"
              @sort-change="handleSortChange"
            >
              <template #empty>
                <GlobalEmpty
                  :text="initialLoadFailed ? '加载失败，请重新加载' : '暂无数据'"
                  :action-text="initialLoadFailed ? '重新加载' : ''"
                  @action="loadInitialNavigationData"
                />
              </template>
              <el-table-column type="selection" width="44" :selectable="canSelectRow" />
              <el-table-column prop="app_name" label="应用名称" width="150" show-overflow-tooltip>
                <template #default="{ row }">
                  <el-link v-if="canModify(row)" class="app-name-link" type="primary" underline="never" @click="handleEdit(row)">
                    {{ row.app_name }}
                  </el-link>
                  <span v-else class="app-name-text">{{ row.app_name }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="system_name" label="所属系统" width="120" show-overflow-tooltip />
              <el-table-column label="入口" min-width="280" header-align="left" class-name="entry-column">
                <template #default="{ row }">
                  <div class="entry-cell" v-if="row.links?.length">
                    <button
                      v-for="(link, idx) in row.links"
                      :key="idx"
                      class="entry-pill"
                      :title="link.name"
                      @click="openLink(link.url)"
                    >
                      {{ link.name }}
                    </button>
                  </div>
                  <span v-else class="empty-cell">--</span>
                </template>
              </el-table-column>
              <el-table-column prop="creator_name" label="创建人" width="120" show-overflow-tooltip />
              <el-table-column prop="updated_at" label="更新时间" width="160" sortable="custom">
                <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="132" fixed="right" align="center">
                <template #default="{ row }">
                  <div v-if="canModify(row)" class="operation-actions">
                    <el-button link type="primary" size="small" :icon="EditPen" @click="handleEdit(row)">编辑</el-button>
                    <el-button link type="danger" size="small" :icon="Delete" @click="handleDelete(row)">删除</el-button>
                  </div>
                  <span v-if="!canModify(row)" class="empty-cell">-</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <el-pagination
            class="navigation-pagination"
            background
            layout="total, sizes, prev, pager, next, jumper"
            :page-size="pageSize"
            :current-page="page"
            :page-sizes="[10, 50, 100]"
            :total="total"
            @size-change="handleSizeChange"
            @current-change="handlePageChange"
          />
        </template>
      </main>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="min(980px, calc(100vw - 48px))" class="navigation-dialog" :close-on-click-modal="false" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="所属系统" prop="system_id">
          <el-select v-model="form.system_id" placeholder="请选择所属系统" filterable style="width: 100%" @change="handleFormSystemChange">
            <el-option
              v-for="system in activeSystems"
              :key="system.id"
              :label="system.name"
              :value="system.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="应用名称" prop="app_name">
          <el-input v-model="form.app_name" maxlength="10" show-word-limit placeholder="请输入应用名称" />
        </el-form-item>
        <div class="entry-list">
          <div v-for="(link, index) in formLinks" :key="link._key" class="entry-row">
            <div class="entry-index">入口 {{ index + 1 }}</div>
            <el-input v-model="link.name" placeholder="入口名称" maxlength="8" show-word-limit />
            <el-input v-model="link.url" placeholder="访问地址，如 https://example.com" />
            <el-input v-model="link.remark" placeholder="备注（可选）" maxlength="20" show-word-limit />
            <el-button
              class="entry-delete-btn"
              type="danger"
              :icon="Delete"
              circle
              size="small"
              :disabled="formLinks.length <= 1"
              title="删除此入口"
              @click="removeLink(index)"
            />
          </div>
          <div v-if="formLinks.length < 6" class="entry-add-row">
            <el-button type="primary" :icon="Plus" plain @click="addLink">添加入口</el-button>
            <span class="entry-hint">最多 6 个入口，当前 {{ formLinks.length }} 个</span>
          </div>
        </div>
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchMoveDialogVisible" title="批量移动应用" width="520px" class="navigation-dialog" :close-on-click-modal="false" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="已选择">
          <span class="batch-count-text">
            {{ selectedCount }} 个应用
            <template v-if="selectedSystemIds.length > 1">，来自 {{ selectedSystemIds.length }} 个系统</template>
          </span>
        </el-form-item>
        <el-form-item label="目标系统" required>
          <el-select v-model="batchMoveSystemId" placeholder="请选择目标系统" filterable style="width: 100%">
            <el-option
              v-for="system in activeSystems"
              :key="system.id"
              :label="getBatchSystemOptionLabel(system)"
              :value="system.id"
            >
              <div class="batch-system-option">
                <span class="batch-system-name">{{ system.name }}</span>
                <el-tag v-if="isSelectedCurrentSystem(system.id)" size="small" effect="plain">当前</el-tag>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchMoveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchOperationLoading" @click="handleBatchMove">确定移动</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="systemDialogVisible" :title="systemDialogTitle" width="520px" class="navigation-dialog" :close-on-click-modal="false" destroy-on-close>
      <el-form ref="systemFormRef" :model="systemForm" :rules="systemRules" label-width="90px">
        <el-form-item label="系统名称" prop="name">
          <el-input v-model="systemForm.name" maxlength="10" show-word-limit placeholder="请输入系统名称" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="systemForm.sort_order" :min="0" :max="9999" controls-position="right" />
          <span class="sort-hint">数字越大越靠前</span>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="systemForm.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="systemDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="systemSubmitLoading" @click="handleSubmitSystem">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onActivated, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, EditPen, FolderOpened, Plus, Refresh, Search, Setting } from '@element-plus/icons-vue'
import { formatBeijingMinute } from '@/utils/beijingTime'
import {
  batchDeleteNavigationApps,
  batchMoveNavigationApps,
  createNavigationApp,
  createNavigationSystem,
  deleteNavigationApp,
  deleteNavigationSystem,
  getNavigationApps,
  getNavigationCreators,
  getNavigationSystems,
  updateNavigationApp,
  updateNavigationSystem,
} from '@/api/navigation'
import { useUserStore } from '@/stores/user'
import GlobalEmpty from '@/components/GlobalEmpty.vue'

defineOptions({ name: 'NavigationApps' })

const userStore = useUserStore()
const loading = ref(false)
// 本页被 KeepAlive 缓存，进入页面的自动加载只会执行一次；这里记住它有没有成功，
// 失败时再次进入页面能自动重试，列表区也能明确区分「加载失败」和「确实没有数据」
const initialLoadFailed = ref(false)
const systemsLoading = ref(false)
const systemNavLoading = ref(false)
const submitLoading = ref(false)
const systemSubmitLoading = ref(false)
const batchOperationLoading = ref(false)
const list = ref([])
const systems = ref([])
const systemOptions = ref([])
const configSystems = ref([])
const creatorOptions = ref([])
const creatorsLoaded = ref(false)
let creatorsLoadingPromise = null
const selectedRows = ref([])
const searchName = ref('')
const searchCreatedBy = ref(null)
const systemKeyword = ref('')
const systemConfigKeyword = ref('')
const systemConfigStatus = ref(null)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const systemPage = ref(1)
const systemPageSize = ref(10)
const systemTotal = ref(0)
const systemConfigPage = ref(1)
const systemConfigPageSize = ref(10)
const systemConfigTotal = ref(0)
const sortOrder = ref('desc')
const activeView = ref('apps')
const selectedSystemId = ref(null)
const dialogVisible = ref(false)
const systemDialogVisible = ref(false)
const batchMoveDialogVisible = ref(false)
const dialogTitle = ref('新增应用')
const systemDialogTitle = ref('新增系统')
const batchMoveSystemId = ref(null)
const appTableRef = ref(null)
const formRef = ref(null)
const systemFormRef = ref(null)

let linkKeyCounter = 0
const emptyLink = () => ({ _key: linkKeyCounter++, name: '', url: '', remark: '' })
const formLinks = ref([emptyLink()])

const form = reactive({
  id: null,
  system_id: null,
  app_name: '',
  description: '',
})

const systemForm = reactive({
  id: null,
  name: '',
  sort_order: 0,
  is_active: true,
})

const currentUser = computed(() => userStore.userInfo || {})
const canManageSystems = computed(() => Boolean(currentUser.value.is_superuser || currentUser.value.is_manager))
const activeSystems = computed(() => systemOptions.value.filter(system => system.is_active))
const visibleSystems = computed(() => systems.value)
const allAppCount = computed(() => activeSystems.value.reduce((count, system) => count + (system.app_count || 0), 0))
const selectedSystem = computed(() => systemOptions.value.find(system => system.id === selectedSystemId.value))
const hasSelectedApps = computed(() => selectedRows.value.length > 0)
const selectedCount = computed(() => selectedRows.value.length)
const selectedSystemIds = computed(() => {
  const ids = selectedRows.value
    .map(row => row.system_id)
    .filter(id => id !== null && id !== undefined)
  return Array.from(new Set(ids))
})

function addLink() {
  if (formLinks.value.length >= 6) return
  formLinks.value.push(emptyLink())
}

function removeLink(index) {
  if (formLinks.value.length <= 1) return
  formLinks.value.splice(index, 1)
}

const validateUniqueAppName = async (_rule, value, callback) => {
  const appName = (value || '').trim()
  if (!appName) {
    callback()
    return
  }
  if (!form.system_id) {
    callback()
    return
  }
  try {
    const res = await getNavigationApps({
      app_name: appName,
      system_id: form.system_id,
      skip: 0,
      limit: 10,
      sort_order: 'desc',
    })
    const duplicated = (res?.items || []).some(item => item.app_name === appName && item.id !== form.id)
    if (duplicated) callback(new Error('当前系统下应用名称已存在，不能重复'))
    else callback()
  } catch {
    callback()
  }
}

const validateUniqueSystemName = async (_rule, value, callback) => {
  const name = (value || '').trim()
  if (!name) {
    callback()
    return
  }
  try {
    const res = await getNavigationSystems({ keyword: name })
    const duplicated = (res || []).some(item => item.name === name && item.id !== systemForm.id)
    if (duplicated) callback(new Error('系统名称已存在，不能重复'))
    else callback()
  } catch {
    callback()
  }
}

const rules = {
  system_id: [{ required: true, message: '请选择所属系统', trigger: 'change' }],
  app_name: [
    { required: true, message: '请输入应用名称', trigger: 'blur' },
    { validator: validateUniqueAppName, trigger: 'blur' },
  ],
}

const systemRules = {
  name: [
    { required: true, message: '请输入系统名称', trigger: 'blur' },
    { validator: validateUniqueSystemName, trigger: 'blur' },
  ],
}

const canModify = (row) => {
  const user = currentUser.value
  return Boolean(user.is_superuser || user.is_manager || row.created_by === user.id)
}
const canSelectRow = (row) => canModify(row)
const selectedAppIds = () => selectedRows.value.map(row => row.id)
const isSelectedCurrentSystem = (systemId) => selectedSystemIds.value.includes(systemId)
const getBatchSystemOptionLabel = (system) => `${system.name}${isSelectedCurrentSystem(system.id) ? '（当前）' : ''}`
const handleFormSystemChange = () => {
  if (form.app_name) formRef.value?.validateField?.('app_name')
}
const clearSelectedRows = () => {
  selectedRows.value = []
  appTableRef.value?.clearSelection?.()
}
const handleSelectionChange = (rows) => {
  selectedRows.value = rows
}

const normalizeForForm = (links = []) => {
  if (!links || !links.length) return [emptyLink()]
  return links.map(link => ({ _key: linkKeyCounter++, name: link.name || '', url: link.url || '', remark: link.remark || '' }))
}

const buildPayloadLinks = () => formLinks.value
  .map(link => ({ name: (link.name || '').trim(), url: (link.url || '').trim(), remark: (link.remark || '').trim() }))
  .filter(link => link.name || link.url)

const validateLinks = () => {
  let validCount = 0
  for (const link of formLinks.value) {
    const hasName = Boolean((link.name || '').trim())
    const hasUrl = Boolean((link.url || '').trim())
    if (hasName !== hasUrl) {
      ElMessage.warning('入口名称和访问地址必须同时填写')
      return false
    }
    if (hasName && hasUrl) validCount += 1
  }
  if (validCount === 0) {
    ElMessage.warning('至少填写 1 个入口')
    return false
  }
  return true
}

const loadSystems = async () => {
  systemNavLoading.value = true
  try {
    const params = {
      paged: true,
      active_only: true,
      skip: (systemPage.value - 1) * systemPageSize.value,
      limit: systemPageSize.value,
    }
    if (systemKeyword.value.trim()) params.keyword = systemKeyword.value.trim()
    const res = await getNavigationSystems(params)
    systems.value = res?.items || []
    systemTotal.value = res?.total || 0
    initialLoadFailed.value = false
    if (!systems.value.length && systemTotal.value > 0 && systemPage.value > 1) {
      systemPage.value -= 1
      await loadSystems()
      return
    }
    if (selectedSystemId.value && !systemOptions.value.some(system => system.id === selectedSystemId.value && system.is_active)) {
      selectedSystemId.value = null
    }
  } catch {
    systems.value = []
    systemTotal.value = 0
  } finally {
    systemNavLoading.value = false
  }
}

const loadConfigSystems = async () => {
  systemsLoading.value = true
  try {
    const params = {
      paged: true,
      skip: (systemConfigPage.value - 1) * systemConfigPageSize.value,
      limit: systemConfigPageSize.value,
    }
    if (systemConfigKeyword.value.trim()) params.keyword = systemConfigKeyword.value.trim()
    if (systemConfigStatus.value !== null) params.is_active = systemConfigStatus.value
    const res = await getNavigationSystems(params)
    configSystems.value = res?.items || []
    systemConfigTotal.value = res?.total || 0
    if (!configSystems.value.length && systemConfigTotal.value > 0 && systemConfigPage.value > 1) {
      systemConfigPage.value -= 1
      await loadConfigSystems()
    }
  } catch {
    configSystems.value = []
    systemConfigTotal.value = 0
  } finally {
    systemsLoading.value = false
  }
}

const loadSystemOptions = async () => {
  try {
    systemOptions.value = await getNavigationSystems() || []
    if (selectedSystemId.value && !systemOptions.value.some(system => system.id === selectedSystemId.value && system.is_active)) {
      selectedSystemId.value = null
    }
  } catch {
    systemOptions.value = []
  }
}

const loadCreators = async () => {
  if (creatorsLoaded.value) return
  if (creatorsLoadingPromise) return creatorsLoadingPromise
  creatorsLoadingPromise = getNavigationCreators()
    .then((data) => {
      creatorOptions.value = data || []
      creatorsLoaded.value = true
    })
    .catch(() => {
      creatorOptions.value = []
    })
    .finally(() => {
      creatorsLoadingPromise = null
    })
  return creatorsLoadingPromise
}

const handleCreatorDropdownVisible = (visible) => {
  if (visible) loadCreators()
}

const loadList = async () => {
  loading.value = true
  try {
    const params = {
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
      sort_order: sortOrder.value,
    }
    if (selectedSystemId.value) params.system_id = selectedSystemId.value
    if (searchName.value.trim()) params.app_name = searchName.value.trim()
    if (searchCreatedBy.value) params.created_by = searchCreatedBy.value
    const res = await getNavigationApps(params)
    list.value = res?.items || []
    total.value = res?.total || 0
    initialLoadFailed.value = false
    clearSelectedRows()
  } catch {
    list.value = []
    total.value = 0
    clearSelectedRows()
  } finally {
    loading.value = false
  }
}

const refreshAppsAndSystems = async () => {
  await loadSystemOptions()
  await Promise.all([loadList(), loadSystems(), loadConfigSystems()])
}

const refreshNavigationData = async () => {
  await loadSystemOptions()
  await Promise.all([loadList(), loadSystems(), loadConfigSystems()])
}

const loadInitialNavigationData = async () => {
  loading.value = true
  systemNavLoading.value = true
  initialLoadFailed.value = false
  const appParams = {
    skip: 0,
    limit: pageSize.value,
    sort_order: sortOrder.value,
  }
  const systemParams = {
    paged: true,
    active_only: true,
    skip: 0,
    limit: systemPageSize.value,
  }

  const [systemOptionsResult, appListResult, systemsResult] = await Promise.allSettled([
    getNavigationSystems(),
    getNavigationApps(appParams),
    getNavigationSystems(systemParams),
  ])

  if (systemOptionsResult.status === 'fulfilled') {
    const data = systemOptionsResult.value
    systemOptions.value = Array.isArray(data) ? data : (data?.items || [])
  } else {
    systemOptions.value = []
  }

  if (appListResult.status === 'fulfilled') {
    list.value = appListResult.value?.items || []
    total.value = appListResult.value?.total || 0
  } else {
    list.value = []
    total.value = 0
  }
  clearSelectedRows()

  if (systemsResult.status === 'fulfilled') {
    systems.value = systemsResult.value?.items || []
    systemTotal.value = systemsResult.value?.total || 0
  } else {
    systems.value = []
    systemTotal.value = 0
  }

  // 任一请求失败都算加载失败：失败后再次进入页面会自动重试，不再需要手动点查询
  initialLoadFailed.value = [systemOptionsResult, appListResult, systemsResult]
    .some(result => result.status === 'rejected')
  loading.value = false
  systemNavLoading.value = false
}

const selectAllSystems = () => {
  activeView.value = 'apps'
  selectedSystemId.value = null
  page.value = 1
  loadList()
}

const selectSystem = (system) => {
  activeView.value = 'apps'
  selectedSystemId.value = system.id
  page.value = 1
  loadList()
}

const openSystemConfig = () => {
  activeView.value = 'systems'
  loadConfigSystems()
}

const handleSystemSearch = () => {
  systemPage.value = 1
  loadSystems()
}

const resetSystemSearch = () => {
  systemKeyword.value = ''
  systemPage.value = 1
  loadSystems()
}

const handleSystemSizeChange = (size) => {
  systemPageSize.value = size
  systemPage.value = 1
  loadSystems()
}

const handleSystemPageChange = (value) => {
  systemPage.value = value
  loadSystems()
}

const handleSearch = () => {
  page.value = 1
  loadList()
}

const resetSearch = () => {
  searchName.value = ''
  searchCreatedBy.value = null
  page.value = 1
  loadList()
}

const handleSystemConfigSearch = () => {
  activeView.value = 'systems'
  systemConfigPage.value = 1
  loadConfigSystems()
}

const resetSystemConfigSearch = () => {
  systemConfigKeyword.value = ''
  systemConfigStatus.value = null
  systemConfigPage.value = 1
  loadConfigSystems()
}

const handleSystemConfigSizeChange = (size) => {
  systemConfigPageSize.value = size
  systemConfigPage.value = 1
  loadConfigSystems()
}

const handleSystemConfigPageChange = (value) => {
  systemConfigPage.value = value
  loadConfigSystems()
}

const handleSizeChange = (size) => {
  pageSize.value = size
  page.value = 1
  loadList()
}

const handlePageChange = (value) => {
  page.value = value
  loadList()
}

const handleSortChange = ({ prop, order }) => {
  if (prop !== 'updated_at') return
  sortOrder.value = order === 'ascending' ? 'asc' : 'desc'
  page.value = 1
  loadList()
}

const resetForm = () => {
  form.id = null
  form.system_id = selectedSystemId.value || activeSystems.value[0]?.id || null
  form.app_name = ''
  form.description = ''
  formLinks.value = [{ _key: linkKeyCounter++, name: '', url: '' }]
}

const resetSystemForm = () => {
  systemForm.id = null
  systemForm.name = ''
  systemForm.sort_order = 0
  systemForm.is_active = true
}

const handleCreate = () => {
  resetForm()
  dialogTitle.value = '新增应用'
  dialogVisible.value = true
}

const handleEdit = (row) => {
  resetForm()
  form.id = row.id
  form.system_id = row.system_id || selectedSystemId.value || activeSystems.value[0]?.id || null
  form.app_name = row.app_name || ''
  form.description = row.description || ''
  formLinks.value = normalizeForForm(row.links || [])
  dialogTitle.value = '编辑应用'
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  if (!validateLinks()) return

  submitLoading.value = true
  try {
    const payload = {
      system_id: form.system_id,
      app_name: form.app_name.trim(),
      links: buildPayloadLinks(),
      description: form.description?.trim() || null,
    }
    if (form.id) await updateNavigationApp(form.id, payload)
    else await createNavigationApp(payload)
    dialogVisible.value = false
    await refreshNavigationData()
  } catch {
    // handled by request interceptor
  } finally {
    submitLoading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除导航记录「${row.app_name}」？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  await deleteNavigationApp(row.id)
  if (list.value.length === 1 && page.value > 1) page.value -= 1
  await refreshNavigationData()
}

const openBatchMove = () => {
  if (!hasSelectedApps.value) return
  const currentSystemId = selectedSystemId.value || selectedRows.value[0]?.system_id || activeSystems.value[0]?.id || null
  batchMoveSystemId.value = currentSystemId
  batchMoveDialogVisible.value = true
}

const handleBatchMove = async () => {
  const appIds = selectedAppIds()
  if (!appIds.length) return
  if (!batchMoveSystemId.value) {
    ElMessage.warning('请选择目标系统')
    return
  }

  batchOperationLoading.value = true
  try {
    await batchMoveNavigationApps({ app_ids: appIds, system_id: batchMoveSystemId.value })
    batchMoveDialogVisible.value = false
    await refreshNavigationData()
  } catch {
    // handled by request interceptor
  } finally {
    batchOperationLoading.value = false
  }
}

const handleBatchDelete = async () => {
  const appIds = selectedAppIds()
  if (!appIds.length) return
  try {
    await ElMessageBox.confirm(`确认删除选中的 ${appIds.length} 个导航应用？删除后不可在列表中恢复。`, '批量删除确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  batchOperationLoading.value = true
  try {
    await batchDeleteNavigationApps({ app_ids: appIds })
    if (list.value.length === appIds.length && page.value > 1) page.value -= 1
    await refreshNavigationData()
  } catch {
    // handled by request interceptor
  } finally {
    batchOperationLoading.value = false
  }
}

const handleCreateSystem = () => {
  resetSystemForm()
  systemDialogTitle.value = '新增系统'
  systemDialogVisible.value = true
}

const handleEditSystem = (row) => {
  resetSystemForm()
  systemForm.id = row.id
  systemForm.name = row.name || ''
  systemForm.sort_order = row.sort_order || 0
  systemForm.is_active = Boolean(row.is_active)
  systemDialogTitle.value = '编辑系统'
  systemDialogVisible.value = true
}

const handleSubmitSystem = async () => {
  if (!systemFormRef.value) return
  try {
    await systemFormRef.value.validate()
  } catch {
    return
  }

  systemSubmitLoading.value = true
  try {
    const payload = {
      name: systemForm.name.trim(),
      sort_order: systemForm.sort_order || 0,
      is_active: systemForm.is_active,
    }
    if (systemForm.id) await updateNavigationSystem(systemForm.id, payload)
    else await createNavigationSystem(payload)
    systemDialogVisible.value = false
    await refreshAppsAndSystems()
  } catch {
    // handled by request interceptor
  } finally {
    systemSubmitLoading.value = false
  }
}

const handleDeleteSystem = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除系统「${row.name}」？删除前请确保该系统下没有导航应用。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  await deleteNavigationSystem(row.id)
  if (selectedSystemId.value === row.id) selectedSystemId.value = null
  if (configSystems.value.length === 1 && systemConfigPage.value > 1) systemConfigPage.value -= 1
  await refreshAppsAndSystems()
}

const openLink = (url) => {
  const target = /^https?:\/\//i.test(url) ? url : `http://${url}`
  window.open(target, '_blank', 'noopener,noreferrer')
}

const formatDate = (value) => value ? formatBeijingMinute(value) || '-' : '-'

onMounted(() => {
  loadInitialNavigationData()
})

// 首次挂载时 onActivated 紧随 onMounted 触发，此时请求还在进行、失败标记为假，不会重复请求；
// 只有上一次自动加载确实失败过，再次进入页面才重新加载
onActivated(() => {
  if (initialLoadFailed.value) loadInitialNavigationData()
})
</script>

<style scoped>
.navigation-apps {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 15px;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.page-header h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #1f2d3d;
}
.page-header p {
  margin: 6px 0 0;
  color: #7a869a;
  font-size: 14px;
}
.navigation-workspace {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 12px;
}
.system-sidebar {
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 10px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  background: #fafafa;
}
.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.sidebar-title {
  color: #595959;
  font-size: 13px;
  font-weight: 600;
}
.config-button {
  flex-shrink: 0;
  font-size: 14px;
}
.system-search {
  margin-bottom: 8px;
}
.system-search-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.system-search-actions :deep(.el-button) {
  flex: 1;
  margin-left: 0;
}
.system-nav-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 2px;
}
.system-pagination {
  flex: 0 0 auto;
  justify-content: center;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}
.system-pagination :deep(.el-pagination__total) {
  display: none;
}
.system-pagination :deep(.el-select__wrapper) {
  min-height: 24px;
}
.system-nav-error {
  padding: 10px 4px;
  color: #909399;
  font-size: 12px;
  text-align: center;
}
.system-nav-list::-webkit-scrollbar {
  width: 6px;
}
.system-nav-list::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 3px;
}
.system-nav-item {
  width: 100%;
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
  padding: 8px 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: #595959;
  font-size: 15px;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  transition: background .15s, color .15s;
}
.system-nav-item:hover {
  background: #f0f0f0;
  color: #1a1a1a;
}
.system-nav-item.active {
  background: #e6f4ff;
  border-color: transparent;
  color: #1677ff;
  font-weight: 600;
}
.system-nav-item.disabled {
  color: #98a2b3;
}
.system-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.system-meta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.system-state {
  color: #98a2b3;
  font-size: 12px;
}
.system-count {
  min-width: 24px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
  border-radius: 999px;
  background: #eef2f7;
  color: #667085;
  font-size: 12px;
}
.content-panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.content-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.content-title-row h3 {
  margin: 0;
  color: #1f2d3d;
  font-size: 18px;
  font-weight: 500;
}
.content-title-row p {
  margin: 4px 0 0;
  color: #7a869a;
  font-size: 13px;
}
.search-form,
.system-config-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 12px;
  padding: 12px 14px;
  background: #f8fbff;
  border: 1px solid #e8f1ff;
  border-radius: 8px;
}
.system-config-toolbar {
  justify-content: flex-start;
}
.filter-group {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px 18px;
}
.search-form :deep(.el-form-item) {
  margin-right: 0;
  margin-bottom: 0;
}
.search-form :deep(.el-form-item__label),
.search-form :deep(.el-input__inner),
.search-form :deep(.el-select__placeholder),
.search-form :deep(.el-button),
.system-config-toolbar :deep(.el-input__inner),
.system-config-toolbar :deep(.el-button) {
  font-size: 15px;
}
.create-button {
  flex-shrink: 0;
}
.toolbar-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
  flex-shrink: 0;
}
.toolbar-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
.table-panel {
  flex: 1;
  min-height: 300px;
  overflow: hidden;
  border: 1px solid #edf0f5;
  border-radius: 8px;
}
.table-panel :deep(.el-table__header th) {
  background: #fbfcfe;
  color: #27364a;
  font-weight: 500;
  font-size: 15px;
}
.table-panel :deep(.el-table__row) {
  height: 54px;
}
.table-panel :deep(.el-table__body) {
  font-size: 15px;
}
.table-panel :deep(.el-table__cell) {
  border-bottom-color: #edf0f5;
}
.table-panel :deep(.entry-column .cell) {
  padding-left: 8px;
  padding-right: 8px;
}
.table-panel :deep(.el-table__body tr:hover > td.el-table__cell) {
  background: #f6faff;
}
.table-panel :deep(.el-scrollbar__bar.is-vertical) {
  width: 12px;
  right: 2px;
}
.table-panel :deep(.el-scrollbar__bar.is-horizontal) {
  height: 12px;
  bottom: 2px;
}
.table-panel :deep(.el-scrollbar__thumb) {
  background-color: rgba(144, 147, 153, 0.45);
  border-radius: 8px;
}
.table-panel :deep(.el-scrollbar__thumb:hover) {
  background-color: rgba(144, 147, 153, 0.7);
}
.table-panel :deep(.el-table__body-wrapper::-webkit-scrollbar) {
  width: 12px;
  height: 12px;
}
.table-panel :deep(.el-table__body-wrapper::-webkit-scrollbar-thumb) {
  background-color: rgba(144, 147, 153, 0.45);
  border-radius: 8px;
}
.navigation-pagination {
  flex: 0 0 auto;
  justify-content: center;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #edf0f5;
}
.navigation-pagination :deep(.el-pagination__total),
.navigation-pagination :deep(.el-pagination__jump),
.navigation-pagination :deep(.el-select__wrapper),
.navigation-pagination :deep(.el-pager li) {
  font-size: 15px;
}
.app-name-link,
.app-name-text {
  font-size: 15px;
  font-weight: 400;
  color: #2f7bff;
  line-height: 22px;
}
.app-name-link {
  color: #2f7bff;
}
.app-name-link:hover {
  color: #1677ff;
}
.entry-cell {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 4px 8px;
  min-width: 0;
  padding: 2px 0 4px;
  overflow-x: auto;
  scrollbar-width: thin;
}
.entry-cell::-webkit-scrollbar {
  height: 8px;
}
.entry-cell::-webkit-scrollbar-thumb {
  background-color: rgba(144, 147, 153, 0.36);
  border-radius: 8px;
}
.entry-pill {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  max-width: 132px;
  min-width: 44px;
  height: 30px;
  padding: 0 14px;
  border: 1px solid #d7e8ff;
  border-radius: 999px;
  background: #f1f7ff;
  color: #2f7bff;
  font-size: 15px;
  font-weight: 400;
  line-height: 28px;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  box-shadow: 0 1px 3px rgba(50, 104, 175, .08);
  transition: background .18s ease, border-color .18s ease, box-shadow .18s ease, color .18s ease;
}
.entry-pill:hover {
  background: #e8f3ff;
  border-color: #a7cdfc;
  box-shadow: 0 2px 7px rgba(50, 104, 175, .14);
  color: #1677ff;
}
.entry-pill:active {
  background: #ddeeff;
  box-shadow: 0 1px 2px rgba(50, 104, 175, .12) inset;
}
.empty-cell {
  color: #d2d8e3;
  font-size: 14px;
}
.empty-state {
  padding: 44px 0;
  color: #8c8c8c;
}
.empty-title {
  color: #3d4b5f;
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 6px;
}
.empty-desc {
  font-size: 13px;
}
.operation-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  white-space: nowrap;
}
.operation-actions :deep(.el-button) {
  font-size: 14px;
}
.operation-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
.table-panel { min-width: 0; overflow: hidden; }
.table-panel :deep(.el-table) { width: 100%; }
.entry-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 18px;
}
.entry-row {
  display: grid;
  grid-template-columns: 76px minmax(200px, 240px) minmax(300px, 1fr) minmax(140px, 200px) 36px;
  gap: 12px;
  align-items: center;
}
.entry-delete-btn {
  flex-shrink: 0;
}
.entry-add-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 4px;
}
.entry-hint {
  color: #909399;
  font-size: 13px;
}
.sort-hint {
  margin-left: 10px;
  color: #8a94a6;
  font-size: 13px;
}
.entry-index {
  color: #606266;
  font-size: 14px;
  text-align: right;
}
.navigation-dialog :deep(.el-dialog__body) {
  padding-top: 18px;
}
.navigation-dialog :deep(.el-dialog) { display: flex; flex-direction: column; max-height: calc(100vh - 48px); }
.navigation-dialog :deep(.el-dialog__body) { min-height: 0; overflow-y: auto; }
.batch-count-text {
  color: #3d4b5f;
  font-size: 15px;
}
.batch-system-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}
.batch-system-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (max-width: 980px) {
  .navigation-workspace {
    grid-template-columns: 1fr;
  }
  .system-sidebar {
    max-height: 240px;
  }
}
@media (max-width: 1440px) {
  .navigation-workspace { grid-template-columns: 220px minmax(0, 1fr); }
  .system-config-toolbar,
  .search-form,
  .toolbar-actions { flex-wrap: wrap; }
}
@media (max-width: 768px) {
  .page-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }
  .search-form,
  .system-config-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .create-button {
    width: 100%;
  }
  .toolbar-actions {
    width: 100%;
    justify-content: flex-start;
  }
  .entry-row {
    grid-template-columns: 1fr 28px;
    gap: 8px;
  }
  .entry-index {
    text-align: left;
  }
}
</style>
