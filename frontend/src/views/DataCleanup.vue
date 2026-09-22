<template>
  <div class="page-wrap">
    <div class="admin-page-title"><h2>平台数据管理</h2></div>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" class="load-error" />

    <div class="scroll-area cleanup-scroll-area">
      <el-card class="config-card">
      <template #header>
        <div class="card-header">
          <span>清理配置</span>
        </div>
      </template>
      
      <!-- 模式选择 -->
      <el-radio-group v-model="configForm.mode" @change="handleModeChange" style="margin-bottom: 20px">
        <el-radio value="datetime">按时间清理</el-radio>
        <el-radio value="days">按天数清理</el-radio>
      </el-radio-group>
      
      <el-form :model="configForm" label-width="120px">
        <!-- 按时间模式 -->
        <el-form-item v-if="configForm.mode === 'datetime'" label="截止时间">
          <el-date-picker
            v-model="configForm.cutoff"
            type="datetime"
            placeholder="选择截止时间"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DDTHH:mm:ss"
            :clearable="false"
            style="width: 280px"
          />
          <span class="form-tip">将清理该时间点之前 (deleted_at &lt;= 选择时间) 的所有软删除数据</span>
        </el-form-item>
        
        <!-- 按天模式 -->
        <el-form-item v-else label="清理天数">
          <el-input-number 
            v-model="configForm.days" 
            :min="0" 
            :max="365"
            style="width: 200px"
          />
          <span class="form-tip">
            {{ configForm.days === 0 ? '⚠️ 0表示清理所有历史软删除数据（非常危险！）' : `清理 ${configForm.days} 天之前被软删除的数据` }}
          </span>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handlePreview" :loading="previewLoading" :disabled="!isConfigValid">
            预览可清理数据
          </el-button>
          <el-button type="danger" :icon="Delete" @click="handleCleanup" :loading="cleanupLoading" :disabled="!isConfigValid || !isPreviewCurrent || previewData.total_tables === 0">
            执行查询范围清理
          </el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
      
      <!-- 提示说明 -->
      <el-alert
        title="清理规则说明"
        type="info"
        :closable="false"
        style="margin-top: 16px"
      >
        <template #default>
          <div style="line-height: 1.8">
            • 清理条件：<code>is_deleted = 1 AND deleted_at IS NOT NULL AND deleted_at &lt;= 选择的截止时间</code><br/>
            • 此操作为物理删除，无法恢复，请谨慎操作<br/>
            • 仅超级管理员可执行<br/>
            • 支持单表清理和查询范围清理两种方式
          </div>
        </template>
      </el-alert>
    </el-card>

    <!-- 预览结果 -->
    <el-card v-if="previewData" class="preview-card" v-loading="previewLoading">
      <template #header>
        <div class="card-header">
          <span>预览结果</span>
          <el-tag type="info">{{ filteredTables.length }} 个表</el-tag>
        </div>
      </template>
      
      <div v-if="filteredTables.length > 0">
        <!-- 搜索框 -->
        <div style="margin-bottom: 16px; display: flex; gap: 12px; align-items: center">
          <el-input
            v-model="searchKeyword.tableName"
            placeholder="搜索表名（英文）..."
            :prefix-icon="Search"
            clearable
            style="max-width: 280px"
            @keyup.enter="handleSearch"
          />
          <el-input
            v-model="searchKeyword.chineseName"
            placeholder="搜索中文名称..."
            :prefix-icon="Search"
            clearable
            style="max-width: 280px"
            @keyup.enter="handleSearch"
          />
          <el-button type="primary" :icon="Search" @click="handleSearch" :loading="previewLoading">搜索</el-button>
          <el-button :icon="Refresh" @click="handleResetSearch">重置</el-button>
        </div>
        
        <el-table
          :data="filteredTables"
          stripe
          style="width:100%"
          class="cleanup-preview-table"
          header-cell-class-name="no-wrap-header"
          @row-click="handleTableRowClick"
        >
          <el-table-column type="index" label="#" width="60" />
          <el-table-column prop="table_name" label="表名" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <el-link type="primary" underline="never" @click.stop="viewTableData(row.table_name)">
                <el-tag size="small" effect="plain">{{ row.table_name }}</el-tag>
              </el-link>
            </template>
          </el-table-column>
          <el-table-column label="中文名称" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <el-link 
                type="primary" 
                underline="never" 
                @click.stop="viewTableData(row.table_name)"
                style="color: #606266; font-weight: 500"
              >
                {{ row.chinese_name || '' }}
              </el-link>
            </template>
          </el-table-column>
          <el-table-column prop="pending_count" label="待清理数据" width="150" align="center">
            <template #default="{ row }">
              <el-link type="primary" underline="never" @click.stop="viewTableData(row.table_name)">
                <el-tag v-if="row.pending_count > 0" type="danger" effect="dark">
                  {{ row.pending_count }} 条
                </el-tag>
                <el-tag v-else type="info">
                  0 条
                </el-tag>
              </el-link>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" align="center" fixed="right" class-name="cleanup-action-cell">
            <template #default="{ row }">
              <el-button 
                size="small" 
                type="primary" 
                link 
                @click.stop="viewTableData(row.table_name)"
              >
                查看详情
              </el-button>
              <el-button 
                size="small" 
                type="danger" 
                link 
                @click.stop="handleDeleteSingleTable(row)"
                :disabled="row.pending_count === 0 || singleDeleteLoading === row.table_name"
                :loading="singleDeleteLoading === row.table_name"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      
      <el-empty v-else description="没有找到匹配的表" />
    </el-card>

    <!-- 清理结果 -->
    <el-card v-if="cleanupResult" class="result-card">
      <template #header>
        <div class="card-header">
          <span>清理结果</span>
          <el-tag :type="cleanupResult.success ? 'success' : 'danger'">
            {{ cleanupResult.success ? '成功' : '失败' }}
          </el-tag>
        </div>
      </template>
      
      <el-descriptions :column="2" border>
        <el-descriptions-item label="清理状态">
          <el-tag :type="cleanupResult.success ? 'success' : 'danger'">
            {{ cleanupResult.success ? '成功' : '失败' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="截止时间">
          {{ cleanupResult.cutoff_time ? formatDate(cleanupResult.cutoff_time) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="清理表数量">
          {{ cleanupResult.tables_cleaned }}
        </el-descriptions-item>
        <el-descriptions-item label="总记录数">
          <el-tag type="danger" effect="dark">{{ cleanupResult.total_records_deleted }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <div v-if="cleanupResult.details && cleanupResult.details.length > 0" style="margin-top: 20px">
        <h4>详细清理记录</h4>
        <el-table :data="cleanupResult.details" stripe style="width:100%; margin-top: 10px" class="cleanup-result-table" header-cell-class-name="no-wrap-header">
          <el-table-column prop="table" label="表名" width="200">
            <template #default="{ row }">
              <el-tag size="small">{{ row.table }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="records_deleted" label="清理记录数" width="150">
            <template #default="{ row }">
              <span v-if="row.records_deleted > 0" style="color: #f56c6c; font-weight: 600">
                {{ row.records_deleted }}
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="cutoff_time" label="截止时间" />
          <el-table-column prop="error" label="错误信息" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.error" style="color: #f56c6c">{{ row.error }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <div class="empty-state" v-if="!previewData && !cleanupResult">
      <el-icon :size="48" color="#bfbfbf"><Document /></el-icon>
      <p>请配置清理参数后点击"预览可清理数据"</p>
    </div>
    </div>

    <!-- 清理过程弹窗 -->
    <el-dialog 
      v-model="cleanupDialogVisible" 
      :title="cleanupDialogTitle" 
      width="450px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <div v-loading="cleanupDialogLoading" style="min-height: 100px; padding: 20px 0; text-align: center">
        <template v-if="!cleanupDialogLoading">
          <div v-if="cleanupDialogResult?.success" style="color: #67c23a; font-size: 16px; font-weight: 500">
            {{ cleanupDialogResult.message }}
          </div>
          <div v-else style="color: #f56c6c; font-size: 16px; font-weight: 500">
            {{ cleanupDialogResult?.error || '操作失败' }}
          </div>
        </template>
        <div v-else style="color: #909399">
          {{ cleanupDialogLoadingText }}
        </div>
      </div>
      
      <template #footer>
        <el-button 
          v-if="!cleanupDialogLoading" 
          type="primary" 
          @click="cleanupDialogVisible = false"
        >
          知道了
        </el-button>
      </template>
    </el-dialog>

    <!-- 待清理数据详情弹窗 -->
    <el-dialog 
      v-model="tableDataDialogVisible" 
      :title="`${currentTableChineseName ? `${currentTableChineseName}（${currentTableName}）` : currentTableName} - 清理详情`"
      width="90%"
      :close-on-click-modal="false"
    >
      <div v-loading="tableDataLoading">
        <el-alert
          v-if="tableDataInfo"
          :title="`共有 ${tableDataInfo.total_count} 条待清理数据（显示前100条样本）`"
          type="warning"
          :closable="false"
          style="margin-bottom: 16px"
        />
        
        <el-tabs v-if="tableDataInfo" v-model="tableDataTab" class="cleanup-detail-tabs">
          <el-tab-pane label="待清理数据" name="data">
            <div v-if="tableDataInfo.sample_data.length > 0">
              <el-table :data="tableDataInfo.sample_data" stripe max-height="500" style="width:100%" class="cleanup-sample-table" header-cell-class-name="no-wrap-header">
                <el-table-column
                  v-for="col in visibleColumns"
                  :key="col.key"
                  :prop="col.key"
                  min-width="120"
                  show-overflow-tooltip
                >
                  <template #header>
                    <div class="cleanup-column-header">
                      <span>{{ col.label }}</span>
                    </div>
                  </template>
                  <template #default="{ row }">
                    <span v-if="row[col.key] === null || row[col.key] === undefined" style="color: #909399">-</span>
                    <span v-else>{{ formatCellValue(row[col.key]) }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <el-empty v-else description="暂无待清理数据" />
          </el-tab-pane>
          <el-tab-pane v-if="tableDataInfo.relations?.length" label="关联关系" name="relations">
            <el-table :data="tableDataInfo.relations" stripe border max-height="500" style="width:100%" class="cleanup-relation-table" header-cell-class-name="no-wrap-header">
              <el-table-column prop="direction" label="关系方向" width="110" />
              <el-table-column label="关联表" min-width="220" show-overflow-tooltip>
                <template #default="{ row }">
                  <span>{{ row.related_chinese_name || '关联表' }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="related_count" label="影响数量" width="110" align="center" />
              <el-table-column label="处理方式" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">
                  <el-tag :type="row.action === '可级联删除子数据' ? 'warning' : row.action === '优先清理子表' ? 'success' : 'info'" size="small">
                    {{ row.action }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </div>
      
      <template #footer>
        <el-button @click="tableDataDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { previewCleanup, previewTableData, cleanupData, cleanupSingleTable } from '@/api/cleanup'
import { Search, Delete, Refresh, Document } from '@element-plus/icons-vue'
import { formatBeijingTime } from '@/utils/beijingTime'

const configForm = reactive({
  mode: 'datetime',  // datetime 或 days
  cutoff: formatBeijingTime(new Date()).replace(' ', 'T'),  // 默认当前北京时间
  days: 7
})

const previewLoading = ref(false)
const cleanupLoading = ref(false)
const singleDeleteLoading = ref(null)  // 存储正在删除的表名
const previewData = ref(null)
const previewQuery = ref(null)
const cleanupResult = ref(null)
const errorMessage = ref('')

// 清理过程弹窗
const cleanupDialogVisible = ref(false)
const cleanupDialogTitle = ref('')
const cleanupDialogLoading = ref(false)
const cleanupDialogLoadingText = ref('')
const cleanupDialogResult = ref(null)

// 表数据详情弹窗
const tableDataDialogVisible = ref(false)
const tableDataLoading = ref(false)
const currentTableName = ref('')
const tableDataInfo = ref(null)
const tableDataTab = ref('data')

// 搜索关键词（分成表名和中文名称）
const searchKeyword = reactive({
  tableName: '',
  chineseName: ''
})

const formatDate = (d) => d ? formatBeijingTime(d) : '-'

const currentTableChineseName = computed(() => tableDataInfo.value?.chinese_name || '')

// 计算可见列（排除软删除控制列，最多显示10列）
const visibleColumns = computed(() => {
  if (!tableDataInfo.value) return []
  return tableDataInfo.value.display_columns || []
})

const formatCellValue = (value) => {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

// 配置是否有效
const isConfigValid = computed(() => {
  if (configForm.mode === 'datetime') {
    return !!configForm.cutoff
  } else {
    return configForm.days >= 0
  }
})

const getCurrentPreviewQuery = () => ({
  mode: configForm.mode,
  cutoff: configForm.mode === 'datetime' ? configForm.cutoff : null,
  days: configForm.mode === 'days' ? Number(configForm.days) : null,
  tableName: searchKeyword.tableName?.trim() || '',
  chineseName: searchKeyword.chineseName?.trim() || '',
})

const isPreviewCurrent = computed(() => {
  if (!previewData.value || !previewQuery.value) return false
  const current = getCurrentPreviewQuery()
  return Object.keys(current).every((key) => current[key] === previewQuery.value[key])
})

// 过滤后的表列表（不再需要前端过滤，后端已处理）
const filteredTables = computed(() => {
  if (!previewData.value || !previewData.value.tables) return []
  return previewData.value.tables
})

const handlePreview = async () => {
  previewLoading.value = true
  cleanupResult.value = null
  errorMessage.value = ''
  const query = getCurrentPreviewQuery()
  
  try {
    const res = await previewCleanup(
      query.mode,
      query.cutoff,
      query.days ?? 7,
      query.tableName,
      query.chineseName
    )
    previewData.value = res
    previewQuery.value = query
  } catch (error) {
    errorMessage.value = error?.message || '预览统计失败，请重试'
  } finally {
    previewLoading.value = false
  }
}

const handleCleanup = async () => {
  // 构建确认文案
  const cutoffText = configForm.mode === 'datetime' 
    ? formatDate(configForm.cutoff)
    : (configForm.days === 0 ? '所有历史数据' : `${configForm.days}天前`)
  
  // 计算总清理数据条数
  const totalRecords = previewData.value?.tables?.reduce((sum, table) => sum + (table.pending_count || 0), 0) || 0
  
  try {
    await ElMessageBox.confirm(
      `<div style="color: #f56c6c; font-weight: bold; margin-bottom: 12px;">⚠️ 高危操作警告</div>
       <div style="margin-bottom: 8px;">您即将清理<strong>当前查询结果中的所有表</strong>中符合条件的软删除数据。</div>
       <div style="margin-bottom: 8px;">系统将按数据依赖关系自动清理，优先清理关联数据，避免外键约束导致失败。</div>
       <div style="margin-bottom: 8px;">截止时间：${cutoffText}</div>
       <div style="margin-bottom: 8px;">预计影响：<strong>${previewData.value?.total_tables || 0}</strong> 个表</div>
       <div style="margin-bottom: 8px;">预计清理：<strong style="color: #f56c6c; font-size: 16px;">${totalRecords}</strong> 条数据</div>
       <div style="color: #f56c6c;">此操作不可恢复，请再次确认是否继续？</div>`,
      '极度危险操作',
      {
        confirmButtonText: '我确定要清理当前范围',
        cancelButtonText: '取消',
        type: 'error',
        dangerouslyUseHTMLString: true,
        distinguishCancelAndClose: true
      }
    )
  } catch {
    return // 用户取消
  }
  
  // 显示清理过程弹窗
  cleanupDialogTitle.value = '批量清理中'
  cleanupDialogLoading.value = true
  cleanupDialogLoadingText.value = '正在清理数据，请稍候...'
  cleanupDialogResult.value = null
  cleanupDialogVisible.value = true
  
  try {
    const res = await cleanupData(
      configForm.mode,
      configForm.mode === 'datetime' ? configForm.cutoff : null,
      configForm.mode === 'days' ? configForm.days : 7,
      previewData.value.tables.map((table) => table.table_name)
    )
    cleanupResult.value = res
    
    // 清理完成，关闭 loading 显示结果
    cleanupDialogLoading.value = false
    if (res.success) {
      cleanupDialogTitle.value = '清理完成'
      cleanupDialogResult.value = {
        success: true,
        message: res.message || `已清理 ${res.tables_cleaned || 0} 个表中的 ${res.total_records_deleted || 0} 条数据`
      }
      // 清理成功后刷新预览
      await handlePreview()
    } else {
      cleanupDialogTitle.value = '清理失败'
      cleanupDialogResult.value = {
        success: false,
        error: res.message || '清理操作失败'
      }
    }
  } catch (error) {
    console.error('清理失败:', error)
    errorMessage.value = error?.message || '物理清理失败，请重试'
    cleanupDialogLoading.value = false
    cleanupDialogTitle.value = '清理失败'
    const errorMsg = error?.response?.data?.message || error?.data?.message || '清理操作失败，请稍后重试'
    cleanupDialogResult.value = {
      success: false,
      error: errorMsg
    }
  }
}

const handleDeleteSingleTable = async (row) => {
  const cutoffText = configForm.mode === 'datetime' 
    ? formatDate(configForm.cutoff)
    : (configForm.days === 0 ? '所有历史数据' : `${configForm.days}天前`)
  
  try {
    await ElMessageBox.confirm(
      `<div style="margin-bottom: 8px;">表名：<strong>${row.table_name}</strong></div>
       <div style="margin-bottom: 8px;">截止时间：${cutoffText}</div>
       <div style="margin-bottom: 8px;">预计删除：<strong style="color: #f56c6c">${row.pending_count}</strong> 条记录</div>
       <div style="color: #f56c6c;">此操作不可逆，请确认是否删除？</div>`,
      '单表删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        dangerouslyUseHTMLString: true
      }
    )
  } catch {
    return // 用户取消
  }
  
  // 显示清理过程弹窗
  cleanupDialogTitle.value = `清理 ${row.table_name}`
  cleanupDialogLoading.value = true
  cleanupDialogLoadingText.value = '正在删除数据，请稍候...'
  cleanupDialogResult.value = null
  cleanupDialogVisible.value = true
  
  try {
    const res = await cleanupSingleTable(
      row.table_name,
      configForm.mode,
      configForm.mode === 'datetime' ? configForm.cutoff : null,
      configForm.mode === 'days' ? configForm.days : 7
    )
    
    // 清理完成，关闭 loading 显示结果
    cleanupDialogLoading.value = false
    if (res.success) {
      cleanupDialogTitle.value = '清理完成'
      cleanupDialogResult.value = {
        success: true,
        message: res.message || `表 ${row.table_name} 已清理 ${res.records_deleted || 0} 条数据`
      }
      // 删除成功后刷新预览
      await handlePreview()
    } else {
      cleanupDialogTitle.value = '清理失败'
      cleanupDialogResult.value = {
        success: false,
        error: res.error || '未知错误'
      }
    }
  } catch (error) {
    console.error('删除失败:', error)
    cleanupDialogLoading.value = false
    cleanupDialogTitle.value = '清理失败'
    let errorMsg = '删除操作失败，请稍后重试'
    if (error?.data?.error) {
      errorMsg = error.data.error
    } else if (error?.data?.message) {
      errorMsg = error.data.message
    } else if (error?.response?.data?.error) {
      errorMsg = error.response.data.error
    } else if (error?.response?.data?.message) {
      errorMsg = error.response.data.message
    }
    cleanupDialogResult.value = {
      success: false,
      error: errorMsg
    }
  }
}

const handleReset = () => {
  configForm.mode = 'datetime'
  configForm.cutoff = formatBeijingTime(new Date()).replace(' ', 'T')
  configForm.days = 7
  previewData.value = null
  previewQuery.value = null
  cleanupResult.value = null
  searchKeyword.tableName = ''
  searchKeyword.chineseName = ''
}

const handleSearch = () => {
  // 调用接口进行搜索过滤
  handlePreview()
}

const handleTableRowClick = (row) => {
  if (row?.table_name) viewTableData(row.table_name)
}

const handleResetSearch = () => {
  searchKeyword.tableName = ''
  searchKeyword.chineseName = ''
  if (previewData.value) {
    handlePreview()
  }
}

const viewTableData = async (tableName) => {
  currentTableName.value = tableName
  tableDataTab.value = 'data'
  tableDataDialogVisible.value = true
  tableDataLoading.value = true
  tableDataInfo.value = null
  
  try {
    const res = await previewTableData(
      tableName,
      configForm.mode,
      configForm.mode === 'datetime' ? configForm.cutoff : null,
      configForm.mode === 'days' ? configForm.days : 7
    )
    tableDataInfo.value = res
  } catch (error) {
    console.error('获取表数据失败:', error)
  } finally {
    tableDataLoading.value = false
  }
}

// 模式切换时不自动刷新预览，需手动点击按钮
const handleModeChange = () => {
  // 切换模式后清空预览数据
  previewData.value = null
  previewQuery.value = null
  cleanupResult.value = null
}

// 清理条件变化后，旧预览不再作为执行依据，但不自动发起查询。
watch(() => [configForm.mode, configForm.cutoff, configForm.days], () => {
  if (previewData.value) {
    previewData.value = null
    previewQuery.value = null
    cleanupResult.value = null
  }
})
</script>

<style scoped>
.page-wrap { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.page-desc { font-size: 13px; color: #8c8c8c; margin: 0 0 12px; flex-shrink: 0; }
.load-error { margin-bottom: 10px; flex-shrink: 0; }
.scroll-area { flex: 1; overflow-y: auto; min-height: 0; }
.config-card { margin-bottom: 24px; }
.preview-card { margin-bottom: 24px; }
.result-card { margin-bottom: 24px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.form-tip { margin-left: 12px; color: #909399; font-size: 14px; }
.empty-state { text-align: center; padding: 100px 0; color: #8c8c8c; }
.empty-state p { margin-top: 20px; font-size: 16px; }
.cleanup-column-header { display: flex; flex-direction: column; min-width: 0; line-height: 1.25; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cleanup-column-header span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cleanup-column-header small { color: #909399; font-size: 12px; font-weight: 400; }
.relation-english { display: block; color: #909399; font-size: 12px; margin-top: 2px; }
.cleanup-preview-table :deep(.el-table__body tr) { cursor: pointer; }
.cleanup-preview-table :deep(.el-table__body tr:hover > td) { background: #ecf5ff !important; }
.cleanup-preview-table :deep(.cleanup-action-cell) { cursor: default; }
:deep(.no-wrap-header .cell) { white-space: nowrap; }
.cleanup-preview-table :deep(.el-table__cell .cell),
.cleanup-result-table :deep(.el-table__cell .cell),
.cleanup-sample-table :deep(.el-table__cell .cell),
.cleanup-relation-table :deep(.el-table__cell .cell) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cleanup-preview-table :deep(.el-table__cell:last-child .cell) { overflow: visible; }
</style>
