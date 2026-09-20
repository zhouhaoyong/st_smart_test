<template>
  <div class="psd-page">
    <div class="page-header">
      <div class="page-title">
        <h2 style="margin:0;font-size:20px;font-weight:600">{{ psName }}</h2>
        <span v-if="psDesc" style="color:#909399;font-size:14px;margin-top:4px;display:block">{{ psDesc }}</span>
      </div>
    </div>

    <div class="search-toolbar-panel">
      <div class="parameter-toolbar-row">
        <el-input v-model="searchFilters.name" placeholder="搜索参数名称" clearable class="search-input" :prefix-icon="Search" />
        <el-input v-model="searchFilters.key" placeholder="搜索 Key" clearable class="search-input" :prefix-icon="Search" />
        <el-input v-model="searchFilters.value" placeholder="搜索 Value" clearable class="search-input" :prefix-icon="Search" />
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
        <el-button type="primary" :icon="Plus" @click="handleCreate">添加参数</el-button>
        <el-button type="warning" @click="openBatchParameterize" :disabled="selectedItems.length === 0">
          批量参数化 {{ selectedItems.length ? `(${selectedItems.length})` : '' }}
        </el-button>
        <el-button @click="openDetectCandidates" :loading="candidateLoading">识别可复用参数</el-button>
        <el-button @click="openHelpDialog('parameterize')">参数化说明</el-button>
        <el-button type="danger" plain :disabled="selectedItems.length === 0" @click="handleBatchDelete">
          批量删除 {{ selectedItems.length ? `(${selectedItems.length})` : '' }}
        </el-button>
        <el-button type="danger" plain :disabled="total === 0" @click="handleDeleteAll">
          全部删除{{ total ? ` (${total})` : '' }}
        </el-button>
      </div>
    </div>

    <div class="parameter-table-scroll" :class="{ 'is-empty': !items.length }" v-loading="loading">
      <el-table v-if="items.length" height="100%" class="parameter-item-table" :data="items" stripe @selection-change="onSelectionChange" ref="tableRef">
        <template #empty><GlobalEmpty text="暂无数据" /></template>
        <el-table-column type="selection" width="45" />
        <el-table-column prop="display_name" label="参数名称" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" underline="never" @click="handleEdit(row)">
              {{ row.display_name || '-' }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="key" label="Key" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" underline="never" class="parameter-item-link" @click="handleEdit(row)">
              {{ row.key || '-' }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="Value" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" underline="never" class="parameter-item-link" @click="handleEdit(row)">
              {{ row.value || '-' }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small" type="info" effect="plain">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="140" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="170" show-overflow-tooltip>
          <template #default="{ row }">
            {{ formatBeijingMinute(row.created_at) || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="warning" size="small" @click="openParameterize(row)">参数化</el-button>
            <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <GlobalEmpty v-else-if="!loading" />
    </div>

    <div v-if="total > 0" class="parameter-pagination">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
    </div>

    <!-- 编辑/添加对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="560px" destroy-on-close :close-on-click-modal="false" class="param-item-dialog">
      <el-form :model="form" ref="formRef" label-width="96px" class="param-item-form">
        <el-form-item label="参数名称" required>
          <el-input v-model="form.display_name" placeholder="如：登录用户名" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="Key" required>
          <el-input v-model="form.key" placeholder="如：username，用于 $.username 引用" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="Value" required>
          <el-input v-model="form.value" type="textarea" :rows="3" placeholder="参数值" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.type" style="width:100%" @change="form.type_source = 'manual'">
            <el-option v-for="t in typeOptions" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" placeholder="可选" maxlength="50" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">{{ form.id ? '保存' : '添加' }}</el-button>
      </template>
    </el-dialog>

    <!-- 识别参数 -->
    <el-dialog v-model="candidateDialogVisible" width="1280px" destroy-on-close :close-on-click-modal="false" :show-close="false" :class="['candidate-dialog', 'smart-dialog', { maximized: candMaxed }]" @closed="candMaxed=false">
      <template #header>
        <div class="smart-dialog-header">
          <span class="smart-dialog-title">识别参数</span>
          <div class="smart-dialog-actions">
            <el-button link class="smart-dialog-icon-btn" title="使用说明" @click.stop="openHelpDialog('candidate')">
              <el-icon :size="17"><QuestionFilled /></el-icon>
            </el-button>
            <el-button link @click.stop="candMaxed=!candMaxed" class="smart-dialog-icon-btn" :title="candMaxed ? '还原' : '最大化'">
              <el-icon :size="17"><Operation v-if="candMaxed" /><FullScreen v-else /></el-icon>
            </el-button>
            <el-button link class="smart-dialog-icon-btn" title="关闭" @click.stop="candidateDialogVisible = false">
              <el-icon :size="17"><Close /></el-icon>
            </el-button>
          </div>
        </div>
      </template>
      <div class="candidate-toolbar">
        <div class="candidate-query">
          <el-input v-model="candSearch" placeholder="搜索参数名称 / Key / 参数值" clearable class="candidate-search-input" />
          <el-select
            v-model="candLocations"
            multiple
            collapse-tags
            collapse-tags-tooltip
            clearable
            class="candidate-location-select"
            placeholder="参数位置"
            :disabled="candidateLoading"
            @change="onCandidateLocationsChange"
            @clear="clearCandidateLocations"
          >
            <el-option v-for="option in candidateLocationOptions" :key="option.value" :label="option.label" :value="option.value" />
            <el-option label="全部（含请求头）" value="all" />
          </el-select>
          <el-button type="primary" :icon="Search" :loading="candidateLoading" @click="loadDetectCandidates">查询</el-button>
        </div>
        <span class="candidate-count">可新增 {{ visibleCandidateRows.length }} 项，需确认 {{ reviewCandidateRows.length }} 项，已存在 {{ existingCandidateRows.length }} 项，异常来源 {{ invalidCandidateRows.length }} 项</span>
      </div>
      <el-tabs v-model="candidateActiveTab" class="candidate-tabs">
        <el-tab-pane :label="`可新增 (${visibleCandidateRows.length})`" name="visible" />
        <el-tab-pane :label="`需确认 (${reviewCandidateRows.length})`" name="review" />
        <el-tab-pane :label="`已存在 (${existingCandidateRows.length})`" name="existing" />
        <el-tab-pane :label="`异常来源 (${invalidCandidateRows.length})`" name="invalid" />
      </el-tabs>
      <div class="candidate-table-wrap">
        <el-table
          ref="candidateTableRef"
          v-loading="candidateLoading"
          :data="displayCandidateRows"
          :max-height="candMaxed ? 'calc(100vh - 210px)' : 'min(58vh, 560px)'"
          border
          size="small"
          scrollbar-always-on
          class="candidate-table"
          :row-class-name="candidateRowClassName"
          @selection-change="rows => selectedCandidateRows = rows"
        >
        <el-table-column type="expand" width="1" class-name="candidate-expand-column">
          <template #default="{ row }">
            <div class="candidate-source-detail">
              <div v-if="!row.sources?.length" class="candidate-source-detail-empty">暂无来源详情</div>
              <div v-for="(src, si) in row.sources" :key="`${src.source_id || 'source'}-${si}`" class="candidate-source-detail-row">
                <div class="candidate-source-detail-main">
                  <el-tag size="small" :type="src.source_type === 'interface' ? 'primary' : 'warning'">
                    {{ src.source_type === 'interface' ? '接口' : '用例' }}
                  </el-tag>
                  <el-button link type="primary" size="small" class="candidate-source-detail-name" @click="openCandidateDetail(row, src)">
                    {{ src.source_name || '-' }}
                  </el-button>
                  <span class="candidate-source-detail-location">参数位置：{{ parameterLocationLabel(src) }}</span>
                </div>
                <div class="candidate-source-detail-meta">
                  <span>值：{{ src.value === '' ? '空值' : src.value }}</span>
                  <span>类型：{{ src.type || row.type || '-' }}</span>
                  <span>来源：{{ src.origin_label || originLabel(src.origin_type) }}</span>
                  <el-tag size="small" effect="plain" :type="src.candidate_status === 'invalid' ? 'danger' : src.candidate_status === 'empty' ? 'info' : 'success'">
                    {{ src.candidate_status_label || '正常候选' }}
                  </el-tag>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column type="selection" width="38" :selectable="isCandidateSelectable" />
        <el-table-column v-if="candidateActiveTab !== 'visible'" label="状态说明" width="96">
          <template #default="{ row }">
            <el-tag size="small" type="info" effect="plain">{{ candidateIgnoredReasonLabel(row.ignored_reason) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="参数名称" width="160">
          <template #default="{ row }">
            <el-input v-model="row.display_name" size="small" :disabled="candidateActiveTab !== 'visible'" />
          </template>
        </el-table-column>
        <el-table-column label="Key" width="160">
          <template #default="{ row }">
            <el-input v-model="row.key" size="small" :disabled="candidateActiveTab !== 'visible'" />
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-select v-model="row.type" size="small" :disabled="candidateActiveTab !== 'visible'" @change="row.type_source = 'manual'">
              <el-option v-for="t in typeOptions" :key="t" :label="t" :value="t" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="参数值" width="180">
          <template #default="{ row }">
            <el-input v-model="row.value" size="small" :disabled="candidateActiveTab !== 'visible'" />
          </template>
        </el-table-column>
        <el-table-column label="来源" min-width="240" class-name="candidate-source-summary-column">
          <template #default="{ row }">
            <div
              class="candidate-source-summary candidate-source-summary-clickable"
              role="button"
              tabindex="0"
              @click="toggleCandidateSource(row)"
              @keydown.enter.prevent="toggleCandidateSource(row)"
              @keydown.space.prevent="toggleCandidateSource(row)"
            >
              <strong>{{ row.sources?.length || row.hit_count || 0 }} 个来源</strong>
              <span>点击展开查看接口、用例和参数位置</span>
            </div>
          </template>
        </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="candidateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="addDetectedItems" :loading="candidateSaving" :disabled="candidateLoading || selectedAddableCandidateRows.length === 0">
          加入参数集 {{ selectedAddableCandidateRows.length ? `(${selectedAddableCandidateRows.length})` : '' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 参数化对话框 -->
    <el-dialog v-model="paramDialogVisible" width="1180px" destroy-on-close :close-on-click-modal="false" :show-close="false" class="param-dialog smart-dialog">
      <template #header>
        <div class="smart-dialog-header">
          <span class="smart-dialog-title">{{ paramDialogTitle }}</span>
          <div class="smart-dialog-actions">
            <el-button link class="smart-dialog-icon-btn" title="使用说明" @click.stop="openHelpDialog('parameterize')">
              <el-icon :size="17"><QuestionFilled /></el-icon>
            </el-button>
            <el-button link class="smart-dialog-icon-btn" title="关闭" @click.stop="paramDialogVisible = false">
              <el-icon :size="17"><Close /></el-icon>
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="paramSearching && !paramSearched" class="param-loading">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <p>正在搜索...</p>
      </div>

      <div v-else-if="paramSearched" class="param-dialog-body" v-loading="paramSearching">
        <div v-if="paramError" class="param-error">{{ paramError }}</div>
        <div v-if="!paramError" class="param-scan-options">
          <div class="param-source-query">
            <el-input
              v-model="paramSourceKeyword"
              clearable
              class="param-source-input"
              placeholder="搜索接口 URL / 接口名称 / 用例名称"
              @keyup.enter="searchParamSources"
            />
            <el-button type="primary" :icon="Search" :loading="paramSearching" @click="searchParamSources">查询</el-button>
          </div>
          <div class="param-scan-preference">
            <el-switch
              v-model="paramIncludeHeaders"
              active-text="包含请求头"
              inactive-text="不扫描请求头"
              :loading="paramSearching"
              @change="onParamIncludeHeadersChange"
            />
            <span v-if="!paramIncludeHeaders && hiddenHeaderReferenceCount > 0" class="param-scan-note">
              已隐藏 {{ hiddenHeaderReferenceCount }} 处请求头引用
            </span>
          </div>
        </div>

        <div v-if="!paramError && paramGroups.length === 0" class="param-empty-status">
          未搜索到匹配的接口或用例
        </div>

        <div v-else-if="!paramError" class="param-action-bar">
          <div class="param-status-tabs">
            <button
              v-for="option in paramStatusOptions"
              :key="option.value"
              type="button"
              class="param-status-tab"
              :class="{ active: paramMatchStatus === option.value }"
              @click="paramMatchStatus = option.value"
            >
              <el-icon><component :is="option.icon" /></el-icon>
              <span>{{ option.label }}</span>
              <strong>{{ option.count }}</strong>
              <span class="param-status-help" role="button" tabindex="0" @click.stop="openParamStatusHelp(option.value)" @keydown.enter.stop.prevent="openParamStatusHelp(option.value)" @keydown.space.stop.prevent="openParamStatusHelp(option.value)">
                <el-icon><QuestionFilled /></el-icon>
              </span>
            </button>
          </div>
          <div class="param-bulk-actions">
            <el-button size="small" @click="toggleAll(true)">全选</el-button>
            <el-button size="small" @click="toggleAll(false)">全不选</el-button>
          </div>
          <span class="param-selection-count">{{ paramStatusSummary }}</span>
        </div>

        <div class="param-results-scroll">
          <div v-if="paramGroups.length > 0 && visibleInterfaceGroups.length === 0 && !paramError" class="param-empty-status">
            当前筛选条件下没有命中项
          </div>

          <section v-for="interfaceGroup in visibleInterfaceGroups" :key="interfaceGroup.key" class="interface-param-group">
            <div class="interface-group-head" @click="toggleInterfaceGroupExpanded(interfaceGroup.key)">
              <el-checkbox
                :model-value="isInterfaceGroupChecked(interfaceGroup)"
                :indeterminate="isInterfaceGroupIndeterminate(interfaceGroup)"
                @click.stop
                @change="value => toggleInterfaceGroupSelection(interfaceGroup, value)"
              />
              <div class="interface-group-main">
                <div class="interface-group-title-row">
                  <el-tag v-if="interfaceGroup.interfaceMethod" :type="methodTagType(interfaceGroup.interfaceMethod)" size="small" effect="dark">
                    {{ interfaceGroup.interfaceMethod }}
                  </el-tag>
                  <strong>{{ interfaceGroup.interfaceName || interfaceGroup.title }}</strong>
                  <el-button link type="primary" size="small" class="interface-group-open-detail" @click.stop="openInterfaceGroupDetail(interfaceGroup)">打开详情</el-button>
                  <span class="interface-group-stats">{{ interfaceGroup.caseCount }} 个用例 · {{ interfaceGroup.matchCount }} 处命中</span>
                </div>
                <div class="interface-group-url">{{ interfaceGroup.interfaceUrl || '未关联接口' }}</div>
              </div>
              <span class="interface-group-chevron" :class="{ expanded: interfaceGroup.expanded }">⌄</span>
            </div>

            <div v-show="interfaceGroup.expanded" class="interface-group-body">
              <div v-for="parameterGroup in interfaceGroup.parameterGroups" :key="parameterGroup.key" class="interface-parameter-block">
                <div class="param-group-title">
                  <span>参数 {{ parameterGroup.displayName || parameterGroup.key }}</span>
                  <span v-if="parameterGroup.displayName" class="param-group-key">({{ parameterGroup.key }})</span>
                  <span class="param-group-arrow">替换为</span>
                  <code>$.{{ parameterGroup.key }}</code>
                  <el-button
                    link
                    type="primary"
                    size="small"
                    class="param-group-edit"
                    :disabled="paramSearching || paramReplacing"
                    @click.stop="toggleParameterEditor(parameterGroup.key)"
                  >
                    {{ isParameterEditorOpen(parameterGroup.key) ? '收起编辑' : '编辑参数' }}
                  </el-button>
                  <el-tag v-if="isParameterDraftDirty(parameterGroup.key)" size="small" type="warning" effect="plain">未保存</el-tag>
                </div>
                <div v-if="isParameterEditorOpen(parameterGroup.key)" class="param-inline-editor" @click.stop>
                  <div class="param-inline-field param-inline-value">
                    <span>Value</span>
                    <el-input
                      v-model="parameterDrafts[parameterGroup.key].value"
                      size="small"
                      :disabled="paramSearching || paramReplacing"
                      placeholder="参数值"
                    />
                  </div>
                  <div class="param-inline-field">
                    <span>类型</span>
                    <el-select
                      v-model="parameterDrafts[parameterGroup.key].type"
                      size="small"
                      :disabled="paramSearching || paramReplacing"
                    >
                      <el-option v-for="t in typeOptions" :key="t" :label="t" :value="t" />
                    </el-select>
                  </div>
                  <el-button type="primary" size="small" :loading="paramSearching" :disabled="paramReplacing" @click="reidentifyParameterization">
                    重新识别
                  </el-button>
                  <span v-if="isParameterDraftDirty(parameterGroup.key)" class="param-inline-hint">修改后请重新识别，执行时才会保存</span>
                </div>
                <div v-for="sourceGroup in parameterGroup.results" :key="sourceGroup.nodeKey" class="param-target-card">
                  <div class="param-target-head">
                    <el-tag :type="sourceGroup.type === 'interface' ? 'primary' : 'warning'" size="small">{{ sourceGroup.type === 'interface' ? '接口' : '用例' }}</el-tag>
                    <span class="param-target-name" role="button" tabindex="0" @click="openDetail(sourceGroup)" @keydown.enter.prevent="openDetail(sourceGroup)" @keydown.space.prevent="openDetail(sourceGroup)">{{ sourceGroup.name }}</span>
                    <span class="param-target-open-detail" role="button" tabindex="0" @click="openDetail(sourceGroup)" @keydown.enter.prevent="openDetail(sourceGroup)" @keydown.space.prevent="openDetail(sourceGroup)">打开详情</span>
                    <span class="param-target-count">{{ sourceGroup._flatMatches.filter(m => m._checked).length }} / {{ sourceGroup._flatMatches.length }}</span>
                  </div>
                  <div v-for="m in sourceGroup._flatMatches" :key="m.nodeKey" class="param-match-row" :class="`is-${m._status}`">
                    <el-checkbox v-if="isParameterMatchReplaceable(m, parameterGroup.key)" v-model="m._checked" class="param-match-checkbox">
                      <div class="param-match-content">
                      <div class="param-match-main">
                          <el-tag size="small" type="info" effect="plain" class="param-location-tag">参数位置：{{ parameterLocationLabel(m) }}</el-tag>
                          <el-tag v-if="m._status === 'conflict'" size="small" type="warning" effect="plain">{{ conflictTagLabel(m) }}</el-tag>
                          <el-tag v-else-if="m._status === 'parameterized'" size="small" type="success" effect="plain">已参数化</el-tag>
                        </div>
                        <div v-if="m._status === 'conflict'" class="param-match-fields">
                          <span class="field-label">当前值</span><code class="param-conflict-value">{{ displayMatchValue(m.value) }}</code>
                          <span class="field-label">目标参数</span><code class="param-new-value">{{ m.replaced }}</code>
                        </div>
                        <div v-else-if="m._status === 'parameterized'" class="param-match-fields">
                          <span class="field-label">参数引用</span><code class="param-new-value">{{ m.replaced }}</code>
                          <span class="param-row-arrow">→</span><span class="field-label">恢复为</span><code class="param-current-value">{{ m.paramValue }}</code>
                        </div>
                        <div v-else class="param-match-fields">
                          <span class="field-label">原值</span><code class="param-old-value">{{ displayMatchValue(m.value) }}</code>
                          <span class="param-row-arrow">→</span><span class="field-label">参数名</span><code class="param-new-value">{{ m.replaced }}</code>
                        </div>
                      </div>
                    </el-checkbox>
                    <div v-else class="param-match-content no-checkbox">
                      <div class="param-match-main">
                        <el-tag size="small" type="info" effect="plain" class="param-location-tag">参数位置：{{ parameterLocationLabel(m) }}</el-tag>
                        <el-tag v-if="m._status === 'parameterized'" size="small" type="success" effect="plain">已参数化</el-tag>
                        <el-tag v-else-if="m._status === 'conflict'" size="small" type="warning" effect="plain">{{ conflictTagLabel(m) }}</el-tag>
                      </div>
                      <div v-if="m._status === 'parameterized'" class="param-match-fields">
                        <span class="field-label">参数名</span><code class="param-new-value">{{ m.replaced }}</code>
                        <span class="field-label">当前值</span><code class="param-current-value">{{ m.paramValue }}</code>
                      </div>
                      <div v-else class="param-match-fields">
                        <span class="field-label">当前值</span><code class="param-conflict-value">{{ displayMatchValue(m.value) }}</code>
                        <span class="field-label">目标参数</span><code class="param-new-value">{{ m.replaced }}</code>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>

      <div v-if="paramSearched && !paramError && (visibleInterfaceGroups.length > 0 || hasParameterDraftChanges())" class="param-dialog-footer">
        <el-button @click="paramDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doParamReplace" :loading="paramReplacing" :disabled="paramSearching">{{ paramActionButtonText }}</el-button>
      </div>
    </el-dialog>

    <el-dialog v-model="paramMatchDetailVisible" title="参数化详情" width="720px" append-to-body class="param-change-dialog">
      <div v-if="paramMatchDetail" class="param-change-detail">
        <div class="param-change-hero">
          <el-tag :type="paramMatchDetail.status === 'conflict' ? 'warning' : paramMatchDetail.status === 'parameterized' ? 'success' : 'primary'" effect="plain">
            {{ paramMatchDetail.modeLabel }}
          </el-tag>
          <div>
            <strong>{{ paramMatchDetail.targetName }}</strong>
            <span>{{ paramMatchDetail.matchType }} / {{ paramMatchDetail.path }}</span>
          </div>
        </div>
        <div class="param-change-grid">
          <section>
            <div class="param-change-title">{{ paramMatchDetail.beforeLabel }}</div>
            <pre>{{ paramMatchDetail.before }}</pre>
          </section>
          <section>
            <div class="param-change-title">{{ paramMatchDetail.afterLabel }}</div>
            <pre>{{ paramMatchDetail.after }}</pre>
          </section>
        </div>
        <div class="param-change-meta">
          <span>参数名</span>
          <code>{{ paramMatchDetail.parameterName || '-' }}</code>
          <span>参数引用</span>
          <code>{{ paramMatchDetail.parameterRef || '-' }}</code>
          <span>参数值</span>
          <code>{{ paramMatchDetail.parameterValue || '-' }}</code>
        </div>
        <div v-if="paramMatchDetail.reason" class="param-change-warning">{{ paramMatchDetail.reason }}</div>
      </div>
    </el-dialog>

    <!-- 接口/用例详情弹窗 -->
    <el-dialog v-model="detailDlgVisible" :title="detailDlgTitle" width="860px" destroy-on-close :close-on-click-modal="false" class="param-detail-dialog">
      <div v-loading="detailDlgLoading" class="detail-scroll">
        <template v-if="detailType === 'interface'">
          <div class="detail-hero">
            <el-tag :type="methodTagType(detailData.method)" effect="dark" class="method-tag">{{ detailData.method || '-' }}</el-tag>
            <div class="detail-main">
              <strong>{{ detailData.name || '-' }}</strong>
              <span>{{ detailData.url || '-' }}</span>
            </div>
            <el-tag effect="plain" type="info">{{ detailData.body_type || '无请求体' }}</el-tag>
          </div>
          <div class="hit-panel">
            <div class="panel-title">命中位置</div>
            <div v-for="m in detailMatches" :key="m.nodeKey" class="hit-row" :class="{ 'is-empty': isEmptyParameterMatch(m) }">
              <el-tag :type="m._checked ? 'danger' : 'info'" size="small" effect="plain">参数位置：{{ parameterLocationLabel(m) }}</el-tag>
              <el-tag v-if="m._status === 'conflict'" size="small" type="warning" effect="plain">{{ conflictTagLabel(m) }}</el-tag>
              <code class="hit-old">{{ displayMatchValue(m.value) }}</code>
              <template v-if="!detailReadonly">
                <span class="hit-arrow">→</span>
                <code class="hit-new">{{ m.replaced }}</code>
                <span class="hit-state">{{ m._checked ? '将替换' : '未选择' }}</span>
              </template>
              <span v-else class="hit-state">只读</span>
            </div>
          </div>
          <div class="detail-grid" @click="handleDetailPreviewClick">
            <div class="detail-panel">
              <div class="panel-title">查询参数</div>
              <pre class="code-block request-preview" v-html="highlightQueryPreview(detailData.query_params, 'query_params')"></pre>
            </div>
          </div>
          <div v-if="detailData.path_params?.length" class="panel-title">路径参数</div>
          <pre v-if="detailData.path_params?.length" class="code-block request-preview" @click="handleDetailPreviewClick" v-html="highlightPathPreview(detailData.url, detailData.path_params, 'path_params')"></pre>
          <div class="panel-title">请求体</div>
          <pre class="code-block" @click="handleDetailPreviewClick" v-html="highlightBodyText(detailData.body_content || '(无)', 'body_content_json')"></pre>
          <div class="panel-title">请求头</div>
          <pre class="code-block request-preview" @click="handleDetailPreviewClick" v-html="highlightHeaderPreview(detailData.headers, 'headers')"></pre>
          <div v-if="detailData.pre_script" class="panel-title">前置脚本</div>
          <pre v-if="detailData.pre_script" class="code-block" @click="handleDetailPreviewClick" v-html="highlightText(detailData.pre_script)"></pre>
          <div v-if="detailData.post_script" class="panel-title">后置脚本</div>
          <pre v-if="detailData.post_script" class="code-block" @click="handleDetailPreviewClick" v-html="highlightText(detailData.post_script)"></pre>
        </template>
        <template v-else-if="detailType === 'testcase'">
          <div class="detail-hero">
            <el-tag type="warning" effect="dark" class="method-tag">CASE</el-tag>
            <div class="detail-main">
              <strong>{{ detailData.name || '-' }}</strong>
              <span>接口 ID: {{ detailData.interface_id || '-' }} · 优先级: {{ detailData.priority || '-' }} · 负责人: {{ detailData.owner || '-' }}</span>
            </div>
          </div>
          <div class="case-card">
            <div class="hit-panel inner">
              <div class="panel-title">命中位置</div>
              <div v-for="m in detailMatches" :key="m.nodeKey" class="hit-row" :class="{ 'is-empty': isEmptyParameterMatch(m) }">
              <el-tag :type="m._checked ? 'danger' : 'info'" size="small" effect="plain">参数位置：{{ parameterLocationLabel(m) }}</el-tag>
              <el-tag v-if="m._status === 'conflict'" size="small" type="warning" effect="plain">{{ conflictTagLabel(m) }}</el-tag>
              <code class="hit-old">{{ displayMatchValue(m.value) }}</code>
                <template v-if="!detailReadonly">
                  <span class="hit-arrow">→</span>
                  <code class="hit-new">{{ m.replaced }}</code>
                  <span class="hit-state">{{ m._checked ? '将替换' : '未选择' }}</span>
                </template>
                <span v-else class="hit-state">只读</span>
              </div>
            </div>
            <div v-if="detailData.description" class="case-desc">{{ detailData.description }}</div>
            <div class="detail-grid" @click="handleDetailPreviewClick">
              <div v-if="detailData.param_overrides?.query_params?.length" class="detail-panel">
                <div class="panel-title">查询参数</div>
                <pre class="code-block compact request-preview" v-html="highlightQueryPreview(detailData.param_overrides.query_params, 'param_overrides.query_params')"></pre>
              </div>
              <div v-if="detailData.param_overrides?.path_params?.length" class="detail-panel">
                <div class="panel-title">路径参数</div>
                <pre class="code-block compact request-preview" v-html="highlightPathPreview(detailData.url, detailData.param_overrides.path_params, 'param_overrides.path_params')"></pre>
              </div>
            </div>
            <div v-if="detailData.param_overrides?.body_content">
              <div class="panel-title">请求体</div>
              <pre class="code-block compact" @click="handleDetailPreviewClick" v-html="highlightBodyText(detailData.param_overrides.body_content, 'param_overrides.body_content_json')"></pre>
            </div>
            <div v-if="detailData.param_overrides?.headers?.length">
              <div class="panel-title">请求头</div>
              <pre class="code-block compact request-preview" @click="handleDetailPreviewClick" v-html="highlightHeaderPreview(detailData.param_overrides.headers, 'param_overrides.headers')"></pre>
            </div>
            <div v-if="detailData.assertions?.length">
              <div class="panel-title">断言</div>
              <pre class="code-block compact" @click="handleDetailPreviewClick" v-html="highlightText(jsonStr(detailData.assertions))"></pre>
            </div>
            <span v-if="!hasCaseOverrides(detailData)" class="muted-text">无用例参数</span>
          </div>
        </template>
      </div>
    </el-dialog>

    <el-dialog v-model="helpDialogVisible" :title="helpDialogTitle" width="560px" destroy-on-close class="param-help-dialog">
      <el-tabs v-if="showParameterizationHelpTabs" v-model="parameterizationHelpTab" class="param-help-tabs">
        <el-tab-pane label="推荐工作流" name="workflow">
          <div class="help-content">
            <p v-for="item in parameterizationHelpWorkflow" :key="item">{{ item }}</p>
          </div>
        </el-tab-pane>
        <el-tab-pane label="参数化说明" name="details">
          <div class="help-content">
            <p v-for="item in parameterizationHelpDetails" :key="item">{{ item }}</p>
          </div>
        </el-tab-pane>
      </el-tabs>
      <div v-else class="help-content">
        <p v-for="item in helpDialogItems" :key="item">{{ item }}</p>
      </div>
      <template #footer>
        <el-button type="primary" @click="helpDialogVisible = false">知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Loading, FullScreen, Operation, Close, QuestionFilled, Select, RefreshLeft, WarningFilled } from '@element-plus/icons-vue'
import { getParameterSet, getParameterSetItems, batchDeleteParameterItems, batchAddParameterItems, addItem, updateItem, deleteItem, getItemReferences, searchValues, batchReplace, detectParameterCandidates } from '@/api/parameterSet'
import { getInterface } from '@/api/interfaces'
import { getTestCase } from '@/api/testcases'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import { confirmDelete } from '@/utils/confirmDelete'
import { formatBeijingMinute } from '@/utils/beijingTime'
import { buildParameterMatchDetail, highlightParameterText, renderParameterBodyJson, renderParameterConfigJson, renderParameterHeaderPreview, renderParameterPathPreview, renderParameterQueryPreview } from '@/utils/paramHighlight'
import { candidateIgnoredReasonLabel, splitParameterCandidates } from '@/utils/parameterCandidates'
import { categorizeParameterMatches, getParameterMatchStatus, isParameterMatchReplaceable } from '@/utils/parameterizeMatches'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => route.params.id)
const psId = computed(() => route.params.psId)

const psName = ref('')
const psDesc = ref('')
const items = ref([])
const detailBreadcrumb = inject('detailBreadcrumb', ref(''))
const loading = ref(false)
const searchFilters = reactive({ name: '', key: '', value: '' })
const appliedSearchFilters = reactive({ name: '', key: '', value: '' })
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
let dataRequestId = 0
const tableRef = ref(null)
const candidateTableRef = ref(null)
const selectedItems = ref([])
const candidateExistingItems = ref([])
const typeOptions = ['string', 'int', 'float', 'bool', 'list', 'object']
const candidateDialogVisible = ref(false)
const candMaxed = ref(false)
const candSearch = ref('')
const candidateLoading = ref(false)
const candidateSaving = ref(false)
const candidateRows = ref([])
const reviewCandidateRows = ref([])
const existingCandidateRows = ref([])
const invalidCandidateRows = ref([])
const selectedCandidateRows = ref([])
const candidateLocationOptions = [
  { label: '查询参数', value: 'query' },
  { label: '路径参数', value: 'path' },
  { label: '请求体', value: 'body' },
  { label: '请求头（需主动选择）', value: 'headers' },
]
const defaultCandidateLocations = ['query', 'path', 'body']
const candLocations = ref([...defaultCandidateLocations])
let lastCandidateLocations = [...defaultCandidateLocations]
const candidateActiveTab = ref('visible')
const helpDialogVisible = ref(false)
const helpDialogType = ref('candidate')
const helpDialogCustomTitle = ref('')
const helpDialogCustomItems = ref([])
const parameterizationHelpTab = ref('workflow')
const paramMatchDetailVisible = ref(false)
const paramMatchDetail = ref(null)

const helpDialogTitle = computed(() => helpDialogCustomTitle.value || (helpDialogType.value === 'candidate' ? '参数识别说明' : '参数化说明'))
const showParameterizationHelpTabs = computed(() => (
  helpDialogType.value === 'parameterize'
  && helpDialogCustomTitle.value === ''
  && helpDialogCustomItems.value.length === 0
))
const parameterizationHelpWorkflow = [
  '人工调试用例时，先识别多个接口或用例中重复使用、适合复用的公共参数。',
  '在参数集管理中新建参数，填写参数名称、Key、Value 和类型。',
  '回到参数化功能，按当前参数识别对应的接口和用例命中位置。',
  '检查“待参数化”“已参数化”和“异常项”，确认需要处理的内容。',
  '执行参数化后，接口或用例使用 $.key，运行时读取参数集中的当前值。',
]
const parameterizationHelpDetails = [
  '参数引用：将接口或用例中的字面值替换为 $.key，运行时读取参数集中的当前值。',
  '匹配规则：系统根据参数 Key 查找同名字段，并根据参数 Value 判断是否匹配；搜索结果还可以按接口 URL、接口名称或用例名称筛选。',
  '处理状态：“待参数化”表示可以执行替换；“已参数化”表示当前已经引用参数；“异常项”表示可能存在类型不匹配或引用冲突，需要确认后处理。',
  '参数位置：默认识别查询参数、路径参数和请求体；请求头默认不扫描，需要时开启“包含请求头”。',
  '修改参数：修改参数 Value 或类型后，需要点击“重新识别”更新命中结果。',
  '去参数化：可将已使用的 $.key 恢复为参数当前值，但不会删除参数本身。',
]
const helpDialogItems = computed(() => {
  if (helpDialogCustomItems.value.length > 0) return helpDialogCustomItems.value
  if (helpDialogType.value === 'candidate') {
    return [
      '系统从项目下的接口和用例中发现参数，最终一个 Key 只保留一条正式候选。',
      '接口文档类型优先；接口没有类型时，才参考接口保存类型和正常用例值。',
      '空值不作为正式参数，非法值只放在异常来源中，不会加入参数集。',
      '同一个 Key 的其他来源、值和类型会在展开详情中保留，便于追溯。',
      '默认选中查询参数、路径参数和请求体；请求头需主动选择，选择“全部（含请求头）”时纳入。',
      '“需要确认”表示缺少有效值或存在接口类型冲突；“已存在”表示当前参数集已有该 Key。',
    ]
  }
  return parameterizationHelpDetails
})

const visibleCandidateRows = computed(() => candidateRows.value)
const displayCandidateRows = computed(() => {
  const rows = {
    visible: candidateRows.value,
    review: reviewCandidateRows.value,
    existing: existingCandidateRows.value,
    invalid: invalidCandidateRows.value,
  }[candidateActiveTab.value] || []
  const sortedRows = [...rows]
  sortedRows.sort((a, b) => {
    const va = String(a.key ?? '').toLowerCase()
    const vb = String(b.key ?? '').toLowerCase()
    return va.localeCompare(vb)
  })
  return sortedRows
})
const selectedAddableCandidateRows = computed(() => selectedCandidateRows.value.filter(row => !row.ignored_reason))

const dialogVisible = ref(false)
const dialogTitle = ref('')
const submitLoading = ref(false)
const formRef = ref(null)
const form = reactive({ id: null, display_name: '', key: '', value: '', type: 'string', type_source: 'manual', description: '' })

function onSelectionChange(rows) { selectedItems.value = rows }

function clearTableSelection() {
  selectedItems.value = []
  tableRef.value?.clearSelection?.()
}

async function loadData() {
  if (!psId.value) return
  const requestId = ++dataRequestId
  loading.value = true
  try {
    const [detail, pageData] = await Promise.all([
      getParameterSet(psId.value, { includeItems: false }),
      getParameterSetItems(psId.value, page.value, pageSize.value, appliedSearchFilters),
    ])
    if (requestId !== dataRequestId) return
    psName.value = detail.name
    psDesc.value = detail.description || ''
    items.value = pageData?.items || []
    total.value = Number(pageData?.total || 0)
    if (detailBreadcrumb) detailBreadcrumb.value = detail.name
    clearTableSelection()
  } catch {
    if (requestId !== dataRequestId) return
    items.value = []
    total.value = 0
    clearTableSelection()
  } finally {
    if (requestId === dataRequestId) loading.value = false
  }
}

async function handleSearch() {
  Object.assign(appliedSearchFilters, searchFilters)
  page.value = 1
  await loadData()
}

async function resetSearch() {
  Object.assign(searchFilters, { name: '', key: '', value: '' })
  Object.assign(appliedSearchFilters, searchFilters)
  page.value = 1
  await loadData()
}

async function onPageChange(value) {
  page.value = value
  await loadData()
}

async function onPageSizeChange(value) {
  pageSize.value = value
  page.value = 1
  await loadData()
}

function handleCreate() {
  dialogTitle.value = '添加参数'
  Object.assign(form, { id: null, display_name: '', key: '', value: '', type: 'string', type_source: 'manual', description: '' })
  dialogVisible.value = true
}

function typeSourceLabel(source) {
  return { schema: '文档', manual: '手动', inferred: '推断', import: '上传', default: '默认', conflict: '冲突' }[source] || '默认'
}

function originLabel(origin) {
  return { curl: 'cURL导入', file: '文件导入', manual: '手动创建' }[origin] || '手动创建'
}

function originTagType(origin) {
  return { curl: 'success', file: 'primary', manual: 'info' }[origin] || 'info'
}

function isCandidateSelectable(row) {
  return !row?.ignored_reason
}

function candidateRowClassName({ row }) {
  return row?.ignored_reason ? 'candidate-row-ignored' : ''
}

function toggleCandidateSource(row) {
  candidateTableRef.value?.toggleRowExpansion?.(row)
}

function openHelpDialog(type) {
  helpDialogType.value = type
  helpDialogCustomTitle.value = ''
  helpDialogCustomItems.value = []
  if (type === 'parameterize') parameterizationHelpTab.value = 'workflow'
  helpDialogVisible.value = true
}

function validateParamValue(type, value) {
  const text = String(value ?? '').trim()
  if (type === 'string') return ''
  if (type === 'int') return /^[+-]?\d+$/.test(text) ? '' : '请输入合法的 int 类型'
  if (type === 'float') return text !== '' && !Number.isNaN(Number(text)) ? '' : '请输入合法的 float 类型'
  if (type === 'bool') return /^(true|false)$/i.test(text) ? '' : '请输入合法的 bool 类型'
  try {
    const parsed = JSON.parse(text)
    if (type === 'list') return Array.isArray(parsed) ? '' : '请输入合法的 list 类型'
    if (type === 'object') return parsed && !Array.isArray(parsed) && typeof parsed === 'object' ? '' : '请输入合法的 object 类型'
  } catch {
    return `请输入合法的 ${type} 类型`
  }
  return ''
}

function hasDisplayNameConflict(displayName, currentId = null) {
  const normalized = String(displayName || '').trim()
  return items.value.some(item => item.id !== currentId && String(item.display_name || '').trim() === normalized)
}

function hasKeyConflict(key, currentId = null) {
  const normalized = String(key || '').trim()
  return items.value.some(item => item.id !== currentId && String(item.key || '').trim() === normalized)
}

async function openDetectCandidates() {
  candMaxed.value = false
  candidateActiveTab.value = 'visible'
  candidateDialogVisible.value = true
  try {
    const detail = await getParameterSet(psId.value)
    candidateExistingItems.value = detail?.items || []
  } catch {
    candidateExistingItems.value = [...items.value]
  }
  await loadDetectCandidates()
}

function onCandidateLocationsChange(value) {
  const selected = Array.isArray(value) ? value.filter(Boolean) : []
  const hadAll = lastCandidateLocations.includes('all')
  if (selected.includes('all') && !hadAll) {
    candLocations.value = ['all']
  } else {
    candLocations.value = selected.filter(item => item !== 'all')
  }
  lastCandidateLocations = [...candLocations.value]
  if (selected.length === 0) clearCandidateResults()
}

function clearCandidateLocations() {
  candLocations.value = []
  lastCandidateLocations = []
  clearCandidateResults()
}

function clearCandidateResults() {
  candidateRows.value = []
  reviewCandidateRows.value = []
  existingCandidateRows.value = []
  invalidCandidateRows.value = []
  selectedCandidateRows.value = []
  candidateActiveTab.value = 'visible'
}

async function loadDetectCandidates() {
  candidateLoading.value = true
  try {
    const res = await detectParameterCandidates(projectId.value, {
      locations: candLocations.value,
      keyword: candSearch.value.trim(),
    })
    const normalizeCandidate = item => ({
        display_name: item.display_name || item.key,
        key: item.key,
        value: item.value ?? '',
        type: item.type || 'string',
        type_source: item.type_source || 'default',
        description: item.description || item.match_type || '',
        hit_count: item.hit_count || 1,
        origin_type: item.origin_type || item.sources?.[0]?.origin_type || 'manual',
        origin_label: item.origin_label || item.origin_labels?.join('、') || item.sources?.[0]?.origin_label || '手动创建',
        source_name: item.source_name || item.sources?.[0]?.source_name || '',
        match_type: item.match_type || item.sources?.[0]?.match_type || '',
        source_type: item.source_type || item.sources?.[0]?.source_type || '',
        source_id: item.source_id || item.sources?.[0]?.source_id || null,
        field_path: item.field_path || item.sources?.[0]?.field_path || '',
        sources: item.sources || [],
        candidate_status: item.candidate_status || 'needs_confirmation',
        candidate_status_label: item.candidate_status_label || '需要确认',
        ignored_reason: item.ignored_reason || '',
      })
    const split = splitParameterCandidates(res?.items || [], candidateExistingItems.value.length ? candidateExistingItems.value : items.value)
    candidateRows.value = split.visible.map(normalizeCandidate)
    reviewCandidateRows.value = split.review.map(normalizeCandidate)
    existingCandidateRows.value = split.existing.map(normalizeCandidate)
    invalidCandidateRows.value = split.invalid.map(normalizeCandidate)
    selectedCandidateRows.value = []
    const activeRows = {
      visible: candidateRows.value,
      review: reviewCandidateRows.value,
      existing: existingCandidateRows.value,
      invalid: invalidCandidateRows.value,
    }[candidateActiveTab.value] || []
    if (activeRows.length === 0) candidateActiveTab.value = 'visible'
  } catch { }
  finally { candidateLoading.value = false }
}

async function addDetectedItems() {
  const existingItems = candidateExistingItems.value.length ? candidateExistingItems.value : items.value
  const existingNames = new Set(existingItems.map(item => String(item.display_name || '').trim()).filter(Boolean))
  const existingKeys = new Set(existingItems.map(item => String(item.key || '').trim()).filter(Boolean))
  const selectedNames = new Set()
  const selectedKeys = new Set()
  const rowsToAdd = selectedAddableCandidateRows.value
  if (rowsToAdd.length === 0) {
    ElMessage.warning('请至少选择一个可新增参数')
    return
  }
  for (const row of rowsToAdd) {
    const displayName = String(row.display_name || row.key || '').trim()
    const key = String(row.key || '').trim()
    if (existingNames.has(displayName) || selectedNames.has(displayName)) {
      ElMessage.warning(`参数名称「${displayName}」已存在`)
      return
    }
    if (existingKeys.has(key) || selectedKeys.has(key)) {
      ElMessage.warning(`Key「${key}」已存在`)
      return
    }
    if (!String(row.value ?? '').trim()) {
      ElMessage.warning(`参数「${key}」缺少有效值`)
      return
    }
    selectedNames.add(displayName)
    selectedKeys.add(key)
  }
  const invalid = rowsToAdd.find(row => validateParamValue(row.type, row.value))
  if (invalid) {
    ElMessage.warning(`${invalid.key}: ${validateParamValue(invalid.type, invalid.value)}`)
    return
  }
  candidateSaving.value = true
  try {
    await batchAddParameterItems(psId.value, {
      items: rowsToAdd.map(row => ({
        display_name: row.display_name || row.key,
        key: row.key,
        value: row.value,
        type: row.type,
        type_source: row.type_source || 'manual',
        description: row.description || null,
      })),
    }, { skipSuccessToast: true })
    ElMessage.success(`已加入 ${rowsToAdd.length} 个参数`)
    candidateDialogVisible.value = false
    await loadData()
  } catch { }
  finally { candidateSaving.value = false }
}

function handleEdit(row) {
  dialogTitle.value = '编辑参数'
  Object.assign(form, { ...row })
  dialogVisible.value = true
}

async function handleDelete(row) {
  let refs = []
  try {
    const res = await getItemReferences(psId.value, row.id)
    refs = res?.items || []
  } catch { refs = [] }

  if (refs.length > 0) {
    const preview = refs.slice(0, 5).map(ref => `${ref.source_name} / ${ref.match_type}`).join('<br/>')
    const suffix = refs.length > 5 ? `<br/>等 ${refs.length} 处引用` : ''
    try {
      await ElMessageBox.confirm(
        `参数 ${row.key} 正在被 ${refs.length} 处接口或用例引用。<br/>删除后将自动把这些引用恢复为参数当前值，避免运行时残留无效引用。<br/><br/>${preview}${suffix}`,
        '确认删除被引用参数',
        {
          confirmButtonText: '删除并去参数化',
          cancelButtonText: '取消',
          type: 'warning',
          dangerouslyUseHTMLString: true,
        }
      )
    } catch { return }
    try {
      await deleteItem(psId.value, row.id, { force: true })
      if (page.value > 1 && items.value.length === 1) page.value -= 1
      await loadData()
    } catch { }
    return
  }

  const ok = await confirmDelete(row.key, '参数项')
  if (!ok) return
  try {
    await deleteItem(psId.value, row.id)
    if (page.value > 1 && items.value.length === 1) page.value -= 1
    await loadData()
  } catch { }
}

async function handleBatchDelete() {
  const ids = selectedItems.value.map(item => item.id).filter(Boolean)
  if (ids.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定删除当前页选中的 ${ids.length} 个参数项吗？如果参数正在被接口或用例引用，系统会先恢复为参数当前值。`,
      '确认批量删除',
      { confirmButtonText: '删除并去参数化', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  try {
    await batchDeleteParameterItems(psId.value, { ids })
    const remain = Math.max(0, total.value - ids.length)
    page.value = Math.min(page.value, Math.max(1, Math.ceil(remain / pageSize.value)))
    await loadData()
  } catch { }
}

async function handleDeleteAll() {
  if (total.value === 0) return
  try {
    await ElMessageBox.confirm(
      `确定删除当前参数集下、按当前查询条件筛选出的全部 ${total.value} 个参数项吗？被引用参数会先恢复为删除前的当前值。`,
      '确认全部删除',
      { confirmButtonText: '全部删除并去参数化', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  try {
    await batchDeleteParameterItems(psId.value, {
      delete_all_in_scope: true,
      ...appliedSearchFilters,
    })
    page.value = 1
    await loadData()
  } catch { }
}

async function handleSubmit() {
  if (!form.display_name?.trim()) { ElMessage.warning('请输入参数名称'); return }
  if (hasDisplayNameConflict(form.display_name, form.id)) { ElMessage.warning(`参数名称「${form.display_name.trim()}」已存在`); return }
  if (!form.key.trim()) { ElMessage.warning('请输入 Key'); return }
  if (hasKeyConflict(form.key, form.id)) { ElMessage.warning(`Key「${form.key.trim()}」已存在`); return }
  if (!form.value) { ElMessage.warning('请输入参数值'); return }
  const valueError = validateParamValue(form.type, form.value)
  if (valueError) { ElMessage.warning(valueError); return }
  submitLoading.value = true
  try {
    const data = {
      display_name: form.display_name.trim(),
      key: form.key.trim(),
      value: form.value,
      type: form.type || 'string',
      type_source: form.type_source || 'manual',
      description: form.description || null,
    }
    if (form.id) { await updateItem(psId.value, form.id, data) } else { await addItem(psId.value, data) }
    dialogVisible.value = false
    await loadData()
  } catch { }
  finally { submitLoading.value = false }
}

// ====== 参数化 ======
const paramDialogVisible = ref(false)
const paramDialogTitle = ref('')
const paramSearching = ref(false)
const paramSearched = ref(false)
const paramError = ref('')
const paramGroups = ref([])
const paramReplacing = ref(false)
const paramMatchStatus = ref('pending')
const paramIncludeHeaders = ref(false)
const hiddenHeaderReferenceCount = ref(0)
const paramSourceKeyword = ref('')
const appliedParamSourceKeyword = ref('')
const interfaceExpansionState = ref({})
const parameterDrafts = reactive({})
const paramDraftEditKey = ref('')
const identifiedParamDraftSignature = ref('')
let _paramItems = []

function parameterDraftSignature() {
  return _paramItems.map(item => {
    const key = String(item.key || '')
    const draft = parameterDrafts[key]
    return [key, String(draft?.value ?? item.value ?? ''), draft?.type || item.type || 'string'].join('\u0000')
  }).join('\u0001')
}

function resetParameterDrafts() {
  Object.keys(parameterDrafts).forEach(key => { delete parameterDrafts[key] })
  _paramItems.forEach(item => {
    const key = String(item.key || '')
    parameterDrafts[key] = {
      id: item.id,
      key,
      value: String(item.value ?? ''),
      type: item.type || 'string',
      originalValue: String(item.value ?? ''),
      originalType: item.type || 'string',
    }
  })
  paramDraftEditKey.value = ''
  identifiedParamDraftSignature.value = ''
}

function isParameterEditorOpen(key) {
  return paramDraftEditKey.value === String(key)
}

function toggleParameterEditor(key) {
  const normalizedKey = String(key)
  if (!parameterDrafts[normalizedKey]) return
  paramDraftEditKey.value = isParameterEditorOpen(normalizedKey) ? '' : normalizedKey
}

function isParameterDraftDirty(key) {
  const draft = parameterDrafts[String(key)]
  return Boolean(draft && (
    String(draft.value ?? '') !== draft.originalValue ||
    String(draft.type || 'string') !== draft.originalType
  ))
}

function hasParameterDraftChanges() {
  return Object.keys(parameterDrafts).some(isParameterDraftDirty)
}

function hasUnidentifiedParameterDraftChanges() {
  return identifiedParamDraftSignature.value !== parameterDraftSignature()
}

function getParameterDraftUpdates() {
  return Object.values(parameterDrafts)
    .filter(draft => isParameterDraftDirty(draft.key) && draft.id)
    .map(draft => ({
      id: draft.id,
      value: String(draft.value ?? ''),
      type: draft.type || 'string',
    }))
}

function validateParameterDrafts() {
  for (const draft of Object.values(parameterDrafts)) {
    const value = String(draft.value ?? '').trim()
    if (!value) return `参数「${draft.key}」的 Value 不能为空`
    const error = validateParamValue(draft.type || 'string', value)
    if (error) return `参数「${draft.key}」：${error}`
  }
  return ''
}

function commitParameterDrafts() {
  _paramItems.forEach(item => {
    const draft = parameterDrafts[String(item.key)]
    if (!draft) return
    item.value = draft.value
    item.type = draft.type || 'string'
    draft.originalValue = String(draft.value ?? '')
    draft.originalType = draft.type || 'string'
  })
  identifiedParamDraftSignature.value = parameterDraftSignature()
}

const isHeaderReference = ref => {
  const path = String(ref?.field_path || '')
  return path.startsWith('headers.') || path.startsWith('param_overrides.headers.')
}

const paramHeaderPreferenceKey = item => `parameterize:includeHeaders:${psId.value}:${item?.id || item?.key || 'unknown'}`

function readParamHeaderPreference(item) {
  try {
    const value = localStorage.getItem(paramHeaderPreferenceKey(item))
    if (value === '1') return true
    if (value === '0') return false
  } catch { }
  return null
}

function saveParamHeaderPreference(value) {
  _paramItems.forEach(item => {
    try { localStorage.setItem(paramHeaderPreferenceKey(item), value ? '1' : '0') } catch { }
  })
}

async function countHeaderReferencesForItems(paramItems) {
  let count = 0
  for (const item of paramItems || []) {
    if (!item?.id) continue
    try {
      const res = await getItemReferences(psId.value, item.id)
      count += (res?.items || []).filter(isHeaderReference).length
    } catch { }
  }
  return count
}

async function initializeParamHeaderPreference(paramItems) {
  hiddenHeaderReferenceCount.value = 0
  const preferences = (paramItems || []).map(readParamHeaderPreference).filter(v => v !== null)
  if (preferences.length > 0) {
    paramIncludeHeaders.value = preferences.some(Boolean)
    hiddenHeaderReferenceCount.value = await countHeaderReferencesForItems(paramItems)
    return
  }
  hiddenHeaderReferenceCount.value = await countHeaderReferencesForItems(paramItems)
  paramIncludeHeaders.value = hiddenHeaderReferenceCount.value > 0
}

async function onParamIncludeHeadersChange(value) {
  saveParamHeaderPreference(value)
  await runParameterize({ keepStatus: true })
}

const paramStatusLabels = {
  pending: '待参数化',
  parameterized: '已参数化',
  conflict: '异常项',
}
const paramStatusIcons = {
  pending: Select,
  parameterized: RefreshLeft,
  conflict: WarningFilled,
}
const paramStatusHelp = {
  pending: [
    '来源：字段值与当前参数值匹配，或系统判断可安全替换的位置。',
    '操作：勾选后会把原值替换为 $.参数名。',
    '建议：这类命中默认适合批量处理，但仍可按接口/用例单独取消勾选。',
  ],
  parameterized: [
    '来源：字段当前已经引用该参数，例如 $.limit。',
    '操作：支持单选或多选去参数化，把 $.参数名恢复为参数当前值。',
    '建议：用于撤销局部引用，不会删除参数本身。',
  ],
  conflict: [
    '来源：需要人工确认的命中项，例如已引用其他参数，或字段名命中但值类型存在风险。',
    '操作：手动勾选后仍可执行替换。',
    '建议：逐条确认后再处理，避免把对象、数组等结构误替换为普通参数引用。',
  ],
}

const categorizedParamGroups = computed(() => categorizeParameterMatches(paramGroups.value))
const paramStatusOptions = computed(() => Object.keys(paramStatusLabels).map(value => ({
  label: paramStatusLabels[value],
  count: countMatches(categorizedParamGroups.value[value]),
  icon: paramStatusIcons[value],
  value,
})))
const visibleParamGroups = computed(() => categorizedParamGroups.value[paramMatchStatus.value] || [])

const visibleInterfaceGroups = computed(() => {
  const grouped = new Map()
  for (const parameterGroup of visibleParamGroups.value) {
    for (const result of parameterGroup.results || []) {
      const interfaceId = result.interface_id || (result.type === 'interface' ? result.id : null)
      const groupKey = interfaceId ? `interface-${interfaceId}` : `unbound-${result.type}-${result.id}`
      if (!grouped.has(groupKey)) {
        grouped.set(groupKey, {
          key: groupKey,
          interfaceId,
          title: interfaceId ? (result.name || '接口') : '未关联接口',
          interfaceName: result.interface_name || (result.type === 'interface' ? result.name : ''),
          interfaceMethod: result.interface_method || '',
          interfaceUrl: result.interface_url || '',
          parameterGroups: [],
          matchRefs: [],
          caseIds: new Set(),
          matchCount: 0,
          expanded: false,
        })
      }
      const group = grouped.get(groupKey)
      const existingParameterGroup = group.parameterGroups.find(item => item.key === parameterGroup.key)
      if (existingParameterGroup) existingParameterGroup.results.push(result)
      else group.parameterGroups.push({ ...parameterGroup, results: [result] })
      if (result.type === 'testcase') group.caseIds.add(result.id)
      for (const match of result._flatMatches || []) {
        group.matchRefs.push({ match, paramKey: parameterGroup.key })
        group.matchCount += 1
      }
    }
  }
  const groupCount = grouped.size
  return [...grouped.values()].map(group => ({
    ...group,
    caseCount: group.caseIds.size,
    expanded: isInterfaceGroupExpanded(group.key, groupCount),
  }))
})

function countMatches(groups) {
  return (groups || []).reduce((sum, g) => (
    sum + g.results.reduce((s, group) => s + group._flatMatches.length, 0)
  ), 0)
}

function toggleAll(checked) {
  paramGroups.value.forEach(g => {
    g.results.forEach(group => {
      group._flatMatches.forEach(m => {
        if (isParameterMatchReplaceable(m, g.key) && getParameterMatchStatus(m, g.key) === paramMatchStatus.value) m._checked = checked
      })
    })
  })
}

function toggleInterfaceGroupExpanded(groupKey) {
  const current = Boolean(visibleInterfaceGroups.value.find(group => group.key === groupKey)?.expanded)
  interfaceExpansionState.value = {
    ...interfaceExpansionState.value,
    [groupKey]: !current,
  }
}

function isInterfaceGroupExpanded(groupKey, groupCount) {
  if (Object.prototype.hasOwnProperty.call(interfaceExpansionState.value, groupKey)) {
    return Boolean(interfaceExpansionState.value[groupKey])
  }
  return groupCount === 1
}

function interfaceGroupMatches(group) {
  return group.matchRefs.filter(({ match, paramKey }) => (
    isParameterMatchReplaceable(match, paramKey) && getParameterMatchStatus(match, paramKey) === paramMatchStatus.value
  ))
}

function isInterfaceGroupChecked(group) {
  const matches = interfaceGroupMatches(group)
  return matches.length > 0 && matches.every(({ match }) => match._checked)
}

function isInterfaceGroupIndeterminate(group) {
  const matches = interfaceGroupMatches(group)
  const checkedCount = matches.filter(({ match }) => match._checked).length
  return checkedCount > 0 && checkedCount < matches.length
}

function toggleInterfaceGroupSelection(group, checked) {
  interfaceGroupMatches(group).forEach(({ match }) => { match._checked = checked })
}

function openParamStatusHelp(status) {
  helpDialogType.value = 'parameterize'
  helpDialogCustomTitle.value = `${paramStatusLabels[status]}说明`
  helpDialogCustomItems.value = paramStatusHelp[status] || []
  helpDialogVisible.value = true
}

const pendingMatchCount = computed(() => countMatches(categorizedParamGroups.value.pending))
const conflictMatchCount = computed(() => countMatches(categorizedParamGroups.value.conflict))
const selectedMatchCount = computed(() => visibleParamGroups.value.reduce((sum, g) => (
  sum + g.results.reduce((s, group) => s + group._flatMatches.filter(m => m._checked).length, 0)
), 0))
const paramStatusSummary = computed(() => {
  if (paramMatchStatus.value === 'pending') return `已选择 ${selectedMatchCount.value} / ${pendingMatchCount.value} 处`
  if (paramMatchStatus.value === 'parameterized') return `已选择 ${selectedMatchCount.value} / ${countMatches(categorizedParamGroups.value.parameterized)} 处`
  return `已选择 ${selectedMatchCount.value} / ${conflictMatchCount.value} 处`
})
const paramActionButtonText = computed(() => {
  if (visibleInterfaceGroups.value.length === 0 && hasParameterDraftChanges()) return '保存参数'
  if (paramMatchStatus.value === 'parameterized') return '执行去参数化'
  if (paramMatchStatus.value === 'conflict') return '确认后替换'
  return '执行替换'
})

async function openBatchParameterize() {
  _paramItems = [...selectedItems.value]
  if (_paramItems.length === 0) return
  resetParameterDrafts()
  paramDialogTitle.value = `批量参数化 (${_paramItems.length} 个参数)`
  paramSourceKeyword.value = ''
  appliedParamSourceKeyword.value = ''
  await initializeParamHeaderPreference(_paramItems)
  await runParameterize()
}

async function openParameterize(row) {
  _paramItems = [row]
  resetParameterDrafts()
  paramDialogTitle.value = `参数化 - ${row.display_name || row.key}`
  paramSourceKeyword.value = ''
  appliedParamSourceKeyword.value = ''
  await initializeParamHeaderPreference(_paramItems)
  await runParameterize()
}

// 打开接口/用例详情（内嵌弹窗）
const detailDlgVisible = ref(false)
const detailDlgTitle = ref('')
const detailDlgLoading = ref(false)
const detailType = ref('')
const detailData = ref({})
const detailMatches = ref([])
const detailReadonly = ref(false)

function jsonStr(v) { try { return JSON.stringify(v, null, 2) } catch { return String(v) } }
function hasCaseOverrides(tc) { return tc.param_overrides && Object.keys(tc.param_overrides).some(k => { const v = tc.param_overrides[k]; return Array.isArray(v) ? v.length > 0 : !!v }) }
function methodTagType(method) {
  return { GET: 'success', POST: 'primary', PUT: 'warning', DELETE: 'danger', PATCH: 'info' }[(method || '').toUpperCase()] || 'info'
}
function highlightText(text) {
  return highlightParameterText(text, detailMatches.value, { clickable: true, previewMode: 'after' })
}
function highlightParamConfig(value, rootPath) {
  return renderParameterConfigJson(value, detailMatches.value, rootPath, { clickable: true, previewMode: 'after' })
}
function highlightHeaderPreview(headers, rootPath) {
  return renderParameterHeaderPreview(headers, detailMatches.value, rootPath, { clickable: true, previewMode: 'after' })
}
function highlightBodyText(text, rootPath) {
  return renderParameterBodyJson(text, detailMatches.value, rootPath, { clickable: true, previewMode: 'after' })
}
function highlightPathPreview(url, params, rootPath) {
  return renderParameterPathPreview(url, params, detailMatches.value, rootPath, { clickable: true, previewMode: 'after' })
}
function highlightQueryPreview(params, rootPath) {
  return renderParameterQueryPreview(params, detailMatches.value, rootPath, { clickable: true, previewMode: 'after' })
}

function parameterConflictReason(match) {
  if (match?.conflict_kind === 'empty_value') return match?.conflict_reason || '原值为空，需确认是否要参数化'
  if (match?.conflict_kind === 'empty_object') return match?.conflict_reason || '原值为空对象，需确认是否要参数化'
  if (match?.conflict_kind === 'empty_array') return match?.conflict_reason || '原值为空数组，需确认是否要参数化'
  if (match?.conflict_kind === 'null_value') return match?.conflict_reason || '原值为空值，需确认是否要参数化'
  return match?.conflict_reason || '已存在其他参数引用，替换前请确认'
}

function conflictTagLabel(match) {
  if (match?.conflict_kind === 'type_mismatch') return '类型需确认'
  if (match?.conflict_kind === 'empty_value') return '空值确认'
  if (match?.conflict_kind === 'empty_object') return '空对象确认'
  if (match?.conflict_kind === 'empty_array') return '空数组确认'
  if (match?.conflict_kind === 'null_value') return '空值确认'
  return '引用异常'
}

function parameterMatchSummary(match) {
  return buildParameterMatchDetail(match).summary
}

function isEmptyParameterMatch(match) {
  return ['empty_value', 'empty_object', 'empty_array', 'null_value'].includes(match?.conflict_kind) || String(match?.value ?? '').trim() === ''
}

function displayMatchValue(value) {
  const text = String(value ?? '').trim()
  if (text === '') return '(空)'
  if (text === '{}') return '(空对象)'
  if (text === '[]') return '(空数组)'
  if (['null', 'none'].includes(text.toLowerCase())) return 'null'
  return value
}

function matchConfidenceTag(match, paramKey) {
  if (match?.value_matches === false) return { type: 'warning', label: '同 Key·值不同' }
  if (match?.value_matches === true) return { type: 'success', label: 'Key+值匹配' }
  const path = String(match?.path || match?.field || '').toLowerCase()
  const key = String(paramKey || '').toLowerCase()
  if (key && path.includes(key)) return { type: 'success', label: 'Key 匹配' }
  if (path.includes('display_name') || path.includes('test_data')) return { type: 'warning', label: '中文名匹配' }
  return { type: 'info', label: '值匹配' }
}

function parameterLocationLabel(match) {
  const path = String(match?.path || match?.field || '').toLowerCase()
  if (path.includes('query_params')) return '查询参数'
  if (path.includes('path_params')) return '路径参数'
  if (path.includes('headers')) return '请求头'
  if (path.includes('body_content')) return '请求体'

  const matchType = String(match?.match_type || '')
  if (matchType.includes('查询参数')) return '查询参数'
  if (matchType.includes('路径参数')) return '路径参数'
  if (matchType.includes('请求头')) return '请求头'
  if (matchType.includes('请求体')) return '请求体'
  return '请求参数'
}

function openParamMatchDetail(match, group, parameterGroup) {
  paramMatchDetail.value = {
    ...buildParameterMatchDetail(match),
    status: match?._status,
    targetName: group?.name || parameterGroup?.displayName || parameterGroup?.key || '命中项',
    matchType: match?.match_type || '-',
    path: match?.path || '-',
    reason: match?._status === 'conflict' ? parameterConflictReason(match) : '',
  }
  paramMatchDetailVisible.value = true
}

function handleDetailPreviewClick(event) {
  const target = event.target?.closest?.('[data-param-match-key]')
  if (!target) return
  const key = target.getAttribute('data-param-match-key')
  const match = detailMatches.value.find(item => item.nodeKey === key)
  if (!match) return
  const currentValue = target.getAttribute('data-param-current-value')
  openParamMatchDetail({ ...match, currentValue: currentValue ?? match.value }, { name: detailDlgTitle.value }, null)
}

async function openDetail(group) {
  detailDlgVisible.value = true
  detailDlgLoading.value = true
  detailType.value = group.type
  detailDlgTitle.value = group.name
  detailMatches.value = group._flatMatches || []
  detailReadonly.value = false
  try {
    if (group.type === 'interface') {
      const res = await getInterface(group.id)
      detailData.value = res || {}
    } else {
      const res = await getTestCase(group.id)
      detailData.value = res || {}
    }
  } catch { detailData.value = {} }
  finally { detailDlgLoading.value = false }
}

async function openInterfaceGroupDetail(group) {
  const directInterfaceMatches = group.parameterGroups
    .flatMap(parameterGroup => parameterGroup.results || [])
    .filter(result => result.type === 'interface')
    .flatMap(result => result._flatMatches || [])
  if (group.interfaceId) {
    await openDetail({
      type: 'interface',
      id: group.interfaceId,
      name: group.interfaceName || group.interfaceUrl || group.title,
      _flatMatches: directInterfaceMatches,
    })
    return
  }
  const firstCase = group.parameterGroups
    .flatMap(parameterGroup => parameterGroup.results || [])
    .find(result => result.type === 'testcase')
  if (firstCase) await openDetail(firstCase)
}

function parameterValuesMatch(actual, expected, type) {
  const left = String(actual ?? '').trim()
  const right = String(expected ?? '').trim()
  if (type === 'int') return left !== '' && right !== '' && Number(left) === Number(right)
  if (type === 'float') return left !== '' && right !== '' && Number(left) === Number(right)
  if (type === 'bool') return left.toLowerCase() === right.toLowerCase()
  if (type === 'list' || type === 'object') {
    try { return JSON.stringify(JSON.parse(left)) === JSON.stringify(JSON.parse(right)) } catch { return left === right }
  }
  return left === right
}

async function searchParamSources() {
  appliedParamSourceKeyword.value = paramSourceKeyword.value.trim()
  await runParameterize({ keepStatus: true })
}

async function openCandidateDetail(row, sourceOverride = null) {
  const source = sourceOverride || row.sources?.[0] || row
  if (!source?.source_type || !source?.source_id) return
  const sameSourceMatches = (row.sources?.length ? row.sources : [source]).filter(item =>
    item.source_type === source.source_type && item.source_id === source.source_id
  )
  detailDlgVisible.value = true
  detailDlgLoading.value = true
  detailType.value = source.source_type === 'interface' ? 'interface' : 'testcase'
  detailDlgTitle.value = row.source_name || source.source_name || row.key
  detailReadonly.value = true
  detailMatches.value = sameSourceMatches.map((item, index) => ({
    nodeKey: `candidate-${row.key}-${index}`,
    path: item.field_path,
    field: item.field_path,
    match_type: item.match_type || row.match_type,
    value: row.value,
    paramValue: row.key,
    _checked: false,
  }))
  try {
    if (detailType.value === 'interface') {
      const res = await getInterface(source.source_id)
      detailData.value = res || {}
    } else {
      const res = await getTestCase(source.source_id)
      detailData.value = res || {}
    }
  } catch { detailData.value = {} }
  finally { detailDlgLoading.value = false }
}

async function runParameterize(options = {}) {
  const keepStatus = options.keepStatus ? paramMatchStatus.value : 'pending'
  const smoothRefresh = options.keepStatus && paramSearched.value
  paramDialogVisible.value = true
  paramError.value = ''
  if (!smoothRefresh) {
    paramSearched.value = false
    paramGroups.value = []
  }
  paramMatchStatus.value = keepStatus
  paramSearching.value = true

  try {
    const allGroups = []
    for (const item of _paramItems) {
      const draft = parameterDrafts[String(item.key)] || {
        value: String(item.value ?? ''),
        type: item.type || 'string',
      }
      const searchValue = String(draft.value ?? '')
      const paramType = draft.type || 'string'
      if (searchValue.trim() === '') continue
      const res = await searchValues(projectId.value, searchValue, item.key, paramType, {
        includeHeaders: paramIncludeHeaders.value,
        sourceKeyword: appliedParamSourceKeyword.value,
      })
      const results = (res?.results || []).map((g, gi) => {
        const flatMatches = []
        const ref = `$.${item.key}`
        if (g.type === 'interface') {
          ;(g.matches || []).forEach((m, mi) => {
            const valueMatches = typeof m.value_matches === 'boolean'
              ? m.value_matches
              : parameterValuesMatch(m.value, searchValue, paramType)
            flatMatches.push({
              ...m, nodeKey: `${item.key}-${gi}-${mi}`,
              value_matches: valueMatches,
              _checked: valueMatches && !String(m.value ?? '').includes(ref) && !m.conflict_reason,
              _status: 'pending', replaced: ref,
              paramValue: searchValue, paramType,
            })
          })
        } else if (g.type === 'testcase') {
          ;(g.matches || []).forEach((m, mi) => {
            const valueMatches = typeof m.value_matches === 'boolean'
              ? m.value_matches
              : parameterValuesMatch(m.value, searchValue, paramType)
            flatMatches.push({
              ...m,
              nodeKey: `${item.key}-${gi}-${m.path}-${mi}`,
              value_matches: valueMatches,
              _checked: valueMatches && !String(m.value ?? '').includes(ref) && !m.conflict_reason,
              _status: 'pending', replaced: ref,
              paramValue: searchValue, paramType,
            })
          })
        }
        return { ...g, nodeKey: `${item.key}-g${gi}`, _flatMatches: flatMatches }
      })
      if (results.length > 0) {
        allGroups.push({ key: item.key, displayName: item.display_name || '', searchValue, paramType, results })
      }
    }
    paramGroups.value = allGroups
    paramSearched.value = true
    identifiedParamDraftSignature.value = parameterDraftSignature()
  } catch (e) {
    paramError.value = e?.message || '搜索失败'
    if (!smoothRefresh) paramSearched.value = true
  }
  paramSearching.value = false
}

async function doParamReplace() {
  const draftError = validateParameterDrafts()
  if (draftError) { ElMessage.warning(draftError); return }
  const parameterUpdates = getParameterDraftUpdates()
  if (hasUnidentifiedParameterDraftChanges()) {
    ElMessage.warning('参数 Value 或类型已修改，请先点击“重新识别”')
    return
  }
  const groups = {}  // 按 replace_value + 原始值分组，避免整段文本替换时丢失 search_value
  visibleParamGroups.value.forEach(g => {
    g.results.forEach(group => {
      group._flatMatches.forEach(m => {
        if (!m._checked) return
        if (!isParameterMatchReplaceable(m, g.key)) return
        const isDeparameterize = paramMatchStatus.value === 'parameterized'
        const searchValue = isDeparameterize ? m.replaced : (m.value || '')
        const rv = isDeparameterize ? (m.paramValue ?? '') : m.replaced
        if (searchValue === rv) return
        const restoreType = isDeparameterize ? (m.paramType || g.paramType || 'string') : null
        const groupKey = `${rv}\u0000${searchValue}\u0000${restoreType || ''}`
        if (!groups[groupKey]) groups[groupKey] = { replaceValue: rv, searchValue: m.value || '', restoreType, targets: [] }
        groups[groupKey].searchValue = searchValue
        const t = { type: group.type === 'interface' ? 'interface' : 'testcase', field_path: m.path }
        if (group.type === 'interface') t.id = group.id
        else t.id = group.id
        groups[groupKey].targets.push(t)
      })
    })
  })
  const keys = Object.keys(groups)
  if (keys.length === 0 && parameterUpdates.length === 0) { ElMessage.warning('请至少选择一项或修改参数设置'); return }
  if (keys.length > 0 && paramMatchStatus.value === 'conflict') {
    try {
      await ElMessageBox.confirm(
        '异常项可能存在引用冲突或类型变化风险，请确认已经逐条检查。是否继续替换选中项？',
        '确认处理异常项',
        { confirmButtonText: '确认替换', cancelButtonText: '取消', type: 'warning' }
      )
    } catch { return }
  }

  paramReplacing.value = true
  try {
    saveParamHeaderPreference(paramIncludeHeaders.value)
    await batchReplace({
      parameter_set_id: psId.value,
      parameter_updates: parameterUpdates,
      replacements: keys.map(key => {
        const group = groups[key]
        return {
          search_value: group.searchValue,
          replace_value: group.replaceValue,
          targets: group.targets,
          ...(group.restoreType ? { restore_type: group.restoreType } : {})
        }
      })
    })
    commitParameterDrafts()
    await loadData()
    hiddenHeaderReferenceCount.value = await countHeaderReferencesForItems(_paramItems)
    await runParameterize({ keepStatus: true })
  } catch { }
  finally { paramReplacing.value = false }
}

async function reidentifyParameterization() {
  const draftError = validateParameterDrafts()
  if (draftError) { ElMessage.warning(draftError); return }
  await runParameterize({ keepStatus: true })
}

onMounted(() => { loadData() })
</script>

<style scoped>
.psd-page { max-width: 100%; height: 100%; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.page-header { margin-bottom: 20px; }
.search-toolbar-panel {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  flex-shrink: 0;
  margin-bottom: 16px;
  padding: 16px 16px 12px;
  border: 1px solid #d7e1ec;
  border-radius: 10px;
  background: #f3f6fa;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: #c2cedb transparent;
}
.parameter-toolbar-row {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 16px;
  width: max-content;
  min-width: max-content;
}
.page-header, .parameter-pagination { flex-shrink: 0; }
.parameter-toolbar-row :deep(.el-input) {
  flex: 0 0 180px;
}
.parameter-toolbar-row :deep(.el-button) {
  height: 34px;
  min-height: 34px;
  margin-left: 0 !important;
  flex: 0 0 auto;
  box-sizing: border-box;
}
.search-input { width: 180px; }
.candidate-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  margin-bottom: 12px;
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
  flex-wrap: wrap;
}
.candidate-query {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.candidate-search-input { width: 320px; }
.candidate-location-select { width: 230px; }
.candidate-count {
  margin-left: auto;
  max-width: 100%;
  padding: 6px 10px;
  border: 1px solid #edf1f7;
  border-radius: 6px;
  background: #fff;
  color: #606266;
  white-space: normal;
}
.candidate-tabs {
  flex: 0 0 auto;
  margin-bottom: 10px;
}
.candidate-tabs :deep(.el-tabs__header) {
  margin: 0;
}
.candidate-dialog :deep(.el-dialog) {
  max-width: calc(100vw - 48px);
  max-height: calc(100vh - 64px);
  border-radius: 16px;
  display: flex;
  flex-direction: column;
}
.candidate-dialog :deep(.el-dialog__header) { padding: 18px 20px 14px 28px; border-bottom: 1px solid #edf1f7; background: linear-gradient(135deg, #f8fbff 0%, #ffffff 65%); }
.candidate-dialog :deep(.el-dialog__body) {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 20px 28px 14px;
  background: #fbfcff;
}
.candidate-dialog :deep(.el-dialog__footer) {
  flex: 0 0 auto;
  border-top: 1px solid #edf1f7;
  background: #fff;
}
.candidate-table-wrap {
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
  overflow: hidden;
  padding-bottom: 8px;
}
.candidate-table {
  width: 100%;
}
.candidate-table :deep(.candidate-nowrap-column .cell),
.candidate-table :deep(th.candidate-nowrap-column .cell) {
  overflow: visible;
  white-space: nowrap;
}
.candidate-table :deep(.candidate-nowrap-column .el-tag) {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
}
.candidate-table :deep(.el-table__inner-wrapper),
.candidate-table :deep(.el-table__body-wrapper),
.candidate-table :deep(.el-scrollbar),
.candidate-table :deep(.el-scrollbar__wrap) {
  overflow-x: hidden !important;
}
.candidate-table :deep(.el-scrollbar__bar.is-vertical) {
  right: 6px;
  width: 12px;
  border-radius: 999px;
  background: #eef4fb;
  opacity: 1;
}
.candidate-table :deep(.el-scrollbar__bar.is-horizontal) {
  display: none;
}
.candidate-table :deep(.el-scrollbar__bar .el-scrollbar__thumb) {
  border-radius: 999px;
  background-color: #9fb3ca;
  opacity: 1;
}
.candidate-table :deep(.candidate-row-ignored) {
  color: #a8abb2;
  background: #fafafa;
}
.candidate-table :deep(.candidate-row-ignored .el-input__wrapper),
.candidate-table :deep(.candidate-row-ignored .el-select__wrapper) {
  background: #f5f6f7;
  box-shadow: 0 0 0 1px #e8edf3 inset;
}
.candidate-table :deep(.el-scrollbar__bar .el-scrollbar__thumb:hover) {
  background-color: #7f98b3;
}
.candidate-table :deep(.candidate-source-summary-column .cell) {
  overflow: hidden;
  padding-left: 12px;
  padding-right: 12px;
}
.candidate-table :deep(th.candidate-expand-column),
.candidate-table :deep(td.candidate-expand-column),
.candidate-table :deep(.candidate-expand-column .cell) {
  width: 0 !important;
  min-width: 0 !important;
  padding: 0 !important;
  border: 0 !important;
  overflow: hidden !important;
}
.candidate-table :deep(.candidate-expand-column .el-table__expand-icon) {
  display: none !important;
}
.parameter-item-table :deep(.el-table__header .cell),
.parameter-item-table :deep(.el-table__body .cell) {
  white-space: nowrap;
}
.parameter-item-table :deep(.el-table__body .cell) {
  overflow: hidden;
  text-overflow: ellipsis;
}
.parameter-item-link {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}
.parameter-table-scroll {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  scrollbar-color: #aeb8c4 #f7f9fc;
}
.parameter-table-scroll.is-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.parameter-table-scroll.is-empty > :deep(.global-empty) { width: 100%; }
.parameter-table-scroll :deep(.el-table) { width: 100%; min-width: 0; }
.parameter-table-scroll::-webkit-scrollbar { width: 8px; height: 8px; }
.parameter-table-scroll::-webkit-scrollbar-track { background: #f7f9fc; border-radius: 4px; }
.parameter-table-scroll::-webkit-scrollbar-thumb { background: #aeb8c4; border: 2px solid #f7f9fc; border-radius: 4px; }
.parameter-table-scroll::-webkit-scrollbar-thumb:hover { background: #8996a5; }
.parameter-pagination {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  min-height: 40px;
  padding: 12px 0 0;
}
.candidate-source-detail {
  padding: 6px 20px;
  color: #606266;
  font-size: 12px;
  background: #f8fbff;
}
.candidate-source-detail-row {
  padding: 8px 12px;
  border-bottom: 1px dashed #edf1f7;
}
.candidate-source-detail-row:last-child { border-bottom: 0; }
.candidate-source-detail-name {
  min-width: 0;
  max-width: min(48vw, 520px);
  padding: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #303133;
  font-weight: 500;
}
.candidate-source-detail-main,
.candidate-source-detail-meta {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 8px;
}
.candidate-source-detail-main { line-height: 22px; }
.candidate-source-detail-location {
  flex: 0 0 auto;
  color: #606266;
  white-space: nowrap;
}
.candidate-source-detail-meta {
  margin-top: 5px;
  padding-left: 58px;
  color: #909399;
  line-height: 20px;
}
.candidate-source-detail-meta span {
  max-width: min(28vw, 320px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.candidate-source-summary {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  line-height: 18px;
}
.candidate-source-summary-clickable {
  cursor: pointer;
  border-radius: 6px;
  padding: 4px 6px;
  margin: -4px -6px;
  transition: background-color .15s ease;
}
.candidate-source-summary-clickable:hover,
.candidate-source-summary-clickable:focus-visible {
  outline: none;
  background: #eef6ff;
}
.candidate-source-summary strong { color: #303133; font-size: 13px; }
.candidate-source-summary span { color: #909399; font-size: 12px; }
.candidate-source-detail-empty { color: #909399; }
.empty-state { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 80px 0; color: #8c8c8c; }
.param-dialog :deep(.el-dialog) { max-width: calc(100vw - 48px); }
.param-dialog :deep(.el-dialog__header) { padding: 24px 40px 16px; border-bottom: 1px solid #eef1f6; }
.param-dialog :deep(.el-dialog__title) { font-size: 18px; font-weight: 700; color: #303133; }
.param-dialog :deep(.el-dialog__body) { padding: 20px 40px 24px; }
.param-loading, .param-error, .param-empty-status { padding: 40px 0; text-align: center; color: #909399; font-size: 13px; }
.param-loading p { margin: 12px 0 0; color: #909399; }
.param-error { color: #f56c6c; }
.param-dialog-body {
  display: flex;
  flex-direction: column;
  max-height: min(64vh, 620px);
  min-height: 0;
  overflow: hidden;
  padding-right: 4px;
}
.param-dialog :deep(.el-dialog__header) { padding: 18px 20px 14px 24px; border-bottom: 1px solid #edf1f7; }
.param-dialog :deep(.el-dialog__body) { padding: 18px 24px 16px; }
.param-scan-options {
  flex: 0 0 auto;
  display: flex; justify-content: space-between; align-items: center; gap: 16px;
  margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid #edf1f7;
}
.param-source-query { display: flex; align-items: center; gap: 8px; min-width: 0; }
.param-source-input { width: min(430px, 42vw); }
.param-scan-preference { display: flex; align-items: center; gap: 10px; min-width: 0; }
.param-scan-note { color: #909399; font-size: 12px; white-space: nowrap; }
.param-action-bar {
  flex: 0 0 auto;
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 14px; padding: 0 0 12px;
  border-bottom: 1px solid #edf1f7;
  background: #fff;
}
.param-status-tabs {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.param-status-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 5px 8px 5px 10px;
  border: 1px solid #dfe6f0;
  border-radius: 8px;
  background: #fff;
  color: #606266;
  font-size: 13px;
  cursor: pointer;
  transition: all .16s ease;
}
.param-status-tab strong {
  min-width: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: #f2f6fc;
  color: #606266;
  font-size: 12px;
  line-height: 20px;
}
.param-status-tab.active {
  border-color: #409eff;
  background: #eef6ff;
  color: #1677ff;
  font-weight: 700;
}
.param-status-tab.active strong {
  background: #409eff;
  color: #fff;
}
.param-status-help {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  color: #909399;
  cursor: help;
}
.param-status-help:hover {
  color: #1677ff;
  background: #fff;
}
.param-bulk-actions { display: flex; gap: 8px; }
.param-selection-count { margin-left: auto; color: #909399; font-size: 13px; white-space: nowrap; }
.param-results-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}
.interface-param-group {
  margin-bottom: 12px;
  border: 1px solid #dfe8f5;
  border-radius: 10px;
  background: #fff;
  overflow: hidden;
}
.interface-group-head {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 12px 14px;
  border-bottom: 1px solid #e8eef6;
  background: linear-gradient(135deg, #f5f9ff 0%, #fbfdff 100%);
  cursor: pointer;
}
.interface-group-head:hover { background: #eef6ff; }
.interface-group-main { flex: 1; min-width: 0; }
.interface-group-title-row { display: flex; align-items: center; gap: 8px; min-width: 0; }
.interface-group-title-row strong { min-width: 0; max-width: min(62%, 520px); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #303133; font-size: 14px; }
.interface-group-open-detail { flex: 0 0 auto; margin: 0; padding: 0; font-size: 12px; font-weight: 500; white-space: nowrap; }
.interface-group-stats { color: #909399; font-size: 12px; white-space: nowrap; }
.interface-group-url { margin-top: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #7b8794; font-family: SFMono-Regular, Consolas, monospace; font-size: 12px; }
.interface-group-chevron { flex: 0 0 auto; color: #909399; font-size: 18px; line-height: 1; transform: rotate(0deg); transition: transform .16s ease; }
.interface-group-chevron.expanded { transform: rotate(180deg); }
.interface-group-body { padding: 2px 12px 12px; background: #fcfdff; }
.interface-parameter-block + .interface-parameter-block { margin-top: 8px; }
.param-group-title {
  display: flex; align-items: center; flex-wrap: wrap; gap: 6px;
  margin: 4px 0 8px; color: #303133; font-size: 14px; font-weight: 700;
}
.param-group-title code {
  padding: 2px 8px; border-radius: 4px; background: #f0f9eb;
  color: #529b2e; font-family: SFMono-Regular,Consolas,monospace; font-size: 12px;
}
.param-group-edit { margin-left: auto; flex: 0 0 auto; }
.param-group-key, .param-group-arrow { color: #909399; font-weight: 400; }
.param-inline-editor {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin: -2px 0 10px;
  padding: 10px 12px;
  border: 1px solid #dfe8f5;
  border-radius: 8px;
  background: #f8fbff;
}
.param-inline-field { display: flex; align-items: center; gap: 6px; min-width: 0; }
.param-inline-field > span { color: #606266; font-size: 12px; white-space: nowrap; }
.param-inline-value { flex: 1 1 280px; }
.param-inline-value :deep(.el-input) { min-width: 0; }
.param-inline-field :deep(.el-select) { width: 110px; }
.param-inline-hint { color: #909399; font-size: 12px; }
.param-target-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}
.param-target-section {
  min-width: 0;
  padding: 12px;
  border: 1px solid #e8edf3;
  border-radius: 10px;
  background: #fbfcff;
}
.param-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.param-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  color: #303133;
  font-size: 13px;
  font-weight: 700;
}
.param-section-count {
  color: #909399;
  font-size: 12px;
  white-space: nowrap;
}
.param-section-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 112px;
  border: 1px dashed #dfe6f0;
  border-radius: 8px;
  background: #fff;
  color: #a8abb2;
  font-size: 13px;
}
.param-target-card { margin-bottom: 12px; border: 1px solid #dce8f6; border-radius: 8px; overflow: hidden; background: #fff; }
.param-target-card:last-child { margin-bottom: 0; }
.param-target-head {
  padding: 10px 14px;
  background: linear-gradient(135deg, #f2f8ff 0%, #f9fbff 100%);
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  cursor: pointer;
  border-bottom: 1px solid #e4eefb;
  transition: all .16s ease;
}
.param-target-head:hover {
  background: #eaf4ff;
  box-shadow: inset 3px 0 0 #409eff;
}
.param-target-head:focus-visible { outline: 2px solid #409eff; outline-offset: -2px; }
.param-target-name { flex: 0 1 auto; min-width: 0; max-width: min(60%, 520px); color: #303133; font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.param-target-count { color: #909399; font-size: 12px; white-space: nowrap; }
.param-target-open-detail {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #e8f3ff;
  color: #1677ff;
  font-size: 12px;
  font-weight: 700;
}
.param-target-open-detail::after {
  content: '>';
  font-family: SFMono-Regular,Consolas,monospace;
  font-size: 12px;
}
.param-match-row { padding: 10px 14px; border-top: 1px solid #f0f2f5; }
.param-match-row:first-of-type { border-top: 0; }
.param-match-row.is-parameterized { background: #f8fcf5; }
.param-match-row.is-conflict { background: #fffaf2; }
.param-match-checkbox { width: 100%; }
.param-match-checkbox :deep(.el-checkbox__label) { width: 100%; }
.param-match-content { display: flex; flex-direction: column; gap: 7px; width: 100%; min-width: 0; }
.param-match-content.no-checkbox { padding-left: 28px; }
.param-match-main, .param-match-fields {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex-wrap: wrap;
}
.param-match-type { color: #606266; font-size: 13px; white-space: nowrap; font-weight: 600; }
.param-confidence-tag { margin-left: 6px; flex-shrink: 0; }
.param-location-tag { flex-shrink: 0; }
.field-label { color: #909399; font-size: 12px; white-space: nowrap; }
.param-old-value, .param-new-value, .param-current-value, .param-conflict-value {
  padding: 2px 8px; border-radius: 4px; font-family: SFMono-Regular,Consolas,monospace;
  font-size: 12px; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.param-old-value { background: #fef0f0; color: #c45656; text-decoration: line-through; }
.param-new-value { background: #fff1f0; color: #cf1322; border: 1px solid #ffa39e; font-weight: 700; }
.param-current-value { background: #f4f6f8; color: #606266; }
.param-conflict-value { background: #fdf6ec; color: #b88230; border: 1px solid #f5dab1; }
.param-row-arrow { color: #a8abb2; font-size: 14px; }
.param-reason { color: #b88230; font-size: 12px; line-height: 20px; }
.param-change-detail { display: flex; flex-direction: column; gap: 14px; }
.param-change-hero {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #e8edf3;
  border-radius: 8px;
  background: #f7faff;
}
.param-change-hero div { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.param-change-hero strong { color: #303133; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.param-change-hero span { color: #909399; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.param-change-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.param-change-grid section {
  min-width: 0;
  border: 1px solid #edf1f7;
  border-radius: 8px;
  background: #fbfcfe;
  overflow: hidden;
}
.param-change-title {
  padding: 9px 12px;
  border-bottom: 1px solid #edf1f7;
  color: #606266;
  font-size: 13px;
  font-weight: 700;
}
.param-change-grid pre {
  margin: 0;
  min-height: 82px;
  max-height: 220px;
  overflow: auto;
  padding: 12px;
  color: #303133;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: SFMono-Regular,Consolas,monospace;
}
.param-change-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: #909399;
  font-size: 12px;
}
.param-change-meta code {
  padding: 2px 8px;
  border-radius: 4px;
  background: #f0f7ff;
  color: #1677ff;
  font-family: SFMono-Regular,Consolas,monospace;
}
.param-change-warning {
  padding: 9px 12px;
  border: 1px solid #f5dab1;
  border-radius: 8px;
  background: #fdf6ec;
  color: #b88230;
  font-size: 13px;
}
.param-dialog-footer { margin-top: 16px; padding-top: 12px; border-top: 1px solid #ebeef5; text-align: right; }
.param-detail-dialog :deep(.el-dialog) { display: flex; flex-direction: column; max-height: min(92vh, 820px); }
.param-detail-dialog :deep(.el-dialog__header) { padding: 18px 24px 12px; border-bottom: 1px solid #edf1f7; }
.param-detail-dialog :deep(.el-dialog__body) { flex: 1; overflow: hidden; padding: 18px 24px 22px; }
.detail-scroll { max-height: calc(92vh - 140px); overflow-y: auto; padding-right: 2px; }
.detail-hero {
  display: flex; align-items: center; gap: 12px; padding: 12px 14px; margin-bottom: 14px;
  background: #f7f9fc; border: 1px solid #e8edf3; border-radius: 8px;
}
.method-tag { min-width: 58px; text-align: center; }
.detail-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.detail-main strong { color: #303133; font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.detail-main span { color: #909399; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.detail-panel { min-width: 0; }
.panel-title { font-weight: 600; font-size: 13px; color: #303133; margin: 12px 0 6px; }
.hit-panel {
  border: 1px solid #fde2e2; border-radius: 8px; background: #fffafa;
  padding: 10px 12px; margin-bottom: 12px;
}
.hit-panel.inner { margin-bottom: 10px; }
.hit-panel .panel-title { margin-top: 0; color: #c45656; }
.hit-row {
  min-height: 32px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 6px 0; border-top: 1px solid #fdecec;
}
.hit-row:first-of-type { border-top: 0; }
.hit-old, .hit-new {
  font-size: 12px; padding: 2px 8px; border-radius: 4px; max-width: 280px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.hit-old { background: #fef0f0; color: #c45656; text-decoration: line-through; }
.hit-new { background: #f0f9eb; color: #529b2e; font-weight: 600; }
.hit-arrow { color: #909399; }
.hit-state { color: #909399; font-size: 12px; margin-left: auto; }
.case-card { border: 1px solid #e8edf3; border-radius: 8px; padding: 12px; background: #fff; }
.case-desc { color: #606266; font-size: 13px; line-height: 1.7; padding: 8px 10px; background: #fbfcfe; border-radius: 6px; }
.muted-text { color: #909399; font-size: 13px; }
.code-block {
  background: #f7f9fc; border: 1px solid #edf1f7; padding: 10px; border-radius: 6px;
  font-size: 13px; font-family: SFMono-Regular,Consolas,monospace; white-space: pre-wrap;
  word-break: break-all; margin: 0; max-height: 220px; overflow: auto;
}
.code-block.compact { max-height: 140px; }
.code-block.request-preview {
  color: #1f2d3d;
  font-size: 14px;
  line-height: 1.8;
}
.code-block :deep(.param-hit), :deep(.param-hit) {
  background: #f56c6c;
  color: #fff;
  border-radius: 3px;
  padding: 1px 3px;
}
.code-block :deep(.param-replace-target), :deep(.param-replace-target) {
  color: #1677ff;
  font-weight: 700;
}
.code-block :deep(button.param-replace-target), :deep(button.param-replace-target) {
  border: 0;
  padding: 1px 4px;
  border-radius: 4px;
  background: #eaf3ff;
  cursor: pointer;
  font-family: inherit;
  line-height: 1.4;
}
.code-block :deep(button.param-replace-target:hover), :deep(button.param-replace-target:hover) {
  color: #0958d9;
  background: #d8eaff;
  text-decoration: underline;
}
.code-block :deep(.param-replace-target.is-empty), :deep(.param-replace-target.is-empty) {
  color: #cf1322;
  background: #fff1f0;
  outline: 1px dashed #ffccc7;
}
.smart-dialog-header { display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 32px; }
.smart-dialog-title { color: #1f2d3d; font-size: 18px; font-weight: 700; letter-spacing: .2px; }
.smart-dialog-actions { display: inline-flex; align-items: center; gap: 4px; height: 32px; }
.smart-dialog-icon-btn { width: 32px; height: 32px; min-height: 32px; padding: 0; margin: 0 !important; display: inline-flex; align-items: center; justify-content: center; color: #7b8794; border-radius: 8px; }
.smart-dialog-icon-btn:hover { color: var(--nexus-primary); background: #eef6ff; }
.param-help-dialog :deep(.el-dialog__body) { max-height: calc(100vh - 220px); overflow-y: auto; padding: 8px 24px 4px; }
.help-content { display: flex; flex-direction: column; gap: 10px; }
.help-content p {
  margin: 0;
  padding: 10px 12px;
  border: 1px solid #edf1f7;
  border-radius: 8px;
  background: #fbfcfe;
  color: #606266;
  font-size: 13px;
  line-height: 1.7;
}
.param-help-tabs :deep(.el-tabs__header) { margin-bottom: 16px; }
.param-help-tabs :deep(.el-tabs__item) { height: 36px; line-height: 36px; }

@media (max-width: 768px) {
  .search-input { width: 100%; }
  .detail-grid { grid-template-columns: 1fr; }
  .detail-hero { align-items: flex-start; }
  .param-dialog :deep(.el-dialog) { width: calc(100vw - 24px) !important; max-width: calc(100vw - 24px); }
  .param-dialog-body { max-height: 66vh; }
  .param-action-bar, .param-scan-options { flex-wrap: wrap; justify-content: flex-start; }
  .param-source-query, .param-scan-preference { width: 100%; }
  .param-source-input { width: 100%; }
  .param-selection-count { width: 100%; margin-left: 0; }
  .param-target-layout { grid-template-columns: 1fr; }
}
</style>

<style>
/* 全局最大化样式（dialog 被 teleport 到 body，scoped 样式不生效） */
.el-dialog.candidate-dialog.maximized {
  width: 100vw !important;
  max-width: 100vw !important;
  height: 100vh !important;
  max-height: 100vh !important;
  margin: 0 !important;
  border-radius: 0 !important;
  display: flex !important;
  flex-direction: column !important;
}
.candidate-dialog.maximized .el-dialog__body {
  flex: 1 !important;
  max-height: none !important;
  min-height: 0 !important;
  overflow: hidden !important;
  display: flex !important;
  flex-direction: column !important;
}
.candidate-dialog.maximized .candidate-toolbar {
  flex: 0 0 auto;
}
.candidate-dialog.maximized .candidate-table-wrap {
  flex: 1 1 auto;
  min-height: 0;
  overflow-x: hidden;
}
.candidate-dialog.maximized .el-table {
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
}
</style>
