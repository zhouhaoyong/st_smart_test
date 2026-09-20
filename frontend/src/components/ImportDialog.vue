<template>
  <el-dialog v-model="visible" title="文件导入" width="min(1320px, calc(100vw - 64px))" :top="step === 1 ? '6vh' : '4vh'" destroy-on-close :close-on-click-modal="false" class="import-dialog import-dialog-shell" :class="{ 'import-dialog-shell--compact': step === 1, 'import-dialog-shell--preview': step === 2, 'import-dialog-shell--result': step === 3 }" @closed="$emit('closed')">
    <el-steps :active="step - 1" finish-status="success" align-center class="import-steps wizard-steps-green">
      <el-step title="上传解析" />
      <el-step title="选择接口" />
      <el-step title="确认导入" />
    </el-steps>

    <div class="import-dialog-body" :class="{ 'import-dialog-body--upload': step === 1, 'import-dialog-body--preview': step === 2 }">
      <!-- Step 1: 上传文件 -->
      <div v-if="step === 1" class="step-pane upload-pane" v-loading="parsing" element-loading-text="正在解析文件，请稍候...">
        <ImportFileUpload
          :selected-file="selectedFile"
          :file-list="fileList"
          :over-size="overSize"
          :limit-label="limitLabel"
          :downloading-template="downloadingTemplate"
          @file-change="handleFileChange"
          @remove="onFileRemove"
          @download-template="downloadExcelTemplate"
        />
        <div v-if="parseErrors.length" class="parse-error-summary" role="status" aria-live="polite">
          <span>{{ parseErrors.length }} 个接口解析失败，</span>
          <el-button link type="danger" @click="openParseErrorDialog">查看详情</el-button>
        </div>

        <el-form label-width="132px" class="target-form">
          <div class="target-config-grid">
            <div class="target-config-item">
              <ImportTargetPicker
                v-model:mode="targetMode"
                v-model:collection-id="targetCollectionId"
                v-model:new-path="targetNewPath"
                :collection-tree="props.collectionTree"
                :target-collection="props.targetCollection"
                required
                class="target-config-block"
              />
            </div>
            <div class="target-config-item">
              <div class="target-config-label">服务标识（可选）</div>
              <div class="path-field">
                <ImportServiceSelect
                  v-model="defaultServiceKey"
                  size="large"
                  class="target-select"
                  :services="services"
                />
              </div>
            </div>
          </div>
          <ImportFirstStepNotice
            :project-id="props.projectId"
            :service-unavailable-tip="serviceUnavailableTip"
          />
        </el-form>
      </div>

      <!-- Step 2: 预览 -->
      <div v-else-if="step === 2" class="step-pane preview-pane">
        <div v-if="parseErrors.length" class="parse-error-summary" role="status" aria-live="polite">
          <span>{{ parseErrors.length }} 个接口解析失败，</span>
          <el-button link type="warning" @click="openParseErrorDialog">查看详情</el-button>
        </div>
        <!-- 顶部只留「模式 + 核心数字」，长说明收进问号，把纵向空间还给下方列表 -->
        <ImportModeBar v-model="importMode" :loading="duplicateChecking" :stats="duplicateSummary ? previewStats : []" />

        <!-- 过滤工具栏 -->
        <div class="preview-toolbar">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索接口名称或URL"
            clearable
            style="width: 240px"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-select v-model="filterMethod" placeholder="请求方法" clearable style="width: 120px">
            <el-option label="GET" value="GET" />
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
            <el-option label="DELETE" value="DELETE" />
            <el-option label="PATCH" value="PATCH" />
          </el-select>
          <el-button
            class="preview-toolbar-button"
            size="default"
            :disabled="selectedInterfaces.length === 0"
            @click="openBatchServiceDialog"
          >
            选择并设置服务 ({{ selectedInterfaces.length }})
          </el-button>
        </div>

        <ImportTableState
          v-if="duplicateCheckError && filteredInterfaceList.length"
          :error="duplicateCheckError"
          compact
          @retry="loadDuplicateSummary"
        />

        <el-table
          :data="filteredInterfaceList"
          height="min(56vh, 560px)"
          class="import-preview-table import-table-scroll"
          v-loading="duplicateChecking"
          @selection-change="handleSelectionChange"
          :row-key="(row) => row._originalIndex"
        >
          <ImportInterfaceCommonColumns :services="services" @open-detail="showInterfaceDetail">
            <template #level1="{ row }">
              <!-- 已存在的接口不给改目录：这次导入只更新它的定义，位置一律保持原样 -->
              <el-tooltip v-if="isExistingRow(row)" :content="existingLocationTip(row)" placement="top">
                <span class="row-locked-text">保持原位</span>
              </el-tooltip>
              <el-select
                v-else
                v-model="row.level1_name"
                placeholder="选择或输入"
                size="small"
                filterable
                allow-create
                default-first-option
                style="width: 100%"
              >
                <el-option v-for="col in level1Collections" :key="col.id" :label="col.name" :value="col.name" />
              </el-select>
            </template>
            <template #level2="{ row }">
              <span v-if="isExistingRow(row)" class="row-locked-text">—</span>
              <el-select
                v-else
                v-model="row.level2_name"
                placeholder="选择或输入"
                size="small"
                filterable
                allow-create
                default-first-option
                style="width: 100%"
                :disabled="!row.level1_name"
              >
                <el-option v-for="col in getLevel2Collections(row.level1_name)" :key="col.id" :label="col.name" :value="col.name" />
              </el-select>
            </template>
          </ImportInterfaceCommonColumns>

          <el-table-column v-if="duplicateSummary" label="本次调整" width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag v-if="rowStatusOf(row) === 'new'" type="success" size="small">新增</el-tag>
              <el-tag v-else-if="rowStatusOf(row) === 'duplicate'" type="info" size="small">无变化，不导入</el-tag>
              <span v-else class="change-reason-text">{{ changeLabelOf(row) }}</span>
            </template>
          </el-table-column>

          <template #empty>
            <ImportTableState :empty-text="emptyStateText" :error="duplicateCheckError" @retry="loadDuplicateSummary" />
          </template>
        </el-table>
      </div>

      <!-- Step 3: 导入报告 -->
      <div v-else class="step-pane result-pane">
        <el-result :icon="hasChanges ? 'success' : 'info'" :title="hasChanges ? (createdCases ? '导入接口 + 生成用例完成' : '导入接口完成') : noChangeTitle">
          <template #sub-title>
            <ImportResultSummary :stats="importResultStats">
              <div v-if="unchangedTip">{{ unchangedTip }}</div>
            </ImportResultSummary>
          </template>
        </el-result>
      </div>
    </div>

    <template #footer>
      <ImportDialogFooter v-if="step === 2">
        <el-button @click="visible = false">关闭</el-button>
        <el-button @click="step = 1">上一步</el-button>
        <el-button type="primary" @click="handleExecute(false)" :loading="executing === 'interface'" :disabled="duplicateChecking || importableInterfaceList.length === 0">导入接口</el-button>
        <el-button type="primary" @click="handleExecute(true)" :loading="executing === 'case'" :disabled="duplicateChecking || importableInterfaceList.length === 0">导入接口 + 生成用例</el-button>
      </ImportDialogFooter>
      <ImportDialogFooter v-else-if="step === 1">
        <el-button @click="visible = false">关闭</el-button>
        <el-button
          type="primary"
          :loading="parsing"
          :disabled="!selectedFile || overSize || !targetReady"
          @click="handleParseFile"
        >
          解析并下一步
        </el-button>
      </ImportDialogFooter>
      <ImportDialogFooter v-else>
        <el-button type="primary" @click="$emit('done')">完成</el-button>
      </ImportDialogFooter>
    </template>
  </el-dialog>

  <el-dialog
    v-model="parseErrorDialogVisible"
    title="解析失败接口"
    width="min(860px, calc(100vw - 64px))"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    class="parse-error-dialog"
  >
    <el-alert
      :title="`共 ${parseErrors.length} 个接口请求体解析失败，这些接口不会提交导入`"
      type="warning"
      :closable="false"
      show-icon
    />
    <el-table :data="parseErrors" max-height="min(52vh, 480px)" border stripe class="parse-error-table">
      <el-table-column type="index" label="#" width="60" />
      <el-table-column prop="name" label="接口名称" min-width="220" show-overflow-tooltip />
      <el-table-column prop="module" label="所属模块" min-width="160" show-overflow-tooltip />
      <el-table-column prop="reason" label="失败原因" min-width="220" show-overflow-tooltip />
    </el-table>
    <template #footer>
      <el-button type="primary" @click="parseErrorDialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>

  <InterfaceDetailDialog
    v-model="detailDialogVisible"
    :interface-data="currentInterface"
    :readonly="true"
    :show-info="false"
    @debug-interface="$emit('debug-interface', $event)"
  />

  <ImportBatchServiceDialog v-model="batchServiceDialogVisible" :services="services" @confirm="applyBatchService" />
</template>

<script setup>
import { ref, watch, computed, nextTick, inject } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { parseImportFile, checkImportDuplicates, executeImport, downloadImportExcelTemplate } from '@/api/import'
import { getCollections } from '@/api/collections'
import {
  buildImportModeStats,
  isImportTargetReady,
  splitCollectionPathInput,
} from '@/utils/interfaceCollections'
import InterfaceDetailDialog from './InterfaceDetailDialog.vue'
import ImportResultSummary from './ImportResultSummary.vue'
import ImportTargetPicker from './ImportTargetPicker.vue'
import ImportBatchServiceDialog from './ImportBatchServiceDialog.vue'
import ImportFileUpload from './ImportFileUpload.vue'
import ImportInterfaceCommonColumns from './ImportInterfaceCommonColumns.vue'
import ImportModeBar from './ImportModeBar.vue'
import ImportServiceSelect from './ImportServiceSelect.vue'
import ImportTableState from './ImportTableState.vue'
import ImportDialogFooter from './ImportDialogFooter.vue'
import ImportFirstStepNotice from './ImportFirstStepNotice.vue'

const props = defineProps({
  modelValue: Boolean,
  projectId: [Number, String],
  services: { type: Array, default: () => [] },
  targetCollection: { type: Object, default: null },
  collectionTree: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'done', 'closed', 'debug-interface', 'result-ready'])
const selectedEnvironment = inject('selectedEnvironment', computed(() => null))

// 导入目标：第一步选定，后面各步只回显，避免用户在两个地方各选一次
const targetMode = ref('existing')
const targetCollectionId = ref(null)
const targetNewPath = ref('')
// 第一步选的服务标识：作为解析出来的接口的默认服务，第二步可逐条或批量改。
const defaultServiceKey = ref(null)
const serviceUnavailableTip = computed(() => {
  const env = selectedEnvironment.value
  if (!env) return '当前未选择运行环境，仍可手动填写服务标识；运行时将按实际选择的环境解析。'
  const items = env.service_config?.items || []
  if (!items.length) return '当前环境尚未配置服务，可继续填写服务标识；运行时将按基础地址请求。'
  if (env.service_config?.enabled === false) return '当前环境服务配置未开启，可继续填写服务标识；运行时将按基础地址请求。'
  if (!items.some(item => item?.enabled === true && item?.path_prefix)) {
    return '当前环境没有可用于自动识别的服务，可继续填写服务标识。'
  }
  return ''
})
const targetReady = computed(() => isImportTargetReady({
  mode: targetMode.value,
  collectionId: targetCollectionId.value,
  newPath: targetNewPath.value,
}))

const visible = ref(false)
watch(() => props.modelValue, v => {
  if (v) { 
    reset()
    loadCollections()
    nextTick(() => visible.value = true) 
  }
  else { visible.value = false }
})
watch(visible, v => emit('update:modelValue', v))

const step = ref(1)
const selectedFile = ref(null)
const fileList = ref([])
const parsing = ref(false)
const downloadingTemplate = ref(false)
const executing = ref(null)
const createdCases = ref(false)
const parseResult = ref(null)
const parseErrors = ref([])
const parseErrorDialogVisible = ref(false)
const sourceName = ref('')
const report = ref(null)
// 导入模式由后端判重接口决定返回范围，落库口径两种模式完全一致：
// 新增导入、有变化更新、无变化跳过。
const importMode = ref('full')
// 扁平化的接口列表
const flatInterfaceList = ref([])
// 判重结果由后端按当前导入模式返回；切换模式会重新请求，不在前端重新分类
const duplicateSummary = ref(null)
const duplicateCheckError = ref('')
// 判重结论按行的稳定标识对回每一行（_originalIndex），不要改用目录名拼键：
// 用户在预览页改目录后就对不上了，历史上这正是「改完目录整行消失」的来源
const statusByRow = ref(new Map())
const duplicateChecking = ref(false)
let duplicateRequestSequence = 0

const JSON_YAML_LIMIT = 10 * 1024 * 1024
const XLSX_LIMIT = 20 * 1024 * 1024
const limitFor = (name) => (/\.xlsx$/i.test(name || '') ? XLSX_LIMIT : JSON_YAML_LIMIT)
const currentLimit = computed(() => limitFor(selectedFile.value?.name))
const limitLabel = computed(() => `${currentLimit.value / (1024 * 1024)}MB`)
const overSize = computed(() => !!selectedFile.value && selectedFile.value.size > currentLimit.value)

const downloadExcelTemplate = async () => {
  downloadingTemplate.value = true
  try {
    const blob = await downloadImportExcelTemplate()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'API接口清单导入模板.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } finally {
    downloadingTemplate.value = false
  }
}

// 过滤和选择
const searchKeyword = ref('')
const filterMethod = ref('')
const selectedInterfaces = ref([])
const batchServiceDialogVisible = ref(false)

const openBatchServiceDialog = () => {
  if (!selectedInterfaces.value.length) {
    ElMessage.warning('请先选择接口')
    return
  }
  batchServiceDialogVisible.value = true
}

const applyBatchService = (serviceKey) => {
  if (!selectedInterfaces.value.length) {
    ElMessage.warning('请先选择接口')
    return
  }
  selectedInterfaces.value.forEach(item => { item.service_key = serviceKey })
  batchServiceDialogVisible.value = false
}

// 详情弹窗
const detailDialogVisible = ref(false)
const currentInterface = ref(null)

// 接口集列表（用于目录选择）
const allCollections = ref([])
const level1Collections = computed(() => {
  // 返回所有一级接口集（parent_id 为 null）
  return allCollections.value.filter(col => col.parent_id === null)
})

// 获取指定一级目录下的二级目录
const getLevel2Collections = (level1Name) => {
  if (!level1Name) return []
  // 找到一级目录的 ID
  const level1Col = allCollections.value.find(col => col.name === level1Name && col.parent_id === null)
  if (!level1Col) return []
  // 返回该一级集下的所有子接口集
  return allCollections.value.filter(col => col.parent_id === level1Col.id)
}

const hasChanges = computed(() => {
  const r = report.value?.report
  return r && (r.new_modules || r.new_interfaces || r.updated_interfaces || r.new_test_cases || r.updated_test_cases)
})
// 两种模式的落库口径一致，没东西可导入只会是「文档与平台完全一致」这一种情况
const noChangeTitle = '文档与平台上完全一致，没有需要导入的接口'
const unchangedTip = computed(() => {
  const count = report.value?.report?.unchanged_interfaces || 0
  return count ? `另有 ${count} 个接口与平台上完全一致，未导入` : ''
})
const importResultStats = computed(() => {
  const r = report.value?.report || {}
  return [
    { key: 'new_modules', label: '新增接口集', value: r.new_modules || 0, unit: '个' },
    { key: 'new_interfaces', label: '新增接口', value: r.new_interfaces || 0, unit: '个' },
    { key: 'updated_interfaces', label: '更新接口', value: r.updated_interfaces || 0, unit: '个' },
    { key: 'new_test_cases', label: '新增用例', value: r.new_test_cases || 0, unit: '个' },
    { key: 'updated_test_cases', label: '更新用例', value: r.updated_test_cases || 0, unit: '个' },
  ]
})

const rowDedupItem = (row) => statusByRow.value.get(row?._originalIndex)
const rowStatusOf = (row) => rowDedupItem(row)?.status || ''
const isExistingRow = (row) => {
  const status = rowStatusOf(row)
  return status === 'changed' || status === 'duplicate'
}
const existingLocationTip = (row) => {
  const name = rowDedupItem(row)?.existing_collection_name
  return name
    ? `平台上已经有这个接口，放在「${name}」，这次导入只更新它的定义，不会换位置`
    : '平台上已经有这个接口，这次导入只更新它的定义，不会换位置'
}

// 这一行本次会不会落库：新增导入、有变化更新、无变化一律跳过（两种模式一致）
const isRowImportable = (row) => rowStatusOf(row) !== 'duplicate'

// 本次真正会落库的接口，用于按钮可用状态与执行前校验
const importableInterfaceList = computed(() => {
  if (!duplicateSummary.value) return flatInterfaceList.value
  if (importMode.value === 'incremental') return visibleInterfaceList.value
  return flatInterfaceList.value.filter(isRowImportable)
})

// 列表展示范围由后端判重结果决定：增量响应只包含新增和有变化的行。
// 预检没成功时退回全部展示，不挡住导入
const visibleInterfaceList = computed(() => {
  if (!duplicateSummary.value) return flatInterfaceList.value
  if (importMode.value === 'incremental') {
    return flatInterfaceList.value.filter(row => statusByRow.value.has(row._originalIndex))
  }
  return flatInterfaceList.value
})

const changeLabelOf = (row) => {
  const item = rowDedupItem(row)
  if (!item) return ''
  if (item.status === 'new') return '新增'
  return item.change_summary || '有变化'
}

// 统计直接使用后端判重结果，避免前端根据行数据重新推导业务分类
const dedupCounts = computed(() => {
  const summary = duplicateSummary.value
  return {
    new: Number(summary?.new_count || 0),
    changed: Number(summary?.changed_count || 0),
    duplicate: Number(summary?.duplicate_count || 0),
  }
})

// 顶部只报核心数字：共解析多少、本次新增多少、有变化多少、无变化不导入多少
const previewStats = computed(() => {
  const { new: newCount, changed, duplicate } = dedupCounts.value
  return buildImportModeStats({
    newCount,
    changedCount: changed,
    unchangedCount: duplicate,
  })
})

const emptyStateText = computed(() => {
  if (!duplicateSummary.value) return '暂无数据'
  const { duplicate } = dedupCounts.value
  if (duplicate) {
    return `这份文档与平台上的接口完全一致，${duplicate} 个接口都已存在且没有任何变化，不会导入，也不会创建用例。`
  }
  return '暂无数据'
})

// 过滤后的接口列表
const filteredInterfaceList = computed(() => {
  let list = visibleInterfaceList.value

  // 关键词过滤
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    list = list.filter(item => 
      item.name.toLowerCase().includes(keyword) || 
      item.url.toLowerCase().includes(keyword)
    )
  }
  
  // 方法过滤
  if (filterMethod.value) {
    list = list.filter(item => item.method === filterMethod.value)
  }
  
  return list
})

const handleFileChange = (file) => {
  selectedFile.value = file.raw
  fileList.value = [file]
  parseErrors.value = []
  parseErrorDialogVisible.value = false
}

const onFileRemove = () => {
  selectedFile.value = null
  fileList.value = []
  parseErrors.value = []
  parseErrorDialogVisible.value = false
}

const openParseErrorDialog = () => {
  if (parseErrors.value.length) parseErrorDialogVisible.value = true
}

// 加载接口集列表
const loadCollections = async () => {
  if (!props.projectId) return
  try {
    const collections = await getCollections(props.projectId)
    allCollections.value = collections || []
  } catch (e) {
    console.error('加载接口集失败', e)
    allCollections.value = []
  }
}

const handleParseFile = async () => {
  if (!selectedFile.value) { ElMessage.warning('请选择文件'); return }
  if (overSize.value) { ElMessage.warning(`文件大小不能超过 ${limitLabel.value}`); return }
  parsing.value = true
  try {
    const result = await parseImportFile(selectedFile.value)
    parseResult.value = result
    parseErrors.value = Array.isArray(result?.failed_interfaces) ? result.failed_interfaces : []
    sourceName.value = selectedFile.value.name.replace(/\.(json|yaml|yml|xlsx)$/i, '')
    
    // 将模块化数据转换为扁平化列表
    flatInterfaceList.value = []
    ;(result?.modules || []).forEach((mod, modIdx) => {
      ;(mod.interfaces || []).forEach((iface, ifaceIdx) => {
        // 如果只有一级目录（level2_name 为空），则保持 level1_name，level2_name 留空
        // 如果只有二级目录（level1_name 为空），则将 level2_name 作为 level1_name
        let finalLevel1 = mod.level1_name || ''
        let finalLevel2 = mod.level2_name || ''
        
        // 如果一级为空但二级有值，说明只解析出一层，将其作为一级
        if (!finalLevel1 && finalLevel2) {
          finalLevel1 = finalLevel2
          finalLevel2 = ''
        }
        
        flatInterfaceList.value.push({
          ...iface,
          // 服务标识用第一步选的默认值，接口地址按文档原样保留（运行时由环境按服务解析）
          service_key: defaultServiceKey.value || null,
          level1_name: finalLevel1,
          level2_name: finalLevel2,
          pre_script: iface.pre_script || '',
          post_script: iface.post_script || '',
          _originalIndex: `${modIdx}-${ifaceIdx}` // 用于追踪原始位置
        })
      })
    })
    if (!flatInterfaceList.value.length) {
      duplicateSummary.value = null
      statusByRow.value = new Map()
      return
    }
    await loadDuplicateSummary()
    step.value = 2
  } catch (e) {
    console.error('解析失败', e)
  }
  finally { parsing.value = false }
}

// 判重预检与真正执行必须用同一份分组，否则预览说的和落库做的对不上。
// rowOrder 按「模块 → 接口」的遍历顺序摊平行标识，与后端给每条结论编号的顺序一致。
const buildModulesForImport = () => {
  const modulesMap = new Map()
  const rowIdsMap = new Map()
  flatInterfaceList.value.forEach(iface => {
    const key = `${iface.level1_name || ''}::${iface.level2_name || ''}`
    if (!modulesMap.has(key)) {
      modulesMap.set(key, {
        level1_name: iface.level1_name || '',
        level2_name: iface.level2_name || '',
        interfaces: [],
      })
      rowIdsMap.set(key, [])
    }
    // 移除临时字段，只保留接口数据
    const { _originalIndex, ...ifaceData } = iface
    modulesMap.get(key).interfaces.push(ifaceData)
    rowIdsMap.get(key).push(_originalIndex)
  })
  const modules = Array.from(modulesMap.values()).map(module => ({
    ...module,
    use_global_level1: true,
    level2_name: module.level2_name || module.level1_name || '',
  }))
  const rowOrder = Array.from(modulesMap.keys()).flatMap(key => rowIdsMap.get(key))
  return { modules, rowOrder }
}

const loadDuplicateSummary = async () => {
  const requestId = ++duplicateRequestSequence
  const { modules, rowOrder } = buildModulesForImport()
  if (!modules.length) {
    duplicateSummary.value = null
    duplicateCheckError.value = ''
    statusByRow.value = new Map()
    duplicateChecking.value = false
    return
  }
  duplicateChecking.value = true
  duplicateCheckError.value = ''
  try {
    const data = await checkImportDuplicates({
      project_id: parseInt(props.projectId),
      selected_modules: modules,
      import_mode: importMode.value,
    })
    if (requestId !== duplicateRequestSequence) return
    const map = new Map()
    ;(data?.items || []).forEach(item => {
      const rowId = rowOrder[item.index]
      if (rowId !== undefined) map.set(rowId, item)
    })
    statusByRow.value = map
    duplicateSummary.value = data || null
  } catch (e) {
    if (requestId !== duplicateRequestSequence) return
    duplicateSummary.value = null
    statusByRow.value = new Map()
    duplicateCheckError.value = e?.data?.message || e?.message || '判重失败，请重新加载'
    // 预检失败不挡住导入，退回"全部展示"，由执行结果兜底
    console.error('判重预检失败', e)
  } finally {
    if (requestId === duplicateRequestSequence) duplicateChecking.value = false
  }
}

watch(importMode, (next, previous) => {
  if (next === previous || !flatInterfaceList.value.length) return
  loadDuplicateSummary()
})

const showInterfaceDetail = (iface) => {
  currentInterface.value = iface
  detailDialogVisible.value = true
}

const handleSelectionChange = (selection) => {
  selectedInterfaces.value = selection
}

const handleExecute = async (withCases) => {
  if (duplicateChecking.value) return
  if (importableInterfaceList.value.length === 0) {
    ElMessage.warning('没有需要导入的接口')
    return
  }
  if (!targetReady.value) {
    ElMessage.warning('请先选择导入到哪个接口集')
    return
  }

  executing.value = withCases ? 'case' : 'interface'
  createdCases.value = withCases
  try {
    const { modules: modulesForImport } = buildModulesForImport()

    report.value = await executeImport({
      project_id: parseInt(props.projectId),
      source: sourceName.value || `import_${Date.now()}`,
      selected_modules: modulesForImport,
      create_test_cases: withCases,
      import_mode: importMode.value,
      // 两种模式落库口径一致：有变化的已有接口一律原地更新
      overwrite_existing: true,
      global_level1_collection_id: targetMode.value === 'new' ? null : targetCollectionId.value,
      global_level1_path: targetMode.value === 'new'
        ? splitCollectionPathInput(targetNewPath.value)
        : [],
    })
    step.value = 3
    emit('result-ready')
  } catch (e) {
    console.error('导入失败', e)
  }
  finally { executing.value = null }
}

const reset = () => {
  duplicateRequestSequence += 1
  duplicateChecking.value = false
  step.value = 1
  // 左侧已选中接口集时默认带出来，用户仍可改
  targetMode.value = 'existing'
  targetCollectionId.value = props.targetCollection?.id || null
  targetNewPath.value = ''
  defaultServiceKey.value = null
  selectedFile.value = null
  fileList.value = []
  parseResult.value = null
  parseErrors.value = []
  parseErrorDialogVisible.value = false
  flatInterfaceList.value = []
  duplicateSummary.value = null
  duplicateCheckError.value = ''
  statusByRow.value = new Map()
  report.value = null
  importMode.value = 'full'
  executing.value = null
  createdCases.value = false
  searchKeyword.value = ''
  filterMethod.value = ''
  batchServiceDialogVisible.value = false
  selectedInterfaces.value = []
  currentInterface.value = null
  detailDialogVisible.value = false
  allCollections.value = []
}

defineExpose({ reset })
</script>

<style scoped>
.target-path-trigger {
  margin-left: 0;
  padding: 0;
  height: auto;
  font-size: 13px;
  vertical-align: baseline;
}
.change-reason-text {
  font-size: 13px;
  color: var(--el-color-warning);
}
/* 已有接口的目录不可改，置灰表明这一格不是输入项 */
.row-locked-text {
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}

.import-preview-table {
  margin-bottom: 0;
}

/* 保持文件导入步骤、上传和底部操作节奏 */
.import-steps { margin-bottom: 16px; }
.import-dialog-body { min-height: 420px; }
/* 第一步按实际高度展示，不撑空白 */
.import-dialog-body--upload { min-height: 0; }
:global(.import-dialog-shell--result) .import-dialog-body { min-height: 0; }
.step-pane { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.upload-pane { align-items: center; width: 100%; gap: 14px; }
/* 第一步配置区：两列网格 */
.target-form { align-self: center; width: 100%; }
.target-select { width: 100%; }
.target-config-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-bottom: 18px; }
.target-config-item { min-width: 0; }
.target-config-label { margin-bottom: 8px; color: var(--el-text-color-regular); font-size: 14px; line-height: 20px; }
.target-config-block { width: 100%; }
.path-field { width: 100%; }
.preview-pane { min-height: 0; }
.parse-error-summary {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 4px;
  min-width: 0;
  width: 100%;
  min-height: 32px;
  padding: 6px 12px;
  border: 1px solid var(--el-color-warning-light-5);
  border-radius: 4px;
  background: var(--el-color-warning-light-9);
  color: var(--el-color-warning);
  font-size: 13px;
}
.parse-error-summary :deep(.el-button) { flex: none; }
.parse-error-dialog :deep(.el-dialog__body) {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: calc(100vh - 220px);
  overflow: hidden;
}
.parse-error-table { min-height: 0; }
/* 模式 + 核心数字压成一行，长说明进问号，纵向空间留给列表 */
.preview-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.preview-toolbar .el-input { width: 240px; }
.preview-toolbar .el-select { width: 120px; }
.preview-toolbar-button { height: 32px; white-space: nowrap; }
.result-pane { min-height: 0; padding: 24px 0 12px; justify-content: center; }

@media (max-width: 900px) {
  .target-config-grid { grid-template-columns: 1fr; gap: 12px; }
}

/* 代码编辑器样式 */
.code-editor :deep(.el-textarea__inner) {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
}

/* 表格中的下拉框样式优化 */
:deep(.el-table .el-select) {
  width: 100%;
}

:deep(.el-table .el-select .el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--el-input-border-color, var(--el-border-color)) inset;
}

:deep(.el-table .el-select:hover .el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--el-input-hover-border-color, var(--el-border-color-hover)) inset;
}

:deep(.el-table .el-select.is-focus .el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--el-input-focus-border-color, var(--el-color-primary)) inset;
}

/* 弹窗：步骤条固定，正文区域独立滚动，底部按钮始终可见 */
:global(.import-dialog) {
  max-width: 1320px;
}
:global(.import-dialog .el-dialog__footer) { display: flex; justify-content: flex-end; }
.import-dialog :deep(.el-result__subtitle) { width: 100%; }

@media (max-width: 720px) {
  .preview-toolbar .el-input { width: min(100%, 240px); }
  .preview-toolbar .el-select { width: 120px; }
}
</style>
