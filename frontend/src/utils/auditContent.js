/**
 * 审计日志展示口径：模块归组、操作类型文案与操作内容拼装。
 *
 * 约定：
 * 1. 操作内容以后端 description 为准，前端不再追加「：目标XXX」这类拼接后缀，
 *    只有后端没写描述时才退化成「资源+操作」兜底。
 * 2. 操作类型下拉按「业务标签 → 一到多个后端取值」组织，后端接口的 operation
 *    支持数组，多取值标签在发起查询前展开即可。
 * 3. 历史日志里的旧取值不做兼容映射，未收录的取值原样展示。
 */

const MODULE_OPTIONS = [
  { value: 'test_workbench', label: '测试工作台' },
  { value: 'api_test', label: 'API测试' },
  { value: 'toolbox', label: '工具箱' },
  { value: 'navigation', label: '导航管理' },
  { value: 'management', label: '管理中心' },
]

const MODULE_GROUPS = {
  test_workbench: 'test_workbench', api_test: 'api_test', toolbox: 'toolbox', navigation: 'navigation', management: 'management',
  project: 'api_test', environment: 'api_test', interface: 'api_test', testcase: 'api_test',
  execution: 'api_test', parameter_set: 'api_test', '参数化': 'api_test',
  ai_import: 'api_test', api_import: 'api_test', interface_case_generate: 'api_test', executor: 'api_test',
  'Xmind转换工具': 'toolbox', 'Xmind生成工具': 'toolbox',
  curl: 'toolbox', text_tool: 'toolbox', json_tool: 'toolbox', cron_tool: 'toolbox',
  navigation_system: 'navigation',
  user: 'management', ai_model: 'management', ai_call: 'management', ai_quota: 'management',
  ai_usage: 'management', model: 'management', message_config: 'management',
  notification: 'management', feedback: 'management', report: 'management',
  schedule_policy: 'management', '审计日志': 'management', data_cleanup: 'management',
}

const MODULE_NAMES = Object.fromEntries(MODULE_OPTIONS.map(item => [item.value, item.label]))

const MODULE_TAGS = {
  test_workbench: 'primary', api_test: 'success', toolbox: 'info', navigation: 'warning', management: 'info',
}

/**
 * 操作类型总表：同一业务标签可对应多个后端取值。
 * codes 里出现的取值都会用该标签展示，除非在 OPERATION_LABEL_OVERRIDES 里单独指定。
 */
const OPERATION_GROUPS = [
  {
    label: '通用操作',
    items: [
      { label: '新增', codes: ['create', '创建', '新增'], tag: 'success' },
      { label: '编辑', codes: ['update', '更新', '编辑'], tag: 'warning' },
      { label: '删除', codes: ['delete', '删除'], tag: 'danger' },
      { label: '全部删除', codes: ['全部删除'], tag: 'danger' },
      { label: '批量删除', codes: ['batch_delete', '批量删除'], tag: 'danger' },
      { label: '复制', codes: ['copy', '复制'], tag: 'info' },
      { label: '移动', codes: ['move'], tag: 'warning' },
      { label: '批量移动', codes: ['batch_move'], tag: 'warning' },
      { label: '执行', codes: ['执行'], tag: 'info' },
      { label: '上传', codes: ['上传'], tag: 'info' },
      { label: '下载', codes: ['下载'], tag: 'info' },
      { label: '保存', codes: ['save', '保存'], tag: 'success' },
      { label: '生成', codes: ['生成'], tag: 'success' },
      { label: '解析', codes: ['解析'], tag: 'info' },
      { label: '取消', codes: ['取消'], tag: 'warning' },
      { label: '解决', codes: ['解决'], tag: 'success' },
    ],
  },
  {
    label: '测试工作台',
    items: [
      { label: '批量执行', codes: ['批量执行'], tag: 'info' },
      { label: '更正执行', codes: ['更正执行'], tag: 'warning' },
      { label: '确认', codes: ['确认'], tag: 'success' },
      { label: '取消确认', codes: ['取消确认'], tag: 'warning' },
      { label: '指派', codes: ['指派'], tag: 'info' },
      { label: '验证', codes: ['验证'], tag: 'success' },
      { label: '转为遗留项', codes: ['转为遗留项'], tag: 'warning' },
      { label: '清空项目数据', codes: ['清空项目数据'], tag: 'danger' },
      { label: 'AI需求补全', codes: ['AI补全', 'AI补全追问'], tag: 'success' },
      { label: 'AI整理成文', codes: ['AI整理成文'], tag: 'success' },
      { label: 'AI预览并对比', codes: ['AI预览并对比'], tag: 'info' },
      { label: 'AI需求合并', codes: ['AI合并追问', 'AI重新合并', 'AI重新合并预览', '重新合并'], tag: 'success' },
      { label: 'AI用例生成', codes: ['AI生成', 'AI用例生成对话'], tag: 'success' },
    ],
  },
  {
    label: 'API测试',
    items: [
      { label: '接口调试', codes: ['接口调试', '调试'], tag: 'info' },
      { label: '用例运行', codes: ['用例运行'], tag: 'info' },
      { label: '提取令牌', codes: ['提取令牌'], tag: 'warning' },
      { label: '设为默认', codes: ['设为默认'], tag: 'success' },
      { label: '排序', codes: ['排序'], tag: 'info' },
      { label: '批量更新服务配置', codes: ['batch_update_service'], tag: 'warning' },
      { label: '参数化', codes: ['参数化'], tag: 'info' },
      { label: '接口导入', codes: ['导入'], tag: 'success' },
      { label: 'AI接口分析', codes: ['推荐'], tag: 'success' },
      { label: 'AI用例生成计划', codes: ['生成计划'], tag: 'success' },
      { label: '确认保存', codes: ['确认保存'], tag: 'success' },
    ],
  },
  {
    label: '工具箱',
    items: [
      { label: '生成 Xmind', codes: ['生成Xmind'], tag: 'success' },
      { label: '翻译', codes: ['翻译'], tag: 'info' },
      { label: '文本对比', codes: ['对比'], tag: 'info' },
      { label: '格式转换', codes: ['转换'], tag: 'info' },
      { label: '请求代理', codes: ['请求代理'], tag: 'info' },
      { label: '复制查询结果', codes: ['复制查询结果'], tag: 'info' },
      { label: '身份证查手机号', codes: ['身份证查手机号'], tag: 'info' },
      { label: '身份证查建档信息', codes: ['身份证查建档信息'], tag: 'info' },
      { label: '主索引查建档信息', codes: ['主索引查建档信息'], tag: 'info' },
    ],
  },
  {
    label: '管理中心',
    items: [
      { label: '登录', codes: ['login'], tag: 'info' },
      { label: '退出', codes: ['logout'], tag: 'info' },
      { label: '注册', codes: ['register'], tag: 'success' },
      { label: '修改密码', codes: ['password_change'], tag: 'warning' },
      { label: '创建令牌', codes: ['token_create'], tag: 'success' },
      { label: '撤销令牌', codes: ['token_revoke'], tag: 'warning' },
      { label: '启用', codes: ['启用'], tag: 'success' },
      { label: '停用', codes: ['停用'], tag: 'warning' },
      // 这几类操作只描述"做了什么"，通过/失败/中断由操作内容体现，故用中性颜色。
      { label: '模型能力检测', codes: ['模型能力检测'], tag: 'info' },
      { label: '拉取模型列表', codes: ['拉取模型列表'], tag: 'info' },
      { label: '测试余额接口', codes: ['测试余额接口'], tag: 'info' },
      { label: '查询余额', codes: ['查询余额'], tag: 'info' },
      { label: '权限变更失效', codes: ['权限变更失效'], tag: 'danger' },
      { label: '设置平台模型额度', codes: ['设置平台模型额度'], tag: 'warning' },
      { label: '设置我的模型额度', codes: ['设置我的模型额度'], tag: 'warning' },
      { label: '模型调用成功', codes: ['模型调用成功'], tag: 'success' },
      { label: '模型调用失败', codes: ['模型调用失败'], tag: 'danger' },
      { label: '调用记录清理', codes: ['调用记录清理'], tag: 'danger' },
      { label: '审计日志清理', codes: ['审计日志清理'], tag: 'danger' },
      { label: '测试', codes: ['测试'], tag: 'info' },
      { label: '预览', codes: ['预览'], tag: 'info' },
      { label: '发送', codes: ['发送'], tag: 'success' },
      { label: '提交', codes: ['提交'], tag: 'success' },
      { label: '回复', codes: ['回复'], tag: 'info' },
      { label: '确认关闭', codes: ['确认关闭'], tag: 'success' },
      { label: '重新打开', codes: ['重新打开'], tag: 'warning' },
      { label: '物理清理', codes: ['物理清理'], tag: 'danger' },
    ],
  },
]

// 下拉里按业务标签聚合，但列表列需要区分到具体动作的取值单独指定文案。
const OPERATION_LABEL_OVERRIDES = {
  'AI补全追问': 'AI需求补全追问',
  'AI合并追问': 'AI需求合并追问',
  'AI重新合并': 'AI需求重新合并',
  'AI重新合并预览': 'AI需求重新合并预览',
  '重新合并': 'AI需求合并保存',
  'AI用例生成对话': 'AI用例生成追问',
}

const OPERATION_VALUE_SEPARATOR = '|'

const operationLabels = {}
const operationTags = {}
for (const group of OPERATION_GROUPS) {
  for (const item of group.items) {
    for (const code of item.codes) {
      operationLabels[code] = OPERATION_LABEL_OVERRIDES[code] || item.label
      operationTags[code] = item.tag
    }
  }
}

export const moduleOptions = MODULE_OPTIONS

/** 操作类型下拉分组：value 为一到多个后端取值，多取值用 | 连接。 */
export const operationFilterGroups = OPERATION_GROUPS.map(group => ({
  label: group.label,
  options: group.items.map(item => ({
    label: item.label,
    value: item.codes.join(OPERATION_VALUE_SEPARATOR),
  })),
}))

/** 把下拉选中的业务标签展开成后端可用的取值数组。 */
export const flattenOperationValues = (values) => {
  const list = Array.isArray(values) ? values : values ? [values] : []
  const flat = list.flatMap(value => String(value).split(OPERATION_VALUE_SEPARATOR)).filter(Boolean)
  return [...new Set(flat)]
}

export const getModuleGroup = (module) => MODULE_GROUPS[module] || 'management'
export const getModuleName = (module) => (module ? MODULE_NAMES[getModuleGroup(module)] : '-')
export const moduleTag = (module) => MODULE_TAGS[getModuleGroup(module)] ?? 'info'

export const getOperationName = (operation) => operationLabels[operation] || (operation ? String(operation) : '-')
export const operationTag = (operation) => operationTags[operation] ?? 'info'

const auditResourceNames = {
  user: '用户', ai_model: '模型', ai_quota: '模型额度', ai_usage: '调用记录', ai_call: '模型调用',
  project: '项目', environment: '环境', interface: '接口', testcase: '用例', execution: '执行集',
  parameter_set: '参数集', api_import: '接口导入',
  interface_case_generate: '接口批量生成用例', executor: '执行器', ai_import: '历史接口导入',
  notification: '通知配置', feedback: '问题反馈', report: '测试报告', message_config: '消息模板',
  schedule_policy: '计划策略', navigation: '导航项', navigation_system: '导航系统',
  curl: 'cURL工具', text_tool: '文本工具', json_tool: 'JSON工具', cron_tool: 'Cron工具',
  test_workbench: '测试工作台', data_cleanup: '数据清理', '审计日志': '审计日志',
}

const cleanAuditText = (value) => String(value ?? '').replace(/\s+/g, ' ').trim()

const getAuditDetails = (details) => {
  if (details && typeof details === 'object' && !Array.isArray(details)) return details
  if (typeof details === 'string' && details.trim()) {
    try {
      const parsed = JSON.parse(details)
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
    } catch { return {} }
  }
  return {}
}

const getDetailNumber = (details, keys) => {
  for (const key of keys) {
    const value = details?.[key]
    if (value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value))) {
      return Number(value)
    }
  }
  return null
}

const detailCount = (details, keys, prefix, suffix) => {
  const value = getDetailNumber(details, keys)
  return value === null ? '' : `${prefix}${value}${suffix}`
}

const formatAuditTarget = (row) => {
  const target = cleanAuditText(row?.target_name)
  if (!target) return ''
  if (row?.module !== 'executor') return target

  // 现在接口调试只记录接口名或主机名；这里仅为历史记录兜底，避免把旧的完整地址展示出来。
  const match = target.match(/^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(.+)$/i)
  if (!match) return target.split(/[?#]/, 1)[0]
  const method = match[1].toUpperCase()
  const rawUrl = match[2]
  if (!/^(https?:\/\/|\/)/i.test(rawUrl)) return target
  try {
    const parsed = new URL(rawUrl, 'http://audit.local')
    return `${method} ${parsed.pathname || '/'}`
  } catch {
    return `${method} ${rawUrl.split(/[?#]/, 1)[0]}`
  }
}

const normalizeApiTestDescription = (description) => {
  let content = cleanAuditText(description)
  if (!content) return ''

  // 兼容历史记录：模块已经展示为“API测试”，操作内容不再重复该前缀。
  content = content.replace(/^API测试[，,]\s*/, '')
  content = content.replace(/^API测试(?=接口导入|接口调试|用例执行)/, '')
  content = content.replace(/执行接口(?=「|：)/g, '接口调试')
  content = content.replace(/执行用例(?=「|：)/g, '用例运行')
  return content
}

const formatLegacyAiImportContent = (row, details) => {
  const operation = cleanAuditText(row?.operation)
  const description = cleanAuditText(row?.description)
  const target = formatAuditTarget(row)
  const labels = {
    解析: '历史接口导入-接口解析',
    推荐: '历史接口导入-接口分析',
    '生成计划': '历史接口导入-用例生成计划',
    生成: '历史接口导入-用例生成',
    下载: '历史接口导入-模板下载',
    save: '历史接口导入-保存',
    保存: '历史接口导入-保存',
  }
  const baseContent = operation === '取消'
    ? `历史接口导入-${/生成|用例/.test(description) ? '用例生成取消' : '接口分析取消'}`
    : labels[operation] || '历史接口导入'
  const parts = []
  if (operation === '解析') {
    parts.push(detailCount(details, ['total_interfaces'], '解析 ', ' 个接口'))
  } else if (operation === '推荐') {
    parts.push(
      detailCount(details, ['analyzed_interfaces'], '分析 ', ' 个接口'),
      detailCount(details, ['recommended_interfaces'], '推荐 ', ' 个接口'),
      detailCount(details, ['not_recommended_interfaces'], '暂不推荐 ', ' 个接口'),
      detailCount(details, ['failed_interfaces'], '失败 ', ' 个接口'),
    )
  } else if (operation === '生成计划') {
    parts.push(
      detailCount(details, ['total_interfaces'], '涉及 ', ' 个接口'),
      detailCount(details, ['total_batches'], '拆分 ', ' 批'),
    )
  } else if (operation === '生成') {
    const batchIndex = getDetailNumber(details, ['batch_index'])
    const totalBatches = getDetailNumber(details, ['total_batches'])
    if (batchIndex !== null && totalBatches !== null) parts.push(`第 ${batchIndex}/${totalBatches} 批`)
    else if (batchIndex !== null) parts.push(`第 ${batchIndex} 批`)
    parts.push(
      detailCount(details, ['batch_interfaces'], '处理 ', ' 个接口'),
      detailCount(details, ['generated_interfaces'], '成功 ', ' 个接口'),
      detailCount(details, ['generated_cases'], '生成 ', ' 个用例'),
      detailCount(details, ['failed_interfaces'], '失败 ', ' 个接口'),
    )
  }
  const summary = parts.filter(Boolean).join('，')
  const content = summary ? `${baseContent}：${summary}` : description || baseContent
  return target ? `${target}项目内，${content}` : content
}

const formatApiImportContent = (row, details) => {
  const report = details?.report && typeof details.report === 'object' ? details.report : details
  const target = formatAuditTarget(row)
  const targetPrefix = target ? (target.endsWith('项目') ? `${target}内，` : `${target}项目内，`) : ''
  const description = normalizeApiTestDescription(row?.description)
  const failed = details?.status === 'failed' || /失败/.test(description)
  const content = failed ? '接口导入失败' : '接口导入'
  const newInterfaces = getDetailNumber(report, ['new_interfaces'])
  const updatedInterfaces = getDetailNumber(report, ['updated_interfaces'])
  const newCases = getDetailNumber(report, ['new_test_cases'])
  const updatedCases = getDetailNumber(report, ['updated_test_cases'])
  const parts = [
    newInterfaces !== null || updatedInterfaces !== null
      ? `接口：新增 ${newInterfaces ?? 0} 个，更新 ${updatedInterfaces ?? 0} 个`
      : '',
    newCases !== null || updatedCases !== null
      ? `用例：新增 ${newCases ?? 0} 个，更新 ${updatedCases ?? 0} 个`
      : '',
    detailCount(report, ['new_modules'], '新增 ', ' 个模块'),
  ].filter(Boolean)
  return parts.length
    ? `${targetPrefix}${content}：${parts.join('，')}`
    : description || content
}

const formatExecutorContent = (row, details) => {
  const operation = cleanAuditText(row?.operation)
  const target = formatAuditTarget(row)
  const description = normalizeApiTestDescription(row?.description)
  // 新版执行审计由后端直接生成完整业务描述；历史记录继续沿用旧统计展示。
  if (details?.audit_content_version >= 2 && description) return description
  const content = ['调试', '接口调试'].includes(operation) ? '接口调试' : '用例运行'
  const parts = []
  if (target) parts.push(target)

  if (['调试', '接口调试'].includes(operation)) {
    const statusCode = getDetailNumber(details, ['status_code'])
    if (statusCode !== null) parts.push(`响应状态码 ${statusCode}`)
    else if (details?.status) parts.push(`结果${details.status === 'success' ? '成功' : '失败'}`)
  } else {
    const executionCount = getDetailNumber(details, ['execution_count'])
    const passed = getDetailNumber(details, ['successful_executions', 'total_passed'])
    const failed = getDetailNumber(details, ['failed_executions', 'total_failed'])
    if (executionCount !== null || passed !== null || failed !== null) {
      const count = executionCount ?? ((passed ?? 0) + (failed ?? 0))
      parts.push(`执行 ${count} 个接口`)
      if (passed !== null) parts.push(`成功 ${passed} 个接口`)
      if (failed !== null) parts.push(`失败 ${failed} 个接口`)
    }
    if (parts.length === (target ? 1 : 0) && details?.status) {
      parts.push(`结果${details.status === 'success' ? '成功' : '失败'}`)
    }
  }
  const summary = parts.filter(Boolean).join('，')
  return summary ? `${content}：${summary}` : cleanAuditText(row?.description) || content
}

/**
 * 操作内容：优先直接展示后端写入的中文描述，不再前端二次拼接目标名称。
 * 仅接口导入、历史接口导入、执行器这三类需要把详情里的统计数字汇总成一句话。
 */
export const formatAuditContent = (row, resolveAiFunctionLabel) => {
  if (row?.module === 'ai_call' && typeof resolveAiFunctionLabel === 'function') {
    const functionLabel = resolveAiFunctionLabel(row.description)
    if (functionLabel) return `${functionLabel}：${getOperationName(row.operation)}`
  }

  const details = getAuditDetails(row?.details)
  if (row?.module === 'ai_import') return formatLegacyAiImportContent(row, details)
  if (row?.module === 'api_import') return formatApiImportContent(row, details)
  if (row?.module === 'executor') return formatExecutorContent(row, details)

  const description = cleanAuditText(row?.description)
  if (description) return description

  // 后端没写描述时才兜底成「资源+操作」，仍不拼接目标名称之外的修饰词。
  const operation = getOperationName(row?.operation)
  const resource = auditResourceNames[row?.module]
  const target = formatAuditTarget(row)
  if (!operation || operation === '-') return target || resource || '-'
  const base = resource ? `${resource}${operation}` : operation
  return target && !base.includes(target) ? `${base}：${target}` : base
}
