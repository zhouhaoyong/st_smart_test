<template>
  <div class="layout">
    <!-- 统一顶部导航栏 -->
    <TopBar />

    <!-- 面包屑 -->
    <div class="breadcrumb-bar" v-if="breadcrumbs.length">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item v-for="(item, i) in breadcrumbs" :key="i" :to="i < breadcrumbs.length - 1 ? item.path : undefined">
          <span>{{ item.label }}</span>
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <!-- 主体区域 -->
    <div class="layout-body">
      <aside class="sidebar" v-if="isProjectPage">
        <nav class="sidebar-nav">
          <div class="nav-group">
            <template v-for="item in navItems" :key="item.path">
              <router-link :to="`/project/${projectId}${item.path}`" class="nav-item" :class="{ active: isActive(item.path) }">
                <el-icon :size="22"><component :is="item.icon" /></el-icon>
                <span>{{ item.label }}</span>
              </router-link>
            </template>
          </div>
        </nav>
        <div class="sidebar-env">
          <section class="project-config-card" aria-label="API测试运行配置">
            <div class="project-config-card__header">
              <span class="project-config-card__title">运行配置</span>
              <el-button link type="primary" @click="openProjectConfig">编辑</el-button>
            </div>
            <button class="project-config-card__value" type="button" @click="openProjectConfig">
              <span>环境</span>
              <el-tooltip :content="selectedEnvironment?.name || '未选择环境'" :disabled="!selectedEnvironment?.name" placement="top" :show-after="300">
                <strong>{{ selectedEnvironment?.name || '未选择' }}</strong>
              </el-tooltip>
            </button>
            <button class="project-config-card__value" type="button" @click="openProjectConfig">
              <span>参数集</span>
              <el-tooltip :content="selectedParameterSet?.name || '未选择参数集'" :disabled="!selectedParameterSet?.name" placement="top" :show-after="300">
                <strong>{{ selectedParameterSet?.name || '未选择' }}</strong>
              </el-tooltip>
            </button>
          </section>
        </div>
      </aside>

      <!-- 管理中心侧边栏 -->
      <aside class="sidebar admin-sidebar" v-if="isAdminPage">
        <nav class="sidebar-nav">
          <div class="nav-group">
            <router-link to="/profile" class="nav-item" :class="{ active: route.path === '/profile' || route.path === '/' }">
              <el-icon :size="20"><User /></el-icon>
              <span>个人中心</span>
            </router-link>
            <router-link v-if="isSuperAdmin" to="/users" class="nav-item" :class="{ active: route.path.startsWith('/users') }">
              <el-icon :size="20"><List /></el-icon>
              <span>平台用户管理</span>
            </router-link>
            <router-link to="/model-admin/models" class="nav-item" :class="{ active: route.path.startsWith('/model-admin/models') }">
              <el-icon :size="20"><DataAnalysis /></el-icon>
              <span>AI模型配置</span>
            </router-link>
            <router-link to="/model-admin/usage" class="nav-item" :class="{ active: route.path.startsWith('/model-admin/usage') }">
              <el-icon :size="20"><DataAnalysis /></el-icon>
              <span>AI用量统计</span>
            </router-link>
            <router-link v-if="isManager" to="/config-admin/channels" class="nav-item" :class="{ active: route.path === '/config-admin/channels' }">
              <el-icon :size="20"><Document /></el-icon>
              <span>消息渠道管理</span>
            </router-link>
            <router-link v-if="isManager" to="/config-admin/templates" class="nav-item" :class="{ active: route.path === '/config-admin/templates' }">
              <el-icon :size="20"><Document /></el-icon>
              <span>消息模板管理</span>
            </router-link>
            <router-link v-if="isManager" to="/config-admin/policies" class="nav-item" :class="{ active: route.path === '/config-admin/policies' }">
              <el-icon :size="20"><Document /></el-icon>
              <span>执行策略管理</span>
            </router-link>
            <router-link to="/feedback" class="nav-item" :class="{ active: route.path === '/feedback' }">
              <el-icon :size="20"><Link /></el-icon>
              <span>问题反馈</span>
            </router-link>
            <router-link v-if="isSuperAdmin" to="/data-admin/audit" class="nav-item" :class="{ active: route.path === '/data-admin/audit' }">
              <el-icon :size="20"><Timer /></el-icon>
              <span>审计日志管理</span>
            </router-link>
            <router-link v-if="isSuperAdmin" to="/data-admin/cleanup" class="nav-item" :class="{ active: route.path === '/data-admin/cleanup' }">
              <el-icon :size="20"><Timer /></el-icon>
              <span>平台数据管理</span>
            </router-link>
          </div>
        </nav>
      </aside>

      <main class="main" :class="{ 'has-sidebar': isProjectPage || isAdminPage, 'is-admin-module': isAdminPage, 'fixed-content-page': isFixedContentPage }">
        <router-view v-slot="{ Component }">
          <KeepAlive include="Projects,TestWorkbenchProjects">
            <component :is="Component" />
          </KeepAlive>
        </router-view>
      </main>
    </div>

    <el-dialog v-if="isProjectPage" v-model="projectConfigDialogVisible" title="运行配置" width="520px" destroy-on-close class="project-config-dialog">
      <p class="project-config-dialog__hint">选择运行环境和参数集后，将用于接口调试、用例运行和执行集请求。</p>
      <div class="project-config-dialog__section">
        <div class="project-config-dialog__label">运行环境</div>
        <el-select v-model="draftEnvId" class="project-config-dialog__select" :loading="envsLoading" placeholder="请选择运行环境" no-data-text="暂无环境，请先创建">
          <el-option v-for="env in environments" :key="env.id" :label="env.name + ' (' + env.base_url + ')'" :value="env.id" />
        </el-select>
      </div>
      <div class="project-config-dialog__section">
        <div class="project-config-dialog__label">参数集</div>
        <el-select v-model="draftParamSetId" class="project-config-dialog__select" :loading="paramSetsLoading" placeholder="请选择参数集" no-data-text="暂无参数集，请先创建" clearable>
          <el-option v-for="ps in paramSets" :key="ps.id" :label="ps.name" :value="ps.id" />
        </el-select>
      </div>
      <template #footer>
        <el-button @click="projectConfigDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveProjectConfig">保存配置</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, provide } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { getProject } from '@/api/project'
import { getEnvironments } from '@/api/environment'
import { getParameterSets } from '@/api/parameterSet'
import TopBar from '@/layout/TopBar.vue'
import { Link, Document, DataAnalysis, List, Timer, User } from '@element-plus/icons-vue'
import { isAdmin as hasAdminRole } from '@/utils/permission'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const projectName = ref('')
const projectId = computed(() => route.params.id)
const isProjectPage = computed(() => /^\/project\/\d+/.test(route.path))
const isFixedContentPage = computed(() => ['Environments', 'Interfaces', 'InterfaceCases', 'ParameterSetDetail'].includes(route.name))
const isToolModule = computed(() => route.path.startsWith('/tools/') && !route.path.includes('/navigation'))
const isNavModule = computed(() => route.path.startsWith('/tools/navigation'))
const adminPageNames = new Set(['Profile', 'Users', 'DataAdminAudit', 'DataAdminCleanup', 'ModelAdminModels', 'ModelAdminModelsMine', 'ModelAdminModelsPlatform', 'ModelAdminModelsUsers', 'ModelAdminUsage', 'ModelAdminUsageOverview', 'ModelAdminUsageRecords', 'ConfigAdminChannels', 'ConfigAdminTemplates', 'ConfigAdminPolicies', 'Feedback', 'UserUsageDetail'])
const isAdminPage = computed(() => adminPageNames.has(route.name))
const isSuperAdmin = computed(() => userStore.userInfo?.is_superuser)
const isManager = computed(() => hasAdminRole(userStore.userInfo))

const environments = ref([])
const envsLoading = ref(false)
const selectedEnvId = ref(null)
const projectConfigDialogVisible = ref(false)
const draftEnvId = ref(null)

const getEnvCacheKey = () => `selected_env_${projectId.value}`

const loadEnvironments = async () => {
  if (!projectId.value) return
  envsLoading.value = true
  try {
    const res = await getEnvironments(projectId.value)
    environments.value = Array.isArray(res) ? res : (res?.items || [])
    const cached = localStorage.getItem(getEnvCacheKey())
    if (cached && environments.value.find(e => e.id === parseInt(cached))) {
      selectedEnvId.value = parseInt(cached)
    } else {
      selectedEnvId.value = environments.value[0]?.id || null
    }
  } catch { environments.value = [] }
  finally { envsLoading.value = false }
}

const selectedEnvironment = computed(() => environments.value.find(e => e.id === selectedEnvId.value) || null)
provide('selectedEnvironment', selectedEnvironment)
provide('refreshEnvironments', loadEnvironments)

// 参数集选择器
const paramSets = ref([])
const paramSetsLoading = ref(false)
const selectedParamSetId = ref(null)
const draftParamSetId = ref(null)

const loadParameterSets = async () => {
  if (!projectId.value) return
  paramSetsLoading.value = true
  try {
    const res = await getParameterSets(projectId.value)
    paramSets.value = Array.isArray(res) ? res : (res?.items || [])
    const cached = localStorage.getItem(`selected_param_set_${projectId.value}`)
    if (cached && paramSets.value.find(p => p.id === parseInt(cached))) {
      selectedParamSetId.value = parseInt(cached)
    } else {
      selectedParamSetId.value = paramSets.value[0]?.id || null
    }
  } catch { paramSets.value = [] }
  finally { paramSetsLoading.value = false }
}

const selectedParameterSet = computed(() => paramSets.value.find(p => p.id === selectedParamSetId.value) || null)
provide('selectedParameterSet', selectedParameterSet)
provide('refreshParameterSets', loadParameterSets)

const openProjectConfig = () => {
  draftEnvId.value = selectedEnvId.value
  draftParamSetId.value = selectedParamSetId.value
  projectConfigDialogVisible.value = true
}

const saveProjectConfig = () => {
  selectedEnvId.value = draftEnvId.value
  selectedParamSetId.value = draftParamSetId.value
  if (draftEnvId.value) localStorage.setItem(getEnvCacheKey(), draftEnvId.value)
  else localStorage.removeItem(getEnvCacheKey())
  if (draftParamSetId.value) localStorage.setItem(`selected_param_set_${projectId.value}`, draftParamSetId.value)
  else localStorage.removeItem(`selected_param_set_${projectId.value}`)
  projectConfigDialogVisible.value = false
}

// 详情页面包屑名称（子页面通过 inject 修改）
const detailBreadcrumb = ref('')
provide('detailBreadcrumb', detailBreadcrumb)

watch(projectId, (val) => {
  if (isProjectPage.value && val) {
    fetchProject()
    loadEnvironments()
    loadParameterSets()
  }
})

const navItems = [
  { path: '/dashboard', label: '数据看板', icon: 'DataAnalysis' },
  { path: '/environments', label: '环境管理', icon: 'Setting' },
  { path: '/interfaces', label: '接口管理', icon: 'Link' },
  { path: '/parameter-sets', label: '参数集管理', icon: 'List' },
  { path: '/executions', label: '执行集', icon: 'VideoPlay' },
  { path: '/reports', label: '测试报告', icon: 'DataAnalysis' },
]

const moduleLabels = {
  TestWorkbench: '测试工作台',
  TestWorkbenchProject: '项目详情',
  TestWorkbenchDashboard: '数据看板',
  TestWorkbenchSystems: '系统管理',
  TestWorkbenchVersions: '版本管理',
  TestWorkbenchRequirements: '需求管理',
  TestWorkbenchMergedRequirements: '需求管理',
  TestWorkbenchCases: '用例管理',
  TestWorkbenchBugs: 'Bug 管理',
  TestWorkbenchLegacy: '遗留项管理',
  ProjectDashboard: '数据看板', Environments: '环境管理', ParameterSets: '参数集管理', ParameterSetDetail: '参数集详情',
  Interfaces: '接口管理',
  Executions: '执行集管理', Reports: '测试报告', Projects: '项目管理',
  Profile: '个人中心', Settings: '系统设置', Users: '平台用户管理',
  SchedulePolicies: '执行策略',
  // 工具箱
  NavigationApps: '导航列表',
  ToolCodec: '编解码工具', ToolBase64: 'Base64', ToolUrlCodec: 'URL 编解码', ToolHash: '哈希',
  ToolTextTools: '文本工具', ToolTextDiff: '文本对比', ToolTranslate: '多语言翻译',
  ToolFormat: '格式处理', ToolJsonFormat: 'JSON格式化', ToolMarkdownPreview: 'Markdown预览',
  ToolGenerate: '生成工具', ToolTimestamp: '时间戳', ToolIdCard: '身份证', ToolQrcode: '二维码生成',
  ToolXmind: '用例工具', ToolJsonPathExtractor: 'JSONPath提取', ToolCurl: 'cURL解析',
  // 管理页面
  Users: '平台用户管理', Profile: '个人中心', Feedback: '问题反馈',
  DataAdminAudit: '审计日志管理', DataAdminCleanup: '平台数据管理', ModelAdminModels: 'AI模型配置', ModelAdminModelsMine: 'AI模型配置', ModelAdminModelsPlatform: 'AI模型配置', ModelAdminModelsUsers: 'AI模型配置', ModelAdminUsage: 'AI用量统计', ModelAdminUsageOverview: 'AI用量统计', ModelAdminUsageRecords: 'AI用量统计', ConfigAdminChannels: '消息渠道管理', ConfigAdminTemplates: '消息模板管理', ConfigAdminPolicies: '执行策略管理',
  // 工具箱
}

const breadcrumbs = computed(() => {
  const path = route.path

  // 模块首页不显示面包屑
  if (path === '/dashboard' || path === '/projects' || path === '/test-workbench') return []
  if (path.startsWith('/test-workbench/project/')) {
    const crumbs = [{ label: '测试工作台', path: '/test-workbench' }]
    if (detailBreadcrumb.value) crumbs.push({ label: detailBreadcrumb.value })
    const label = moduleLabels[route.name]
    if (label && label !== '项目详情') crumbs.push({ label })
    return crumbs
  }

  // 工具箱 / 导航管理
  if (isToolModule.value) {
    const label = moduleLabels[route.name]
    return label ? [{ label: '工具箱', path: '/tools/codec' }, { label }] : [{ label: '工具箱' }]
  }
  if (isNavModule.value) {
    const label = moduleLabels[route.name]
    return label ? [{ label: '导航管理', path: '/tools/navigation' }, { label }] : [{ label: '导航管理' }]
  }

  // 管理中心页面 — 不显示面包屑，改由各页内容区顶部展示统一标题
  if (isAdminPage.value) return []

  // API测试项目页面
  const crumbs = [{ label: 'API测试', path: '/projects' }]
  if (isProjectPage.value) {
    crumbs.push({ label: projectName.value || '项目', path: `/project/${projectId.value}/environments` })
  }
  const label = moduleLabels[route.name]
  if (route.name === 'ParameterSetDetail') {
    crumbs.push({ label: '参数集管理', path: `/project/${projectId.value}/parameter-sets` })
    if (detailBreadcrumb.value) crumbs.push({ label: detailBreadcrumb.value })
  } else if (label) {
    crumbs.push({ label })
  }
  return crumbs
})

const isActive = (path) => {
  const base = `/project/${projectId.value}${path}`
  return route.path === base || route.path.startsWith(`${base}/`)
}

const fetchProject = async () => {
  if (!isProjectPage.value || !projectId.value) return
  try { const data = await getProject(projectId.value); projectName.value = data?.name || '' }
  catch { projectName.value = '' }
}

onMounted(async () => {
  if (!userStore.userInfo) await userStore.getUserInfo()
  if (isProjectPage.value && projectId.value) { fetchProject(); loadEnvironments(); loadParameterSets() }
})
</script>

<style scoped>
.layout { height: 100vh; display: flex; flex-direction: column; background: #f7f8fa; }


/* 面包屑 */
.breadcrumb-bar {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 24px; background: #fff; border-bottom: 1px solid #f0f0f0;
  font-size: 15px; flex-shrink: 0;
}
/* 主体 */
.layout-body { flex: 1; display: flex; overflow: hidden; }
.sidebar { width: 240px; background: #fafafa; border-right: 1px solid #f0f0f0; display: flex; flex-direction: column; flex-shrink: 0; overflow-y: auto; }
.sidebar-nav { padding: 10px; flex: 1; display: flex; flex-direction: column; gap: 2px; }
.nav-group { display: flex; flex-direction: column; gap: 2px; }
.nav-item { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 8px; font-size: 15px; font-weight: 500; color: #595959; text-decoration: none; transition: all .2s; }
.nav-item:hover { background: #f0f0f0; color: #1a1a1a; }
.nav-item.active { background: #e6f4ff; color: #1677ff; font-weight: 600; }
.sidebar-env { padding: 10px; border-top: 1px solid #f0f0f0; margin-top: auto; }
.project-config-card { display: flex; flex-direction: column; gap: 10px; padding: 12px; border: 1px solid #e1efff; border-radius: 10px; background: linear-gradient(145deg, #f5faff 0%, #fff 100%); box-shadow: 0 4px 12px rgba(64, 158, 255, .06); }
.project-config-card__header { display: flex; align-items: center; justify-content: space-between; min-height: 24px; padding: 0 2px; }
.project-config-card__title { color: #409eff; font-size: 14px; font-weight: 700; letter-spacing: .2px; }
.project-config-card__header :deep(.el-button) { padding: 3px 4px; font-size: 13px; font-weight: 600; }
.project-config-card__value { display: flex; width: 100%; align-items: center; justify-content: space-between; gap: 10px; min-height: 40px; padding: 6px 8px; border: 1px solid #edf3fc; border-radius: 7px; background: rgba(255, 255, 255, .72); color: #606266; cursor: pointer; font-size: 13px; text-align: left; transition: border-color .2s, background .2s; }
.project-config-card__value:hover { border-color: #b3d8ff; background: #f0f8ff; }
.project-config-card__value > span { display: inline-flex; flex: 0 0 auto; align-items: center; justify-content: center; min-width: 46px; min-height: 24px; padding: 0 6px; border-radius: 5px; background: #edf5ff; color: #409eff; font-size: 13px; font-weight: 600; white-space: nowrap; }
.project-config-card__value :deep(.el-tooltip__trigger) { flex: 1 1 auto; min-width: 0; overflow: hidden; }
.project-config-card__value strong { display: block; overflow: hidden; color: #303133; font-size: 13px; font-weight: 600; text-align: right; text-overflow: ellipsis; white-space: nowrap; }
.project-config-dialog__hint { margin: 0 0 18px; color: var(--el-text-color-secondary); font-size: 13px; line-height: 20px; }
.project-config-dialog__section + .project-config-dialog__section { margin-top: 18px; }
.project-config-dialog__label { margin-bottom: 8px; color: var(--el-text-color-regular); font-size: 14px; font-weight: 600; }
.project-config-dialog__select { width: 100%; }
.env-label, .context-label { font-size: 13px; color: #595959; margin-bottom: 8px; font-weight: 600; }
.main { flex: 1; min-width: 0; overflow-y: auto; padding: 20px 24px; }
.main.has-sidebar { }
.main.fixed-content-page { overflow: hidden; display: flex; flex-direction: column; }
.main.fixed-content-page > * { flex: 1 1 auto; min-width: 0; min-height: 0; }
.main.is-ui-module { overflow: hidden; padding: 0; display: flex; flex-direction: column; }
.main.is-admin-module {
  overflow: hidden;
  background: #f6f8fb;
  color: #303133;
}

/* 管理中心局部主题：仅统一视觉，不影响其他业务模块 */
.main.is-admin-module :deep(.page-wrap),
.main.is-admin-module :deep(.profile-container) {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.main.is-admin-module :deep(.page-header) {
  min-height: 40px;
  margin-bottom: 14px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-shrink: 0;
}
.main.is-admin-module :deep(h2.page-title),
.main.is-admin-module :deep(.page-title h2) {
  margin: 0 0 4px;
  color: #1f2937;
  font-size: 20px;
  font-weight: 650;
  line-height: 1.4;
}
/* 管理中心各页统一页面标题（内容区顶部，替代原面包屑） */
.main.is-admin-module :deep(.admin-page-title) {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 14px;
}
.main.is-admin-module :deep(.admin-page-title h2) {
  margin: 0;
  color: #1f2937;
  font-size: 20px;
  font-weight: 650;
  line-height: 1.4;
}
.main.is-admin-module :deep(.page-desc),
.main.is-admin-module :deep(.toolbar-tip) {
  margin: 0;
  color: #8a94a6;
  font-size: 13px;
  line-height: 1.6;
}
.main.is-admin-module :deep(.search-area),
.main.is-admin-module :deep(.search-bar),
.main.is-admin-module :deep(.filter-bar),
.main.is-admin-module :deep(.filter-row),
.main.is-admin-module :deep(.log-search-form) {
  padding: 12px 16px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  background: #f8fafc;
  border: 1px solid #edf1f6;
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.02);
  flex-shrink: 0;
}
.main.is-admin-module :deep(.toolbar-row) {
  min-height: 36px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
}
.main.is-admin-module :deep(.toolbar-actions),
.main.is-admin-module :deep(.toolbar-buttons) {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.main :deep(.list-toolbar-frame) {
  box-sizing: border-box;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 12px 10px;
  width: 100%;
  min-width: 0;
  padding: 12px 16px;
  margin-bottom: 12px;
  background: #f8fafc;
  border: 1px solid #edf1f6;
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.02);
}
.main :deep(.list-toolbar-frame > .el-form) {
  display: flex;
  flex: 1 1 auto;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 12px 10px;
  min-width: 0;
  margin: 0;
}
.main :deep(.list-toolbar-frame .el-form-item) { margin: 0; }
.main :deep(.list-toolbar-frame .list-toolbar-actions),
.main :deep(.list-toolbar-frame .interface-header-actions),
.main :deep(.list-toolbar-frame .card-header-actions) {
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 12px;
  min-width: 0;
}
.main.is-admin-module :deep(.search-area .el-form),
.main.is-admin-module :deep(.search-area .search-form) {
  width: 100%;
  margin: 0;
}
.main.is-admin-module :deep(.search-area .el-form-item),
.main.is-admin-module :deep(.log-search-form .el-form-item) {
  margin-top: 0;
  margin-bottom: 0;
  margin-right: 12px;
}
.main.is-admin-module :deep(.el-button) {
  font-size: 14px !important;
  border-radius: 6px;
}
.main.is-admin-module :deep(.el-input__inner),
.main.is-admin-module :deep(.el-select .el-input__inner),
.main.is-admin-module :deep(.el-form-item__label) {
  font-size: 14px !important;
}
.main.is-admin-module :deep(.el-tabs__header) {
  margin: 0 0 14px;
  flex-shrink: 0;
}
.main.is-admin-module :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background: #dfe5ee;
}
.main.is-admin-module :deep(.el-tabs__item) {
  height: 42px;
  padding: 0 20px;
  font-size: 15px;
  font-weight: 600;
}
.main.is-admin-module :deep(.el-tabs__active-bar) {
  height: 3px;
  border-radius: 3px;
}

/* 有页签的管理页统一三段式布局：页签在最上、搜索工具栏居中、列表在下 */
/* page-header 默认是左右分栏（标题+操作），此处强制竖排，避免页签与搜索挤在同一行 */
.main.is-admin-module :deep(.admin-tabs-shell .page-header) {
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  gap: 0;
}
.main.is-admin-module :deep(.admin-tabs-shell .model-tabs-row),
.main.is-admin-module :deep(.admin-tabs-shell .list-toolbar) {
  width: 100%;
}
/* 搜索项与按钮统一为独立卡片，与下方列表卡片形成清晰分段 */
.main.is-admin-module :deep(.admin-tabs-shell .list-toolbar) {
  padding: 12px 16px;
  background: #f8fafc;
  border: 1px solid #edf1f6;
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.02);
}
.main.is-admin-module :deep(.scroll-area),
.main.is-admin-module :deep(.log-card) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: #fff;
  border: 1px solid #e7ebf1;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}
.main.is-admin-module :deep(.scroll-area) {
  display: flex;
  flex-direction: column;
}
.main.is-admin-module :deep(.scroll-area.cleanup-scroll-area) {
  display: block;
  overflow-y: auto;
  padding: 12px;
}
.main.is-admin-module :deep(.scroll-area > .el-table),
.main.is-admin-module :deep(.log-card-body .el-table) {
  flex: 1;
  min-height: 0;
}
.main.is-admin-module :deep(.el-table) {
  --el-table-border-color: #edf0f5;
  --el-table-header-bg-color: #f7f9fc;
  --el-table-row-hover-bg-color: #f3f7ff;
  font-size: 14px;
}
.main.is-admin-module :deep(.el-table th.el-table__cell) {
  height: 46px;
  padding: 0;
  color: #303744;
  background: #f7f9fc;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
}
.main.is-admin-module :deep(.el-table td.el-table__cell) {
  height: 48px;
  padding: 0;
  color: #596273;
}
.main.is-admin-module :deep(.el-table .cell) {
  line-height: 1.5;
}
.main.is-admin-module :deep(.el-table__fixed-right) {
  box-shadow: -4px 0 10px rgba(15, 23, 42, 0.04) !important;
}
.main.is-admin-module :deep(.pagination-area),
.main.is-admin-module :deep(.log-card-ft) {
  min-height: 48px;
  padding: 10px 12px 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-shrink: 0;
}
.main.is-admin-module :deep(.log-card-ft) {
  padding-bottom: 10px;
  border-top: 1px solid #edf0f5;
}
.main.is-admin-module :deep(.el-pagination),
.main.is-admin-module :deep(.el-pagination button),
.main.is-admin-module :deep(.el-pager li) {
  font-size: 14px;
}
.main.is-admin-module :deep(.el-empty) {
  padding: 52px 0;
}
.main.is-admin-module :deep(.el-empty__description p) {
  color: #9aa3b2;
  font-size: 14px;
}
.main.is-admin-module :deep(.profile-container > .el-card) {
  height: 100%;
  overflow: hidden;
  border-color: #e7ebf1 !important;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}
.main.is-admin-module :deep(.profile-container > .el-card:hover) {
  transform: none;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03) !important;
}
.main.is-admin-module :deep(.profile-container > .el-card .el-card__body) {
  height: calc(100% - 58px);
  overflow-y: auto;
}

@media (max-width: 1600px) {
  .sidebar { width: 220px; }
  .main { padding: 18px 20px; }
}
@media (max-width: 1440px) {
  .sidebar { width: 200px; }
  .main { padding: 16px; }
  .breadcrumb-bar { padding: 8px 16px; font-size: 14px; }
  .main.is-admin-module :deep(.page-header) { gap: 12px; }
  .main.is-admin-module :deep(.toolbar-form) { display: flex; flex-wrap: wrap; }
  .main.is-admin-module :deep(.toolbar-form .el-form-item) { margin-right: 10px; }
}
@media (max-width: 1200px) {
  .sidebar { width: 190px; }
}
/* 平板 */
@media (max-width: 768px) {
  .sidebar { width: 180px; }
  .nav-item { padding: 10px 12px; font-size: 14px; gap: 8px; }
  .main { padding: 14px; }
  .breadcrumb-bar { padding: 8px 12px; font-size: 12px; }
}
/* 手机 */
@media (max-width: 480px) {
  .sidebar { width: 56px; }
  .nav-item span { display: none; }
  .nav-item { justify-content: center; padding: 12px 0; }
  .sidebar-env { display: none; }
  .main { padding: 10px; }
}
</style>
