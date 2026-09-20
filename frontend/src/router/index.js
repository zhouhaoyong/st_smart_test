import { createRouter, createWebHashHistory } from 'vue-router'
import Layout from '@/layout/index.vue'
import ToolsLayout from '@/layout/ToolsLayout.vue'
import { isAdmin } from '@/utils/permission'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: Layout,
    children: [
      {
        path: '',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '智测' }
      }
    ]
  },
  {
    path: '/',
    component: Layout,
    redirect: '/projects',
    children: [
      {
        path: 'projects',
        name: 'Projects',
        component: () => import('@/views/Projects.vue'),
        meta: { title: '项目管理' }
      },
      {
        path: 'test-workbench',
        name: 'TestWorkbench',
        component: () => import('@/views/TestWorkbenchProjects.vue'),
        meta: { title: '测试工作台' }
      },
      {
        path: 'test-workbench/project/:id',
        name: 'TestWorkbenchProject',
        component: () => import('@/views/TestWorkbench.vue'),
        meta: { title: '测试工作台详情' },
        children: [
          {
            path: '',
            redirect: to => `/test-workbench/project/${to.params.id}/dashboard`,
          },
          {
            path: 'dashboard',
            name: 'TestWorkbenchDashboard',
            component: () => import('@/views/test-workbench/pages/WorkbenchDashboardPage.vue'),
            meta: { title: '数据看板' },
          },
          {
            path: 'pending',
            name: 'TestWorkbenchPending',
            component: () => import('@/views/test-workbench/pages/WorkbenchPendingPage.vue'),
            meta: { title: '待办事项' },
          },
          {
            path: 'systems',
            name: 'TestWorkbenchSystems',
            component: () => import('@/views/test-workbench/pages/WorkbenchSystemPage.vue'),
            meta: { title: '系统管理' },
          },
          {
            path: 'versions',
            name: 'TestWorkbenchVersions',
            component: () => import('@/views/test-workbench/pages/WorkbenchVersionPage.vue'),
            meta: { title: '版本管理' },
          },
          {
            path: 'requirements',
            name: 'TestWorkbenchRequirements',
            component: () => import('@/views/test-workbench/pages/WorkbenchRequirementPage.vue'),
            meta: { title: '需求管理' }
          },
          {
            path: 'merged-requirements',
            name: 'TestWorkbenchMergedRequirements',
            component: () => import('@/views/test-workbench/pages/WorkbenchRequirementPage.vue'),
            meta: { title: '需求管理' }
          },
          {
            path: 'cases',
            name: 'TestWorkbenchCases',
            component: () => import('@/views/test-workbench/pages/WorkbenchTestCasePage.vue'),
            meta: { title: '用例管理' }
          },
          {
            path: 'bugs',
            name: 'TestWorkbenchBugs',
            component: () => import('@/views/test-workbench/pages/WorkbenchBugPage.vue'),
            meta: { title: 'Bug 管理' }
          },
          {
            path: 'legacy',
            name: 'TestWorkbenchLegacy',
            component: () => import('@/views/test-workbench/pages/WorkbenchLegacyPage.vue'),
            meta: { title: '遗留项管理' }
          },
        ],
      },
      {
        path: 'project/:id',
        name: 'ProjectDetail',
        redirect: '/project/:id/dashboard',
      },
      {
        path: 'project/:id/dashboard',
        name: 'ProjectDashboard',
        component: () => import('@/views/ProjectDashboard.vue'),
        meta: { title: '数据看板' }
      },
      {
        path: 'project/:id/environments',
        name: 'Environments',
        component: () => import('@/views/Environments.vue'),
        meta: { title: '环境管理' }
      },
      {
        path: 'project/:id/parameter-sets',
        name: 'ParameterSets',
        component: () => import('@/views/ParameterSets.vue'),
        meta: { title: '参数集管理' }
      },
      {
        path: 'project/:id/parameter-sets/:psId',
        name: 'ParameterSetDetail',
        component: () => import('@/views/ParameterSetDetail.vue'),
        meta: { title: '参数集详情' }
      },
      {
        path: 'project/:id/interfaces',
        name: 'Interfaces',
        component: () => import('@/views/Interfaces.vue'),
        meta: { title: '接口管理' }
      },
      {
        path: 'project/:id/testcases',
        redirect: to => `/project/${to.params.id}/interfaces`,
      },
      {
        path: 'project/:id/interfaces/:iid/cases',
        name: 'InterfaceCases',
        component: () => import('@/views/InterfaceCases.vue'),
        meta: { title: '用例管理' }
      },
      {
        path: 'project/:id/executions',
        name: 'Executions',
        component: () => import('@/views/Executions.vue'),
        meta: { title: '执行集管理' }
      },
      {
        path: 'project/:id/reports',
        name: 'Reports',
        component: () => import('@/views/Reports.vue'),
        meta: { title: '测试报告' }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/Profile.vue'),
        meta: { title: '个人中心' }
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/Users.vue'),
        meta: { title: '平台用户管理' }
      },
      {
        path: 'schedule-policies',
        name: 'SchedulePolicies',
        component: () => import('@/views/SchedulePolicies.vue'),
        meta: { title: '执行策略' }
      },
      {
        path: 'feedback',
        name: 'Feedback',
        component: () => import('@/views/feedback/index.vue'),
        meta: { title: '问题反馈' }
      },
      {
        path: 'data-admin',
        redirect: '/data-admin/cleanup',
        meta: { title: '数据管理' }
      },
      {
        path: 'data-admin/audit',
        name: 'DataAdminAudit',
        component: () => import('@/views/AuditLogs.vue'),
        meta: { title: '审计日志管理' }
      },
      {
        path: 'data-admin/cleanup',
        name: 'DataAdminCleanup',
        component: () => import('@/views/DataCleanup.vue'),
        meta: { title: '平台数据管理' }
      },
      {
        path: 'model-admin',
        redirect: '/model-admin/models/mine',
        meta: { title: 'AI模型配置' }
      },
      {
        path: 'model-admin/models',
        name: 'ModelAdminModels',
        redirect: '/model-admin/models/mine',
        meta: { title: 'AI模型配置' }
      },
      {
        path: 'model-admin/models/mine',
        name: 'ModelAdminModelsMine',
        component: () => import('@/views/admin/AiModels.vue'),
        meta: { title: 'AI模型配置', tab: 'mine' }
      },
      {
        path: 'model-admin/models/platform',
        name: 'ModelAdminModelsPlatform',
        component: () => import('@/views/admin/AiModels.vue'),
        meta: { title: 'AI模型配置', tab: 'platform' }
      },
      {
        path: 'model-admin/models/users',
        name: 'ModelAdminModelsUsers',
        component: () => import('@/views/admin/AiModels.vue'),
        meta: { title: 'AI模型配置', tab: 'users' }
      },
      {
        path: 'model-admin/usage',
        name: 'ModelAdminUsage',
        redirect: to => {
          const query = { ...to.query }
          const target = query.tab === 'logs' ? '/model-admin/usage/records' : '/model-admin/usage/overview'
          delete query.tab
          return { path: target, query }
        },
        meta: { title: 'AI用量统计' }
      },
      {
        path: 'model-admin/usage/overview',
        name: 'ModelAdminUsageOverview',
        component: () => import('@/views/admin/AiUsage.vue'),
        props: { view: 'full' },
        meta: { title: 'AI用量统计', tab: 'summary' }
      },
      {
        path: 'model-admin/usage/records',
        name: 'ModelAdminUsageRecords',
        component: () => import('@/views/admin/AiUsage.vue'),
        props: { view: 'full' },
        meta: { title: 'AI用量统计', tab: 'logs' }
      },
      {
        path: 'model-admin/quotas',
        redirect: '/model-admin/models',
      },
      {
        path: 'model-admin/logs',
        redirect: '/model-admin/usage',
      },
      {
        path: 'model-admin/usage/users/:userId',
        name: 'UserUsageDetail',
        component: () => import('@/views/admin/UserUsageDetail.vue'),
        meta: { title: '用户 AI 用量' }
      },
      {
        path: 'config-admin',
        redirect: '/config-admin/channels',
        meta: { title: '配置管理' }
      },
      {
        path: 'config-admin/channels',
        name: 'ConfigAdminChannels',
        component: () => import('@/views/admin/MessageChannels.vue'),
        meta: { title: '消息渠道管理' }
      },
      {
        path: 'config-admin/templates',
        name: 'ConfigAdminTemplates',
        component: () => import('@/views/admin/MessageTemplates.vue'),
        meta: { title: '消息模板管理' }
      },
      {
        path: 'config-admin/policies',
        name: 'ConfigAdminPolicies',
        component: () => import('@/views/SchedulePolicies.vue'),
        meta: { title: '执行策略管理' }
      },
    ]
  },
  // 智测 测试工具模块
  {
    path: '/tools',
    component: ToolsLayout,
    redirect: '/tools/markdown-preview',
    children: [
      {
        path: 'navigation',
        name: 'NavigationAppsRoot',
        component: () => import('@/views/tools/NavigationApps.vue'),
        meta: { title: '导航管理' }
      },
      {
        path: 'generate',
        name: 'ToolGenerate',
        redirect: '/tools/timestamp',
        meta: { title: '生成工具' }
      },
      {
        path: 'geocode',
        name: 'ToolGeocode',
        component: () => import('@/views/tools/GeocodeTool.vue'),
        meta: { title: '地址转经纬度' }
      },
      {
        path: 'text-tools',
        name: 'ToolTextTools',
        redirect: '/tools/text-diff',
        meta: { title: '文本工具' }
      },
      {
        path: 'curl',
        name: 'ToolCurl',
        component: () => import('@/views/tools/Curl.vue'),
        meta: { title: 'cURL解析' }
      },
      {
        path: 'cron',
        name: 'ToolCron',
        component: () => import('@/views/tools/CronTool.vue'),
        meta: { title: 'Cron 表达式' }
      },
      {
        path: 'codec',
        name: 'ToolCodec',
        redirect: '/tools/base64',
        meta: { title: '编解码工具' }
      },
      {
        path: 'base64',
        name: 'ToolBase64',
        component: () => import('@/views/tools/CodecTools.vue'),
        meta: { title: 'Base64', toolTab: 'base64' }
      },
      {
        path: 'url-codec',
        name: 'ToolUrlCodec',
        component: () => import('@/views/tools/CodecTools.vue'),
        meta: { title: 'URL 编解码', toolTab: 'url' }
      },
      {
        path: 'hash',
        name: 'ToolHash',
        component: () => import('@/views/tools/CodecTools.vue'),
        meta: { title: '哈希', toolTab: 'hash' }
      },
      {
        path: 'text-diff',
        name: 'ToolTextDiff',
        component: () => import('@/views/tools/TextTools.vue'),
        meta: { title: '文本对比', toolTab: 'textdiff' }
      },
      {
        path: 'translate',
        name: 'ToolTranslate',
        component: () => import('@/views/tools/TextTools.vue'),
        meta: { title: '多语言翻译', toolTab: 'translation' }
      },
      {
        path: 'format',
        name: 'ToolFormat',
        redirect: '/tools/json-format',
        meta: { title: '格式处理' }
      },
      {
        path: 'json-format',
        name: 'ToolJsonFormat',
        component: () => import('@/views/tools/FormatTools.vue'),
        meta: { title: 'JSON格式化', toolTab: 'json' }
      },
      {
        path: 'markdown-preview',
        name: 'ToolMarkdownPreview',
        component: () => import('@/views/tools/FormatTools.vue'),
        meta: { title: 'Markdown预览', toolTab: 'markdown' }
      },
      {
        path: 'timestamp',
        name: 'ToolTimestamp',
        component: () => import('@/views/tools/GenerateTools.vue'),
        meta: { title: '时间戳', toolTab: 'timestamp' }
      },
      {
        path: 'id-card',
        name: 'ToolIdCard',
        component: () => import('@/views/tools/GenerateTools.vue'),
        meta: { title: '身份证生成', toolTab: 'idcard' }
      },
      {
        path: 'qrcode',
        name: 'ToolQrcode',
        component: () => import('@/views/tools/QrcodeTool.vue'),
        meta: { title: '二维码生成' }
      },
      {
        path: 'xmind',
        name: 'ToolXmind',
        component: () => import('@/views/tools/XmindTool.vue'),
        meta: { title: '用例工具' }
      },
      {
        path: 'json-path-extractor',
        name: 'ToolJsonPathExtractor',
        component: () => import('@/views/tools/JsonPathExtractorTool.vue'),
        meta: { title: 'JSONPath提取' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes
})

const publicRouteNames = ['Login']

const getStoredUser = () => {
  const userStr = localStorage.getItem('user_info')
  if (!userStr) return null
  try {
    return JSON.parse(userStr)
  } catch {
    localStorage.removeItem('user_info')
    localStorage.removeItem('access_token')
    return null
  }
}

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('access_token')
  if (!publicRouteNames.includes(to.name) && !token) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }
  // 管理员页面路由守卫
  const superAdminPaths = ['/data-admin', '/model-admin/models/users', '/model-admin/usage/users']
  const managerPaths = ['/config-admin', '/schedule-policies']
  if (superAdminPaths.some(p => to.path.startsWith(p))) {
    const user = getStoredUser()
    if (!user || !user.is_superuser) {
      next('/')
      return
    }
  }
  if (to.path.startsWith('/users')) {
    const user = getStoredUser()
    if (!user || !user.is_superuser) {
      next('/')
      return
    }
  }
  if (managerPaths.some(p => to.path.startsWith(p))) {
    const user = getStoredUser()
    if (!user || !isAdmin(user)) {
      next('/')
      return
    }
  }
  next()
})

// 路由切换期间抑制过渡/动画：整页重建时会有大批 CSS 过渡同时触发，造成切换卡顿。
// 抑制窗口必须盖到首屏内容渲染完成为止：新页面挂载后的首帧还只是空骨架，接口数据要几十到
// 几百毫秒才回来，表格等大批 DOM 是那时才渲染的，若首帧就放开等于没抑制。平时 hover 动效不受影响。
const TRANSITION_SUPPRESS_MS = 400
// 导航被守卫拦截或中途取消时不会走到 afterEach，用更长的兜底时长确保标记一定会被摘掉，
// 否则标记残留会让全站动效永久失效。
const TRANSITION_SUPPRESS_FALLBACK_MS = 2000
let transitionReleaseTimer = 0

const suppressTransitions = (releaseDelay) => {
  if (transitionReleaseTimer) clearTimeout(transitionReleaseTimer)
  document.documentElement.classList.add('route-switching')
  transitionReleaseTimer = setTimeout(() => {
    transitionReleaseTimer = 0
    document.documentElement.classList.remove('route-switching')
  }, releaseDelay)
}

router.beforeEach((to, from, next) => {
  suppressTransitions(TRANSITION_SUPPRESS_FALLBACK_MS)
  next()
})

router.afterEach(() => {
  // 双 rAF 后新页面已完成首帧，从这一刻起再计时，把窗口盖到首屏数据渲染出来之后
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      suppressTransitions(TRANSITION_SUPPRESS_MS)
    })
  })
})

export default router
