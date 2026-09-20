<template>
  <AdminTabsShell class="model-list-page">
    <div class="admin-page-title"><h2>AI模型配置</h2></div>
    <div class="page-header">
      <div class="model-tabs-row">
        <el-tabs :model-value="activeModelTab" class="model-tabs" @update:model-value="handleModelTabChange">
          <el-tab-pane label="我的模型" name="mine" />
          <el-tab-pane label="平台模型" name="platform" />
          <el-tab-pane v-if="isSuperuser" label="用户模型" name="users" />
        </el-tabs>
        <div v-if="isPlatformTab" class="platform-quota-summary" role="status">
          <span class="platform-quota-title">平台模型额度</span>
          <span v-if="isSuperuser" class="platform-quota-item"><span>普通用户每日</span><strong>{{ platformQuotaLimitLabel }}</strong></span>
          <span v-else class="platform-quota-item"><span>每日</span><strong>{{ platformQuotaLabel }}</strong></span>
          <span v-if="isSuperuser" class="platform-quota-item"><span>超管</span><strong>不受限制</strong></span>
          <span v-else class="platform-quota-item"><span>今日已用</span><strong>{{ platformQuota.today_used || 0 }} 次</strong></span>
          <span
            v-if="!isSuperuser"
            class="platform-quota-item platform-quota-remaining"
            :class="{ 'is-low': platformQuota.quota > 0 && Number(platformQuota.remaining || 0) <= 1, 'is-empty': platformQuota.quota > 0 && Number(platformQuota.remaining || 0) <= 0 }"
          >
            <span>剩余</span><strong>{{ platformQuotaRemainingLabel }}</strong>
          </span>
          <span v-if="isSuperuser && !hasAvailablePlatformModel" class="platform-quota-warning">当前无可用平台模型，额度暂不生效</span>
          <el-button v-if="isSuperuser" link type="primary" @click="openPlatformQuotaDialog">设置额度</el-button>
        </div>
      </div>
      <div class="list-toolbar">
        <el-form inline class="toolbar-form">
            <el-form-item v-if="isUserModelsTab" label="模型使用人">
              <el-input v-model="currentModelFilters.creator_name" :placeholder="isUserModelsTab ? '模型使用人' : '模型创建人'" clearable />
            </el-form-item>
            <el-form-item label="模型别名">
              <el-input v-model="currentModelFilters.model_name" placeholder="模型别名" clearable class="model-name-filter" />
            </el-form-item>
            <el-form-item label="模型名称">
              <el-input v-model="currentModelFilters.model_identifier" placeholder="模型名称" clearable class="model-identifier-filter" />
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="currentModelFilters.enabled" placeholder="全部状态" clearable class="model-status-filter filter-select">
                <el-option label="启用" value="enabled" />
                <el-option label="停用" value="disabled" />
              </el-select>
            </el-form-item>
            <el-form-item label="能力检测">
              <el-select v-model="currentModelFilters.connectivity_status" placeholder="全部能力检测" clearable class="model-capability-filter filter-select">
                <el-option label="已通过" value="passed" />
                <el-option label="未通过" value="failed" />
                <el-option label="未检测" value="unknown" />
              </el-select>
            </el-form-item>
            <el-form-item class="toolbar-button-item">
              <div class="toolbar-buttons">
                <el-button @click="searchModels">查询</el-button>
                <el-button @click="resetModelSearch">重置</el-button>
                <el-button @click="openRules">使用说明</el-button>
                <el-button v-if="isMineTab" type="primary" @click="openAdd('personal')">添加我的模型</el-button>
                <el-button v-if="isPlatformTab && isSuperuser" type="primary" @click="openAdd('platform')">添加平台模型</el-button>
              </div>
            </el-form-item>
          </el-form>
      </div>
    </div>

    <div class="scroll-area" v-loading="loading">
      <el-table :data="pageData" :fit="true" stripe class="full-table model-table" header-cell-class-name="no-wrap-header">
        <el-table-column v-if="isUserModelsTab" label="模型使用人" width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <el-button v-if="row.owner_user_id" link type="primary" class="user-cell user-link" @click="openUserDetail(row)">
              <span class="user-avatar-sm" :style="row.owner_avatar ? {} : { background: avatarColor(row.owner_user_id) }">
                <img v-if="row.owner_avatar" :src="row.owner_avatar" :alt="`${row.owner_name || '模型使用人'}头像`" />
                <span v-else>{{ row.owner_name?.charAt(0) || '?' }}</span>
              </span>
              <span class="user-name-text">{{ row.owner_name || '未知用户' }}</span>
            </el-button>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="模型别名" prop="name" width="130" show-overflow-tooltip>
          <template #default="{ row }">
                <el-link v-if="row.can_edit && !isUserModelsTab" type="primary" underline="never" @click="openEdit(row)">{{ row.name }}</el-link>
            <span v-else>{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="模型名称" prop="model" width="160" show-overflow-tooltip>
          <template #default="{ row }">
                <el-link v-if="row.can_edit && !isUserModelsTab" type="primary" underline="never" @click="openEdit(row)">{{ row.model }}</el-link>
            <span v-else>{{ row.model }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="showCreatorColumn" label="模型创建人" prop="creator_name" min-width="120" show-overflow-tooltip />
        <el-table-column label="状态" min-width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="isUserModelsTab" :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '停用' }}</el-tag>
            <el-switch
              v-else
              :model-value="row.enabled"
              size="small"
              :disabled="!row.can_edit"
              @change="(val) => toggleEnabled(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column label="能力检测" min-width="110" align="center">
          <template #default="{ row }"><el-tag :type="connectivityTagType(row.connectivity_status)" size="small">{{ connectivityLabel(row.connectivity_status) }}</el-tag></template>
        </el-table-column>
        <el-table-column v-if="isMineTab || (isPlatformTab && isSuperuser)" label="余额查询" min-width="140" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.can_query_balance && row.balance_query_enabled && row.balance_query_configured"
              link
              type="primary"
              size="small"
              :loading="balanceLoadingRowId === row.id"
              @click="checkRowBalance(row)"
            >查询余额</el-button>
            <el-tooltip v-else-if="row.balance_query_configured" :content="balanceQueryHint(row)" placement="top">
              <el-tag :type="balanceStatusTagType(row.balance_query_status)" size="small">{{ balanceStatusLabel(row.balance_query_status) }}</el-tag>
            </el-tooltip>
            <span v-else>未配置</span>
          </template>
        </el-table-column>
        <el-table-column v-if="!isPlatformTab" label="我的模型额度（次）" min-width="160" align="center">
          <template #default="{ row }">
            <el-button link class="quota-cell-button" @click="openPersonalQuotaDialog(row)">
              <el-tag :type="personalQuotaTagType(row)" size="small">{{ personalQuotaValue(row) }}</el-tag>
            </el-button>
          </template>
        </el-table-column>
        <el-table-column v-if="isUserModelsTab" label="平台模型额度（次）" min-width="150" align="center">
          <template #default="{ row }">
            <el-tag :type="platformQuotaTagType(row)" size="small">{{ platformQuotaValue(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="showCreatorColumn" label="创建时间" min-width="170" align="center">
          <template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="190" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">查看</el-button>
            <template v-if="row.can_edit && !isUserModelsTab">
              <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="doDelete(row)">删除</el-button>
            </template>
          </template>
        </el-table-column>
        <template #empty>
          <GlobalEmpty
            text="暂无数据"
            :action-text="isMineTab ? '添加我的模型' : ((isPlatformTab && isSuperuser) ? '添加平台模型' : '')"
            @action="openAdd(isPlatformTab ? 'platform' : 'personal')"
          />
        </template>
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

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="formVisible" :title="isEditing ? '编辑模型' : '添加模型'" width="min(980px, calc(100vw - 48px))" top="5vh" destroy-on-close class="model-dialog">
      <el-form :model="form" label-width="88px" class="model-form">
        <div class="model-form-layout">
          <div class="model-form-column">
            <el-form-item label="模型别名" required>
              <el-input v-model="form.name" placeholder="如：DeepSeek 分析" />
            </el-form-item>
            <!-- 模型范围由所在页签决定（我的模型 / 平台模型），新建与编辑均不展示、不可选，避免误改 -->
            <el-form-item label="模型名称" required>
              <div class="field-action-row">
                <el-autocomplete
                  ref="modelNameInputRef"
                  v-model="form.model"
                  class="field-main model-name-input"
                  placeholder="deepseek-chat"
                  clearable
                  :fetch-suggestions="queryModelOptions"
                  :trigger-on-focus="true"
                  @input="markModelKeywordFiltering"
                  @select="selectModelOption"
                >
                  <template #default="{ item }">
                    <div class="model-option" :class="{ 'is-current': item.value === form.model }">
                      <span class="model-option-name">{{ item.value }}</span>
                      <span v-if="item.value === form.model" class="model-option-current">当前</span>
                    </div>
                  </template>
                </el-autocomplete>
                <el-button @click="fetchModels" :loading="fetchLoading" :disabled="!form.base_url">获取模型</el-button>
              </div>
            </el-form-item>
            <el-form-item label="接口地址" required>
              <el-input v-model="form.base_url" placeholder="https://api.deepseek.com" />
            </el-form-item>
            <el-form-item label="接口协议">
              <el-radio-group v-model="form.provider">
                <el-radio value="openai-compat">OpenAI 兼容对话</el-radio>
                <el-radio value="responses">Responses</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="API Key">
                <div class="api-key-field">
                  <div class="field-action-row">
                    <el-input v-model="form.api_key" class="field-main" :placeholder="isEditing ? '输入新 Key 可覆盖已保存的 Key' : 'sk-...'" />
                  </div>
                <div v-if="isEditing && savedApiKey" class="masked-hint">当前已配置：{{ savedApiKey }}</div>
                <div class="form-tip">新 Key 会替换已有 Key，留空则不修改</div>
              </div>
            </el-form-item>
            <el-form-item label="能力检测" class="capability-check-row">
              <div class="capability-status">
                <el-tag :type="currentConfigConnectivityVerified ? 'success' : 'warning'">{{ currentConfigConnectivityVerified ? '当前配置已连通' : '未检测，仅供配置参考' }}</el-tag>
                <el-tag :type="reasoningTagType(editingReasoningStatus)">{{ reasoningLabel(editingReasoningStatus) }}</el-tag>
                <el-tag :type="usageTagType(editingUsageStatus)">{{ usageLabel(editingUsageStatus) }}</el-tag>
                <span v-if="editingConnectivityCheckedAt" class="form-tip">检测于：{{ formatBeijingTime(editingConnectivityCheckedAt) }}</span>
                <div class="capability-actions">
                  <el-button type="primary" plain @click="testCapabilities" :loading="capabilityTesting">能力检测</el-button>
                  <span class="form-tip">能力检测用于辅助检查配置，不影响模型启用。</span>
                </div>
              </div>
            </el-form-item>
          </div>

          <div class="model-form-column">
            <el-form-item label="最大输出">
              <div class="max-tokens-row">
                <el-input-number v-model="form.max_output_tokens" :min="1" :max="1000000" :step="1024" :controls="false" placeholder="留空=保守兜底" class="max-tokens-input" />
                <span class="max-tokens-unit">tokens / 次</span>
                <el-button text type="primary" class="max-tokens-ref" @click="tokenRefVisible = true">上限参考</el-button>
              </div>
              <div class="form-tip">建议设置，否则输出容易被截断。</div>
              <div class="form-tip">留空则使用模型默认上限；设置过大可能被渠道拒绝。</div>
            </el-form-item>
            <template v-if="form.scope === 'personal'">
              <el-form-item label="日额度" required>
                <el-input-number v-model="form.daily_limit" :min="1" :max="99999" controls-position="right" style="width: 100%" />
                <div class="form-tip">必填且大于 0；达到限额后当天不再调用该模型。</div>
                <div class="form-tip">为保障正常使用，建议设置充裕的日额度。</div>
                <div class="form-tip">系统默认优先使用平台模型；平台模型不可用或额度不足时，再使用我的模型。您也可以在实际使用前手动选择模型。</div>
              </el-form-item>
            </template>
            <el-form-item label="余额查询">
              <div class="config-summary-row">
                <el-button @click="openBillingDialog">余额配置</el-button>
                <el-tag :type="form.balance_query_enabled ? 'success' : 'info'" size="small">{{ form.balance_query_enabled ? '已启用' : '未启用' }}</el-tag>
                <span v-if="!canConfigureBalance" class="summary-text">仅模型创建人可配置和测试</span>
                <span v-else class="summary-text">{{ form.balance_query_config?.url || '未配置余额接口' }}</span>
              </div>
            </el-form-item>
            <el-form-item label="状态" class="switch-pair-row">
              <el-switch
                :model-value="form.enabled"
                active-text="启用"
                inactive-text="停用"
                @change="handleFormEnabledChange"
              />
            </el-form-item>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="saveModel" :loading="saveLoading" :disabled="saveLoading">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="platformQuotaVisible" title="设置平台模型日额度" width="440px" append-to-body>
      <p class="platform-setting__hint">所有普通用户按统一日额度独立计数；额度大于 0 且存在可用平台模型时才可使用。</p>
      <el-form label-width="92px">
        <el-form-item label="日额度" required>
          <el-input-number v-model="platformQuotaForm.daily_limit" :min="1" :max="99999" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="platformQuotaVisible = false">取消</el-button>
        <el-button type="primary" :loading="platformQuotaSaving" @click="savePlatformQuota">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="personalQuotaVisible" title="设置我的模型日额度" width="420px" append-to-body>
      <el-form label-width="92px">
        <el-form-item label="日额度" required>
          <el-input-number v-model="personalQuotaForm.daily_limit" :min="1" :max="99999" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="personalQuotaVisible = false">取消</el-button>
        <el-button type="primary" :loading="personalQuotaSaving" @click="savePersonalQuota">保存</el-button>
      </template>
    </el-dialog>

    <!-- 模型能力检测结果（三合一：连通性 / 思考模式 / 用量统计） -->
    <el-dialog v-model="capabilityDialogVisible" title="能力检测结果" width="520px" append-to-body :close-on-click-modal="!capabilityTesting" :show-close="!capabilityTesting">
      <div v-if="capabilityTesting" class="connectivity-loading">
        <el-icon class="is-loading" :size="34"><Loading /></el-icon>
        <div class="connectivity-loading-title">正在进行能力检测</div>
      <div class="connectivity-loading-tip">系统会用当前接口地址、模型名称和 API Key 发起一次真实调用，判定连通性和思考能力；用量信息仅在流中顺带采集，请稍候。</div>
      </div>
      <!-- 服务商原始返回：在同一弹窗内切换视图，避免在「编辑模型 → 检测结果」之上再叠一层弹窗 -->
      <div class="provider-error-view" v-else-if="capabilityResult && capabilityDetailVisible">
        <div class="provider-error-title">服务商返回（已脱敏）</div>
        <pre class="provider-error-text">{{ capabilityResult.providerError }}</pre>
      </div>
      <div class="connectivity-result" v-else-if="capabilityResult">
        <template v-if="capabilityResult.ok">
          <div class="result-detail">
            <div class="result-item">
              <span class="result-label">连通性</span>
              <el-tag type="success" size="small">已通过</el-tag>
            </div>
            <div class="result-item">
              <span class="result-label">思考模式</span>
              <el-tag :type="reasoningTagType(capabilityResult.reasoning)" size="small">{{ reasoningLabel(capabilityResult.reasoning) }}</el-tag>
            </div>
            <div class="result-item">
              <span class="result-label">用量统计</span>
              <el-tag :type="usageTagType(capabilityResult.usage)" size="small">{{ usageLabel(capabilityResult.usage) }}</el-tag>
            </div>
          </div>
        </template>
        <div class="result-detail result-error" v-else>
          <span>{{ capabilityResult.message || '未知错误' }}</span>
          <el-button
            v-if="capabilityResult.providerError"
            type="primary"
            link
            class="provider-error-entry"
            @click="capabilityDetailVisible = true"
          >查看服务商返回</el-button>
        </div>
      </div>
      <template #footer>
        <el-button v-if="capabilityTesting" type="danger" plain @click="cancelCapabilityTest">终止检测</el-button>
        <template v-if="capabilityDetailVisible">
          <el-button @click="capabilityDetailVisible = false">返回</el-button>
          <el-button type="primary" plain @click="copyProviderError">复制</el-button>
        </template>
        <el-button type="primary" :disabled="capabilityTesting" @click="capabilityDialogVisible = false">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="billingDialogVisible" title="余额查询配置" width="700px" append-to-body>
      <el-form label-width="100px">
        <el-form-item label="预置方案">
          <el-select v-model="billingForm.preset" style="width: 100%" @change="applyBillingPreset">
            <el-option v-for="item in balancePresetOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="余额接口" required>
          <el-input
            v-model="billingForm.url"
            :placeholder="billingUrlPlaceholder"
            @input="markBillingChanged"
          />
        </el-form-item>
        <el-form-item label="请求方法">
          <el-radio-group v-model="billingForm.method" @change="markBillingChanged">
            <el-radio value="GET">GET</el-radio>
            <el-radio value="POST">POST</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="认证信息">
          <div class="billing-credential-summary">
            {{ hasModelCredential ? '使用当前模型已配置的 API Key' : '未配置 API Key，可使用下方请求头认证' }}
            <div class="hint-text">余额配置弹窗不会再次展示或要求输入 API Key。</div>
          </div>
        </el-form-item>
        <el-form-item label="余额字段">
          <el-input
            v-model="billingForm.balance_path"
            placeholder="例如：$.data.balance；留空时自动识别常见字段"
            @input="markBillingFieldChanged"
          />
        </el-form-item>
        <el-form-item label="附加请求头">
          <div class="billing-header-list">
            <div v-for="(header, index) in billingForm.headers" :key="index" class="billing-header-row">
              <el-input v-model="header.key" placeholder="请求头名称" @input="markBillingChanged" />
              <el-input v-model="header.value" placeholder="请求头值" show-password @input="markBillingChanged" />
              <el-button text type="danger" @click="removeBillingHeader(index)">删除</el-button>
            </div>
            <el-button text type="primary" @click="addBillingHeader">添加请求头</el-button>
          </div>
        </el-form-item>
        <el-form-item label="接口响应" v-if="billingResponsePreview">
          <div class="billing-response-panel">
            <div class="billing-response-header">
              <span>最近一次测试响应</span>
              <el-tag :type="billingTestPassed ? 'success' : 'warning'" size="small">{{ billingTestPassed ? '余额字段验证通过' : '请求成功，请确认余额字段' }}</el-tag>
            </div>
            <pre class="billing-response-json">{{ billingResponsePreview }}</pre>
            <div class="billing-candidate-block">
              <div class="billing-candidate-title">自动识别字段（复制后手动填入）</div>
              <div v-if="billingCandidates.length" class="billing-candidate-list">
                <div v-for="candidate in billingCandidates" :key="candidate.path" class="billing-candidate-row">
                  <span class="billing-candidate-path">{{ candidate.path }}<span class="billing-candidate-value">余额：{{ candidate.value }}</span></span>
                  <el-button text type="primary" size="small" @click="copyBalancePath(candidate.path)">复制字段</el-button>
                </div>
              </div>
              <div v-else class="hint-text">暂未识别到余额字段，请根据上方响应手动填写后重新测试。</div>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="启用查询">
          <div class="billing-enable-row">
            <el-switch v-model="billingForm.enabled" :disabled="!billingTestPassed" />
            <span class="hint-text">测试通过后才能启用</span>
          </div>
        </el-form-item>
      </el-form>
      <div class="billing-note">
        <div class="billing-note-title">展示规则</div>
        <div>余额查询仅在模型配置人主动查询时执行，不参与 AI 调用后的费用计算。</div>
        <div>支持 DeepSeek、CC Switch 和自定义接口；接口地址、请求头和原始响应均不会向其他用户展示。</div>
      </div>
      <template #footer>
        <el-button @click="billingDialogVisible = false">取消</el-button>
        <el-button @click="testBilling" :loading="billingTesting">测试接口</el-button>
        <el-button type="primary" @click="confirmBilling">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rulesVisible" :title="rulesScope === 'platform' ? '平台模型使用说明' : '我的模型使用说明'" width="620px" append-to-body>
      <section v-if="rulesScope === 'platform'" class="rules-section">
        <h4>什么是平台模型</h4>
        <p>平台模型由平台统一配置，供符合条件的用户共同使用。普通用户只能看到已启用的平台模型；超级管理员可以查看和管理全部平台模型。</p>
        <h4>模型优先级</h4>
        <p>系统默认优先使用平台模型；平台模型不可用或额度不足时，再使用我的模型。平台模型和我的模型分别按照模型 ID 升序排列。您也可以在实际使用前手动选择模型。</p>
        <h4>额度与权限</h4>
        <p>平台模型使用平台统一的平台模型日额度，非超级管理员用户按统一标准分别享有额度；超级管理员不受平台模型调用次数限制。普通用户不能修改平台模型配置，平台模型统一由超级管理员配置和维护。</p>
      </section>
      <section v-else class="rules-section">
        <h4>什么是我的模型</h4>
        <p>我的模型是由您自行配置的模型，仅供您本人使用。所有字段配置均由您自行维护。</p>
        <h4>模型优先级</h4>
        <p>系统默认优先使用平台模型；平台模型不可用或额度不足时，再使用我的模型。平台模型和我的模型分别按照模型 ID 升序排列。您也可以在实际使用前手动选择模型。</p>
        <h4>额度与权限</h4>
        <p>我的模型列表中的模型，可单独设置日额度；额度用尽后，当天不会再自动调用该模型。您可以配置、检测、启停和删除我的模型列表中的所有模型。</p>
      </section>
      <template #footer><el-button type="primary" @click="rulesVisible = false">知道了</el-button></template>
    </el-dialog>

    <AiModelDetailDialog v-model="detailVisible" :model="detailRow" :viewer-mode="detailViewerMode" />
    <UserDialog v-model="userDetailVisible" :user-id="userDetailId" mode="view" />

    <!-- 常见模型输出上限参考 -->
    <el-dialog v-model="tokenRefVisible" title="常见模型单次输出上限参考" width="760px" append-to-body>
      <div class="token-ref-note">云端上限以公开模型文档为参考，实际可用值仍以当前服务商账户和接口限制为准；本地建议会预留输入和思考空间，实际受 Ollama / vLLM 的上下文长度、显存和部署参数限制。点击右侧「复制」可直接填入上方「最大输出」。</div>
      <el-table :data="tokenRefRows" size="small" class="token-ref-table" border header-cell-class-name="no-wrap-header">
        <el-table-column prop="category" label="类型" width="96" />
        <el-table-column prop="model" label="模型" min-width="280" show-overflow-tooltip />
        <el-table-column prop="tokens" label="输出上限(tokens)" width="150" align="center" />
        <el-table-column label="操作" width="110" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="applyTokenRef(row.tokens)">复制填入</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="token-ref-tip">云端中转服务可能低于模型公开上限，请以当前账户和接口限制为准；本地模型应先确认运行时上下文长度，再按显存余量设置。处理长需求或批量生成测试用例前，请确认最大输出能够覆盖预期内容。</div>
      <template #footer>
        <el-button type="primary" @click="tokenRefVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </AdminTabsShell>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { getAiModels, getAiModelDetail, createAiModel, updateAiModel, deleteAiModel, checkAiModelBalance, fetchAiModels, getAiModelBalanceQueryConfig, setAiModelQuota, getAiModelQuotas, getAiPlatformQuotaSetting, setAiPlatformQuotaSetting, getAiQuota, testAiModelBilling, testAiModelBillingDraft, testAiModelCapabilities, testAiModelCapabilitiesDraft, resetAiModelCapabilities } from '@/api/ai'
import { formatBeijingTime } from '@/utils/beijingTime'
import { copyToClipboard } from '@/utils/clipboard'
import AiModelDetailDialog from './components/AiModelDetailDialog.vue'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import AdminTabsShell from '@/components/AdminTabsShell.vue'
import UserDialog from '@/components/UserDialog.vue'

const loading = ref(false)
const userStore = useUserStore()
const route = useRoute()
const router = useRouter()
const canEditModels = computed(() => true)
const isSuperuser = computed(() => !!userStore.userInfo?.is_superuser)
const models = ref([])
const personalQuotas = ref([])
const platformQuota = ref({ quota: null, today_used: 0, remaining: null, has_access: false })
const platformQuotaSetting = ref({ daily_limit: null })
const platformQuotaQueryFailed = ref(false)
const platformQuotaSettingQueryFailed = ref(false)
const personalQuotaQueryFailed = ref(false)
const platformQuotaVisible = ref(false)
const platformQuotaSaving = ref(false)
const platformQuotaForm = reactive({ daily_limit: 50 })
const personalQuotaVisible = ref(false)
const personalQuotaSaving = ref(false)
const selectedPersonalQuota = ref(null)
const personalQuotaForm = reactive({ daily_limit: 50 })
const activeModelTab = computed(() => route.meta.tab || 'mine')
const emptyModelFilters = () => ({ creator_name: '', model_name: '', model_identifier: '', enabled: '', connectivity_status: '' })
const modelFilters = reactive({ mine: emptyModelFilters(), platform: emptyModelFilters(), users: emptyModelFilters() })
const appliedModelFilters = reactive({ mine: emptyModelFilters(), platform: emptyModelFilters(), users: emptyModelFilters() })
const page = ref(1)
const pageSize = ref(10)
// 三页签：我的模型(mine，owner=本人)/平台模型(platform，scope=platform)/用户模型(users，仅超管，他人的我的模型)
const isMineTab = computed(() => activeModelTab.value === 'mine')
const isPlatformTab = computed(() => activeModelTab.value === 'platform')
const isUserModelsTab = computed(() => isSuperuser.value && activeModelTab.value === 'users')
const isCreatingPersonal = computed(() => !isEditing.value && form.value.scope === 'personal')
const quotaByModelId = computed(() => new Map(personalQuotas.value.map(item => [Number(item.model_id), item])))
const platformQuotaLabel = computed(() => platformQuotaQueryFailed.value
  ? '查询失败'
  : Number(platformQuota.value.quota) > 0 ? `${platformQuota.value.quota} 次 / 天` : '未配置')
const platformQuotaLimitLabel = computed(() => platformQuotaSettingQueryFailed.value
  ? '查询失败'
  : Number(platformQuotaSetting.value.daily_limit) > 0 ? `${platformQuotaSetting.value.daily_limit} 次 / 天` : '未配置')
const platformQuotaRemainingLabel = computed(() => platformQuotaQueryFailed.value
  ? '查询失败'
  : Number(platformQuota.value.quota) > 0 ? `${Math.max(0, Number(platformQuota.value.remaining || 0))} 次` : '未配置')
// 是否存在启用中的平台模型（后端返回的全局标志，与当前页签/分页无关）。
const hasAvailablePlatformModel = ref(false)
// 平台模型展示创建人；用户模型单独展示使用人。
const showCreatorColumn = computed(() => isPlatformTab.value)
const currentTabKey = computed(() => (isUserModelsTab.value ? 'users' : (isPlatformTab.value ? 'platform' : 'mine')))
const currentModelFilters = computed(() => modelFilters[currentTabKey.value])
const currentAppliedModelFilters = computed(() => appliedModelFilters[currentTabKey.value])
// 列表数据与总数均由后端按页签+筛选+分页返回，前端不再做客户端过滤/分页。
const total = ref(0)
const pageData = computed(() => models.value)
const formVisible = ref(false)
const isEditing = ref(false)
const saveLoading = ref(false)
const balanceLoading = ref(false)
const balanceLoadingRowId = ref(null)
const fetchLoading = ref(false)
const modelOptions = ref([])
const modelNameInputRef = ref(null)
// 输入框当前值是否应作为候选过滤的关键词：手动键入时为 true，选中/回显/获取模型后为 false。
const modelKeywordFiltering = ref(false)
const editingId = ref(null)
const editingOwnerId = ref(null)
const savedApiKey = ref('')
const billingDialogVisible = ref(false)
const billingTesting = ref(false)
const billingTestPassed = ref(false)
const billingResponsePreview = ref('')
const billingCandidates = ref([])
// 三合一「模型能力检测」：一次真实调用同时判定 连通性 / 思考模式 / 用量统计
const capabilityTesting = ref(false)
let capabilityAbortController = null
const capabilityDialogVisible = ref(false)
const capabilityResult = ref(null)
// 失败时是否切到「服务商返回」视图（同一弹窗内切换，不新增弹窗层级）
const capabilityDetailVisible = ref(false)
const connectivityVerified = ref(false)
const testedConnectionFingerprint = ref('')
const savedConnectionFingerprint = ref('')
const editingReasoningStatus = ref('unknown')
const editingReasoningProfile = ref('')
const editingUsageStatus = ref('unknown')
const editingConnectivityCheckedAt = ref(null)
const rulesVisible = ref(false)
const rulesScope = ref('platform')
const detailVisible = ref(false)
const detailRow = ref(null)
const userDetailVisible = ref(false)
const userDetailId = ref(null)
const detailViewerMode = computed(() => {
  if (isUserModelsTab.value) return 'superadmin'
  if (detailRow.value?.can_edit) return 'owner'
  return isSuperuser.value ? 'superadmin' : 'member'
})
function openRules() {
  rulesScope.value = isMineTab.value || isUserModelsTab.value ? 'mine' : 'platform'
  rulesVisible.value = true
}
const billingForm = ref({ preset: 'deepseek', url: '', enabled: false, method: 'GET', type: 'balance', headers: [], balance_path: '' })
const balancePresetOptions = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'cc_switch', label: 'CC Switch（填写部署地址）' },
  { value: 'custom', label: '自定义接口' },
]
const balancePresetDefaults = {
  deepseek: { url: 'https://api.deepseek.com/user/balance', method: 'GET', balance_path: '$.balance_infos[0].total_balance' },
  cc_switch: { url: '', method: 'GET', balance_path: '$.data.balance' },
  custom: { url: '', method: 'GET', balance_path: '' },
}
const billingUrlPlaceholder = computed(() => billingForm.value.preset === 'cc_switch'
  ? '填写当前 CC Switch 的余额接口地址'
  : 'https://api.example.com/balance')
const tokenRefVisible = ref(false)
const tokenRefRows = [
  { category: '云端官方', model: 'GPT-5.6（Sol）', tokens: 128000 },
  { category: '云端官方', model: 'Claude Opus 5', tokens: 128000 },
  { category: '云端官方', model: 'Gemini 3.1 Pro', tokens: 65536 },
  { category: '云端官方', model: 'Qwen3.7-Max', tokens: 65536 },
  { category: '云端官方', model: 'DeepSeek V4（Pro / Flash）', tokens: 384000 },
  { category: '云端官方', model: 'GLM-5', tokens: 128000 },
  { category: '本地建议', model: 'Qwen3 / Qwen3-Coder（32K 上下文）', tokens: 8192 },
  { category: '本地建议', model: 'Llama 3.3 / Gemma 3（32K 上下文）', tokens: 8192 },
  { category: '本地建议', model: 'Qwen3 / Llama 3.3（64K 上下文）', tokens: 16384 },
  { category: '本地建议', model: '高显存本地部署（256K 上下文）', tokens: 32768 },
]
function applyTokenRef(tokens) {
  form.value.max_output_tokens = tokens
  ElMessage.success(`已填入 ${tokens} tokens`)
  tokenRefVisible.value = false
}
const form = ref({ name: '', provider: 'openai-compat', base_url: '', model: '', api_key: '', scope: 'personal', enabled: false, balance_query_enabled: false, balance_query_config: {}, max_output_tokens: null, daily_limit: 50 })
const canConfigureBalance = computed(() => !isEditing.value || Number(editingOwnerId.value) === Number(userStore.userInfo?.id))
const hasModelCredential = computed(() => !!String(form.value.api_key || '').trim() || !!savedApiKey.value)
const connectionFingerprint = computed(() => JSON.stringify([form.value.provider, form.value.base_url?.trim(), form.value.model?.trim(), form.value.api_key?.trim() || savedApiKey.value]))
const currentConfigConnectivityVerified = computed(() => connectivityVerified.value && testedConnectionFingerprint.value === connectionFingerprint.value)
function resetCapabilityStateForConfigChange() {
  connectivityVerified.value = false
  testedConnectionFingerprint.value = ''
  editingReasoningStatus.value = 'unknown'
  editingReasoningProfile.value = ''
  editingUsageStatus.value = 'unknown'
  editingConnectivityCheckedAt.value = null
  capabilityResult.value = null
  capabilityDetailVisible.value = false
}
watch(
  () => form.value.model,
  (value, previousValue) => {
    if (!formVisible.value || String(value || '').trim() === String(previousValue || '').trim()) return
    resetCapabilityStateForConfigChange()
  },
  { flush: 'sync' },
)
const connectivityLabel = status => ({ passed: '已通过', failed: '未通过', unknown: '未检测' }[status] || '未检测')
const connectivityTagType = status => ({ passed: 'success', failed: 'danger', unknown: 'info' }[status] || 'info')
const reasoningLabel = status => ({ supported: '可展示思考', unsupported: '不支持展示', unknown: '未验证' }[status] || '未验证')
const reasoningTagType = status => ({ supported: 'success', unsupported: 'info', unknown: 'warning' }[status] || 'warning')
const usageLabel = status => ({ supported: '可统计用量', unsupported: '不返回用量', unknown: '未检测' }[status] || '未检测')
const usageTagType = status => ({ supported: 'success', unsupported: 'info', unknown: 'warning' }[status] || 'warning')
function buildModelQueryParams() {
  const filters = currentAppliedModelFilters.value
  const params = {
    tab: currentTabKey.value,
    page: page.value,
    page_size: pageSize.value,
  }
  if (filters.model_name && filters.model_name.trim()) params.model_name = filters.model_name.trim()
  if (filters.model_identifier && filters.model_identifier.trim()) params.model_identifier = filters.model_identifier.trim()
  if (filters.enabled) params.enabled = filters.enabled
  if (filters.connectivity_status) params.connectivity_status = filters.connectivity_status
  // “模型使用人”筛选仅用户模型页签有意义。
  if (currentTabKey.value === 'users' && filters.creator_name && filters.creator_name.trim()) {
    params.creator_name = filters.creator_name.trim()
  }
  return params
}
async function loadModels() {
  loading.value = true
  try {
    const [modelResult, quotaResult, platformSettingResult, platformQuotaResult] = await Promise.allSettled([
      getAiModels(buildModelQueryParams()), getAiModelQuotas(), getAiPlatformQuotaSetting(), getAiQuota(),
    ])
    if (modelResult.status === 'fulfilled') {
      const payload = modelResult.value || {}
      models.value = payload.items || []
      total.value = Number(payload.total || 0)
      hasAvailablePlatformModel.value = !!payload.has_available_platform_model
    } else {
      models.value = []
      total.value = 0
      hasAvailablePlatformModel.value = false
    }
    personalQuotaQueryFailed.value = quotaResult.status !== 'fulfilled'
    personalQuotas.value = quotaResult.status === 'fulfilled' ? (quotaResult.value || []) : []
    platformQuotaSettingQueryFailed.value = platformSettingResult.status !== 'fulfilled'
    platformQuotaSetting.value = platformSettingResult.status === 'fulfilled'
      ? (platformSettingResult.value || { daily_limit: null })
      : { daily_limit: null }
    platformQuotaQueryFailed.value = platformQuotaResult.status !== 'fulfilled'
    platformQuota.value = platformQuotaResult.status === 'fulfilled'
      ? (platformQuotaResult.value || { quota: null, today_used: 0, remaining: null, has_access: false })
      : { quota: null, today_used: 0, remaining: null, has_access: false }
  } catch {
    models.value = []
    total.value = 0
    personalQuotas.value = []
  }
  finally { loading.value = false }
}

function searchModels() {
  Object.assign(currentAppliedModelFilters.value, currentModelFilters.value)
  page.value = 1
  loadModels()
}

function resetModelSearch() {
  Object.assign(currentModelFilters.value, emptyModelFilters())
  Object.assign(currentAppliedModelFilters.value, emptyModelFilters())
  page.value = 1
  loadModels()
}

const modelTabPaths = {
  mine: '/model-admin/models/mine',
  platform: '/model-admin/models/platform',
  users: '/model-admin/models/users',
}
function handleModelTabChange(tab) {
  page.value = 1
  const target = modelTabPaths[tab]
  if (target && target !== route.path) router.push(target)
}

async function openDetail(row) {
  try {
    const detail = await getAiModelDetail(row.id, { skipErrorToast: true })
    detailRow.value = { ...row, ...detail }
    detailVisible.value = true
  } catch (err) {
    ElMessage.error(err?.data?.message || err?.response?.data?.message || '读取模型详情失败')
  }
}

function onPageChange(val) {
  page.value = val
  loadModels()
}

function onPageSizeChange(size) {
  pageSize.value = size
  page.value = 1
  loadModels()
}

// 切换页签走同一组件，路由变化后按新页签重新向后端请求当前页数据。
watch(activeModelTab, () => {
  page.value = 1
  loadModels()
})

function openAdd(scope) {
  if (!canEditModels.value) return
  // 允许从“平台模型”页签直接以 scope='platform' 新建；事件对象/空值时回退我的模型
  const initialScope = scope === 'platform' ? 'platform' : 'personal'
  isEditing.value = false; editingId.value = null; editingOwnerId.value = userStore.userInfo?.id || null
  modelOptions.value = []
  modelKeywordFiltering.value = false
  capabilityResult.value = null
  capabilityDetailVisible.value = false
  connectivityVerified.value = false
  testedConnectionFingerprint.value = ''
  savedConnectionFingerprint.value = ''
  editingReasoningStatus.value = 'unknown'
  editingReasoningProfile.value = ''
  editingUsageStatus.value = 'unknown'
  editingConnectivityCheckedAt.value = null
  billingTestPassed.value = false
  billingResponsePreview.value = ''
  billingCandidates.value = []
  form.value = { name: '', provider: 'openai-compat', base_url: '', model: '', api_key: '', scope: initialScope, enabled: false, balance_query_enabled: false, balance_query_config: {}, max_output_tokens: null, daily_limit: 50 }
  formVisible.value = true
}

async function openEdit(row) {
  if (!row.can_edit) return
  // 列表接口不返回 base_url，编辑回显需向详情接口拉取（owner 返回完整地址）
  let baseUrl = row.base_url || ''
  let modelDetail = null
  try {
    modelDetail = await getAiModelDetail(row.id, { skipErrorToast: true })
    baseUrl = modelDetail?.base_url || baseUrl
  } catch (err) {
    ElMessage.error(err?.data?.message || err?.response?.data?.message || '读取模型详情失败')
    return
  }
  let balanceConfig = {}
  let balanceEnabled = !!row.balance_query_enabled
  const isBalanceOwner = Number(row.owner_user_id) === Number(userStore.userInfo?.id)
  if (isBalanceOwner && row.balance_query_configured) {
    try {
      const balanceDetail = await getAiModelBalanceQueryConfig(row.id, { skipErrorToast: true })
      balanceConfig = balanceDetail?.config || {}
      balanceEnabled = !!balanceDetail?.enabled
    } catch (err) {
      ElMessage.error(err?.data?.message || err?.response?.data?.message || '读取余额查询配置失败')
      return
    }
  }
  isEditing.value = true; editingId.value = row.id; editingOwnerId.value = row.owner_user_id || row.created_by || null
  modelOptions.value = []
  modelKeywordFiltering.value = false
  savedApiKey.value = row.api_key_masked || ''
  capabilityResult.value = null
  capabilityDetailVisible.value = false
  editingReasoningStatus.value = row.reasoning_status || 'unknown'
  editingReasoningProfile.value = row.reasoning_profile || ''
  editingUsageStatus.value = row.usage_status || 'unknown'
  editingConnectivityCheckedAt.value = row.connectivity_checked_at || null
  form.value = {
    name: row.name, provider: row.provider || 'openai-compat', base_url: baseUrl, model: row.model,
    api_key: '', scope: row.scope, enabled: row.enabled,
    balance_query_enabled: isBalanceOwner ? balanceEnabled : !!row.balance_query_enabled, balance_query_config: balanceConfig,
    // 详情接口是编辑回显的权威来源，避免列表行保留旧的最大输出值。
    max_output_tokens: Object.prototype.hasOwnProperty.call(modelDetail || {}, 'max_output_tokens')
      ? modelDetail.max_output_tokens
      : (row.max_output_tokens ?? null),
    daily_limit: Number(quotaByModelId.value.get(Number(row.id))?.daily_limit) > 0
      ? Number(quotaByModelId.value.get(Number(row.id))?.daily_limit)
      : null,
  }
  savedConnectionFingerprint.value = connectionFingerprint.value
  connectivityVerified.value = row.connectivity_status === 'passed'
  testedConnectionFingerprint.value = connectivityVerified.value ? connectionFingerprint.value : ''
  billingTestPassed.value = isBalanceOwner && !!row.balance_query_enabled
  billingResponsePreview.value = ''
  billingCandidates.value = []
  formVisible.value = true
}

function openBillingDialog() {
  if (!canConfigureBalance.value) return ElMessage.warning('仅模型创建人可以配置和测试余额接口')
  if (!hasModelCredential.value) return ElMessage.warning('请先在模型配置中填写 API Key')
  const savedConfig = form.value.balance_query_config || {}
  billingForm.value = {
    preset: savedConfig.preset || 'custom',
    url: savedConfig.url || '',
    enabled: !!form.value.balance_query_enabled,
    method: savedConfig.method || 'GET',
    type: savedConfig.type || 'balance',
    headers: (savedConfig.headers || []).map(item => ({ key: item?.key || '', value: item?.value || '' })),
    balance_path: savedConfig.balance_path || '',
  }
  billingTestPassed.value = !!form.value.balance_query_enabled
  billingResponsePreview.value = ''
  billingCandidates.value = []
  billingDialogVisible.value = true
}

function markBillingChanged() {
  billingTestPassed.value = false
  billingForm.value.enabled = false
  billingResponsePreview.value = ''
  billingCandidates.value = []
}

function markBillingFieldChanged() {
  billingTestPassed.value = false
  billingForm.value.enabled = false
}

function applyBillingPreset(preset) {
  const defaults = balancePresetDefaults[preset] || balancePresetDefaults.custom
  billingForm.value = {
    ...billingForm.value,
    preset,
    url: preset === 'custom' ? billingForm.value.url : defaults.url,
    method: defaults.method,
    balance_path: defaults.balance_path,
  }
  markBillingChanged()
}

function addBillingHeader() {
  billingForm.value.headers.push({ key: '', value: '' })
  markBillingChanged()
}

function removeBillingHeader(index) {
  billingForm.value.headers.splice(index, 1)
  markBillingChanged()
}

async function copyBalancePath(path) {
  try {
    if (await copyToClipboard(path)) ElMessage.success('已复制')
    else ElMessage.error('复制失败，请手动复制字段路径')
  } catch {
    ElMessage.error('复制失败，请手动复制字段路径')
  }
}

async function testBilling() {
  if (!canConfigureBalance.value) return ElMessage.warning('仅模型创建人可以配置和测试余额接口')
  const hasHeaderCredential = billingForm.value.headers.some(item => item?.value)
  if (!hasModelCredential.value && !hasHeaderCredential) return ElMessage.warning('请先在模型配置中填写 API Key 或配置请求头')
  if (!billingForm.value.url) return ElMessage.warning('请填写计费接口')
  billingTesting.value = true
  try {
    const payload = {
      provider: form.value.provider,
      base_url: form.value.base_url,
      model: form.value.model,
      balance_query_config: {
        preset: billingForm.value.preset || 'custom',
        url: billingForm.value.url,
        method: billingForm.value.method || 'GET',
        type: billingForm.value.type || 'balance',
        headers: billingForm.value.headers.filter(item => item?.key),
        balance_path: billingForm.value.balance_path || '',
      },
    }
    let res
    if (isEditing.value) {
      if (form.value.api_key) payload.api_key = form.value.api_key
      res = await testAiModelBilling(editingId.value, { balance_query_config: payload.balance_query_config, api_key: payload.api_key }, { skipErrorToast: true, skipSuccessToast: true })
    } else {
      payload.api_key = form.value.api_key || undefined
      res = await testAiModelBillingDraft(payload, { skipErrorToast: true, skipSuccessToast: true })
    }
    billingResponsePreview.value = res?.response_preview || ''
    billingCandidates.value = Array.isArray(res?.balance_candidates) ? res.balance_candidates : []
    billingTestPassed.value = !!res?.supported
    const balanceText = res?.balance !== undefined && res?.balance !== null ? `，当前余额：${res.balance}` : ''
    ElMessage.success(`${res?.message || '计费接口可用'}${balanceText}`)
  } catch (err) {
    billingTestPassed.value = false
    billingForm.value.enabled = false
    const result = err?.data?.data || err?.response?.data?.data || {}
    billingResponsePreview.value = result.response_preview || ''
    billingCandidates.value = Array.isArray(result.balance_candidates) ? result.balance_candidates : []
    const errorMessage = err?.data?.message || err?.response?.data?.message || '余额接口测试失败'
    if (result.response_preview) ElMessage.warning(errorMessage)
    else ElMessage.error(errorMessage)
  } finally {
    billingTesting.value = false
  }
}

function confirmBilling() {
  if (billingForm.value.enabled && !billingTestPassed.value) {
    ElMessage.warning('请先测试计费接口')
    return
  }
  form.value.balance_query_enabled = !!billingForm.value.enabled
  form.value.balance_query_config = billingForm.value.url ? {
    preset: billingForm.value.preset || 'custom',
    url: billingForm.value.url,
    method: billingForm.value.method || 'GET',
    type: billingForm.value.type || 'balance',
    headers: billingForm.value.headers.filter(item => item?.key),
    balance_path: billingForm.value.balance_path || '',
  } : {}
  billingDialogVisible.value = false
}

// 只有「用户手动键入」的内容才作为过滤关键词。
// 从下拉选中的、或打开编辑时回显的模型名不参与过滤——否则输入框里的完整模型名会把候选过滤到只剩自己，
// 用户必须先清空才能重新挑选。
function queryModelOptions(query, cb) {
  const keyword = modelKeywordFiltering.value ? String(query || '').trim().toLowerCase() : ''
  const allModels = modelOptions.value || []
  const matched = keyword
    ? allModels.filter((model) => String(model).toLowerCase().includes(keyword))
    : allModels
  cb(matched.map((model) => ({ value: model })))
}

function markModelKeywordFiltering() {
  modelKeywordFiltering.value = true
}

function selectModelOption(item) {
  form.value.model = item?.value || form.value.model
  modelKeywordFiltering.value = false
}

function handleFormEnabledChange(value) {
  form.value.enabled = !!value
}

async function saveModel() {
  if (!canEditModels.value) return
  if (!form.value.name || !form.value.base_url || !form.value.model) {
    ElMessage.warning('请填写模型别名、接口地址和模型名称')
    return
  }
  const connectivityVerified = currentConfigConnectivityVerified.value
  const personalModel = form.value.scope === 'personal'
  if (personalModel && Number(form.value.daily_limit) <= 0) {
    ElMessage.warning('日额度须填写大于 0 的数值')
    return
  }
  saveLoading.value = true
  let createdModelId = null
  try {
    const data = { ...form.value }
    delete data.daily_limit
    data.connectivity_verified = connectivityVerified
    data.enabled = !!form.value.enabled
    if (!canConfigureBalance.value) {
      delete data.balance_query_enabled
      delete data.balance_query_config
      delete data.billing_enabled
      delete data.billing_config
    }
    // If editing and api_key hasn't changed from the masked value, don't send it
    if (isEditing.value && data.api_key === savedApiKey.value) delete data.api_key
    if (!data.api_key) delete data.api_key
    // 「模型能力检测」在弹窗内探测到的思考模式 / 用量统计结果随保存一并落库：
    // 新建走草稿接口不落库；编辑若改了连接配置也走草稿接口探测新配置，同样需要随保存带上，
    // 否则后端 connection_changed 分支会把刚测到的能力重置为未检测。
    if (connectivityVerified && (editingReasoningStatus.value === 'supported' || editingReasoningStatus.value === 'unsupported')) {
      data.reasoning_status = editingReasoningStatus.value
      if (editingReasoningProfile.value) data.reasoning_profile = editingReasoningProfile.value
    }
      if (connectivityVerified && ['supported', 'unsupported', 'unknown'].includes(editingUsageStatus.value)) {
        data.usage_status = editingUsageStatus.value
      }
    if (isEditing.value) {
      await updateAiModel(editingId.value, data)
      if (personalModel) {
        await setAiModelQuota(editingId.value, Number(form.value.daily_limit))
      }
    } else {
      const created = await createAiModel(data)
      createdModelId = created.id
      if (personalModel) {
        await setAiModelQuota(created.id, Number(form.value.daily_limit))
      }
    }
    formVisible.value = false
    await loadModels()
  } catch {
    if (createdModelId) {
      try {
        await deleteAiModel(createdModelId, { skipErrorToast: true, skipSuccessToast: true })
      } catch { /* 补偿删除失败时保留后端返回的首个错误提示 */ }
    }
  }
  finally { saveLoading.value = false }
}

async function checkBalance() {
  if (!canEditModels.value) return
  balanceLoading.value = true
  try {
    const payload = {}
    if (form.value.api_key) payload.api_key = form.value.api_key
    if (form.value.base_url) payload.base_url = form.value.base_url
    payload.model_id = editingId.value
    const res = await checkAiModelBalance(editingId.value, payload, { skipSuccessToast: true, skipErrorToast: true })
    if (res?.balance !== undefined && res?.balance !== null) {
      ElMessage.success(`余额：${res.balance}`)
    } else {
      ElMessage.warning(res?.message || '查询失败')
    }
  } catch (err) {
    ElMessage.error(err?.data?.message || err?.response?.data?.message || '余额查询异常')
  } finally {
    balanceLoading.value = false
  }
}

const balanceStatusLabel = status => ({ passed: '已通过', failed: '失败', unknown: '未查询' }[status] || '未查询')
const balanceStatusTagType = status => ({ passed: 'success', failed: 'danger', unknown: 'info' }[status] || 'info')
const balanceStatusTooltip = row => {
  const time = row?.balance_query_checked_at ? formatBeijingTime(row.balance_query_checked_at) : '尚未查询'
  return `余额查询${balanceStatusLabel(row?.balance_query_status)}，${time}`
}

const avatarColors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#f5222d', '#faad14']
const avatarColor = (id) => avatarColors[(id || 0) % avatarColors.length]

function openUserDetail(row) {
  if (!row?.owner_user_id) return
  userDetailId.value = row.owner_user_id
  userDetailVisible.value = true
}
const balanceQueryHint = row => {
  if (row?.balance_query_enabled && row?.balance_query_configured && !row?.can_query_balance) return '仅模型创建人可以查询余额'
  if (!row?.balance_query_enabled) return '余额查询尚未启用'
  if (!row?.balance_query_configured) return '请先配置余额查询接口'
  return balanceStatusTooltip(row)
}

async function checkRowBalance(row) {
  if (!row?.can_query_balance) {
    if (row?.balance_query_enabled && row?.balance_query_configured) return ElMessage.warning('仅模型创建人可以查询余额')
    if (!row?.balance_query_enabled) return ElMessage.warning('余额查询尚未启用')
  }
  if (!row?.balance_query_configured) return ElMessage.warning('请先配置余额查询接口')
  balanceLoadingRowId.value = row.id
  try {
    const res = await checkAiModelBalance(row.id, {}, { skipSuccessToast: true, skipErrorToast: true })
    ElMessage.success(`余额：${res?.balance ?? '未返回'}`)
    await loadModels()
  } catch (err) {
    ElMessage.error(err?.data?.message || err?.response?.data?.message || '余额查询失败')
  } finally {
    balanceLoadingRowId.value = null
  }
}

function personalQuotaFor(row) {
  return quotaByModelId.value.get(Number(row?.id)) || null
}

function quotaTagType(remaining, limit) {
  const normalizedLimit = Number(limit)
  if (!Number.isFinite(normalizedLimit) || normalizedLimit <= 0) return 'info'
  return Number(remaining) > 0 ? 'success' : 'danger'
}

function personalQuotaValue(row) {
  if (personalQuotaQueryFailed.value) return '查询失败'
  const quota = personalQuotaFor(row)
  if (!quota || Number(quota.daily_limit || 0) <= 0) return '未配置'
  const remaining = Math.max(0, Number(quota.daily_limit) - Number(quota.today_used || 0))
  return `${remaining} / ${quota.daily_limit}`
}

function personalQuotaTagType(row) {
  if (personalQuotaQueryFailed.value) return 'warning'
  const quota = personalQuotaFor(row)
  if (!quota) return 'info'
  const remaining = Math.max(0, Number(quota.daily_limit) - Number(quota.today_used || 0))
  return quotaTagType(remaining, quota.daily_limit)
}

function platformQuotaValue(row) {
  const quota = row?.platform_quota
  if (!quota || Number(quota.daily_limit || 0) <= 0) return '未配置'
  return `${Math.max(0, Number(quota.remaining || 0))} / ${quota.daily_limit}`
}

function platformQuotaTagType(row) {
  const quota = row?.platform_quota
  if (!quota) return 'info'
  return quotaTagType(quota.remaining, quota.daily_limit)
}

function openPersonalQuotaDialog(row) {
  if (!row?.can_edit) return
  selectedPersonalQuota.value = row
  const currentLimit = Number(personalQuotaFor(row)?.daily_limit)
  personalQuotaForm.daily_limit = currentLimit > 0 ? currentLimit : null
  personalQuotaVisible.value = true
}

async function savePersonalQuota() {
  const row = selectedPersonalQuota.value
  if (!row?.can_edit) return
  if (Number(personalQuotaForm.daily_limit) <= 0) return ElMessage.warning('日额度须大于 0')
  personalQuotaSaving.value = true
  try {
    await setAiModelQuota(row.id, Number(personalQuotaForm.daily_limit))
    personalQuotaVisible.value = false
    await loadModels()
  } finally { personalQuotaSaving.value = false }
}

function openPlatformQuotaDialog() {
  const currentLimit = Number(platformQuotaSetting.value.daily_limit)
  platformQuotaForm.daily_limit = currentLimit > 0 ? currentLimit : null
  platformQuotaVisible.value = true
}

async function savePlatformQuota() {
  if (Number(platformQuotaForm.daily_limit) <= 0) return ElMessage.warning('日额度须大于 0')
  platformQuotaSaving.value = true
  try {
    await setAiPlatformQuotaSetting(Number(platformQuotaForm.daily_limit))
    platformQuotaVisible.value = false
    await loadModels()
  } finally { platformQuotaSaving.value = false }
}

// 检测失败文案：后端 message 优先；拿不到响应时（等待超时 / 连接中断）必须给出可读原因，
// 否则只显示一句「能力检测失败」，既看不出是模型问题还是等待超时，也无从排查。
function isCapabilityTimeout(err) {
  return err?.code === 'ECONNABORTED' || err?.code === 'ETIMEDOUT' || /timeout/i.test(err?.message || '')
}

function resolveCapabilityErrorMessage(err) {
  const backendMessage = err?.data?.message || err?.response?.data?.message
  if (backendMessage) return backendMessage
  if (isCapabilityTimeout(err)) return '能力检测等待超时：模型长时间未返回结果，请稍后重试或检查模型服务负载'
  if (!err?.response) return '能力检测请求中断：未收到模型服务响应，请检查网络后重试'
  return '能力检测失败'
}

async function copyProviderError() {
  const text = capabilityResult.value?.providerError || ''
  if (!text) return
  if (await copyToClipboard(text)) {
    ElMessage.success('已复制')
  } else {
    ElMessage.error('复制失败，请手动复制')
  }
}

// 三合一「模型能力检测」：一次真实调用同时判定 连通性 / 思考模式 / 用量统计。
// - 编辑且表单配置与已保存一致：走带 id 的落库接口，检测结果即时落库；
// - 新建，或编辑但配置已改动：走草稿接口按当前表单配置探测，结果暂存，保存时随模型一并落库。
async function testCapabilities() {
  if (!canEditModels.value) return
  if (capabilityTesting.value) return
  if (!form.value.base_url || !form.value.model) {
    ElMessage.warning('请先填写接口地址和模型名称')
    return
  }
  capabilityResult.value = null
  capabilityDetailVisible.value = false
  capabilityDialogVisible.value = true
  capabilityTesting.value = true
  const controller = new AbortController()
  capabilityAbortController = controller
  const requestConfig = { skipSuccessToast: true, skipErrorToast: true, signal: controller.signal }
  const connectionChanged = connectionFingerprint.value !== savedConnectionFingerprint.value
  const useSaved = !!editingId.value && !connectionChanged
  try {
    let res
    if (useSaved) {
      res = await testAiModelCapabilities(editingId.value, requestConfig)
    } else {
      const payload = {
        provider: form.value.provider,
        scope: form.value.scope || 'platform',
        model_id: editingId.value || undefined,
      }
      if (form.value.api_key) payload.api_key = form.value.api_key
      if (form.value.base_url) payload.base_url = form.value.base_url
      if (form.value.model) payload.model = form.value.model
      res = await testAiModelCapabilitiesDraft(payload, requestConfig)
    }
    if (controller.signal.aborted) return
    const reasoningStatus = res?.reasoning_status || (res?.supports_reasoning ? 'supported' : 'unsupported')
    const usageStatus = res?.usage_status || (res?.has_usage ? 'supported' : 'unsupported')
    const now = new Date().toISOString()
    connectivityVerified.value = true
    testedConnectionFingerprint.value = connectionFingerprint.value
    editingConnectivityCheckedAt.value = now
    editingReasoningStatus.value = reasoningStatus
    editingReasoningProfile.value = res?.reasoning_profile || ''
    editingUsageStatus.value = usageStatus
    if (!isEditing.value || connectionChanged) form.value.enabled = true
    capabilityResult.value = {
      ok: true,
      connectivity: 'passed',
      reasoning: reasoningStatus,
      usage: usageStatus,
    }
    // 编辑走落库接口，刷新列表；其余暂存，保存时随模型一并写入。
    if (useSaved) await loadModels()
  } catch (err) {
    if (controller.signal.aborted) return
    connectivityVerified.value = false
    testedConnectionFingerprint.value = ''
    editingReasoningStatus.value = 'unknown'
    editingReasoningProfile.value = ''
    editingUsageStatus.value = 'unknown'
    editingConnectivityCheckedAt.value = null
    capabilityResult.value = {
      ok: false,
      message: resolveCapabilityErrorMessage(err),
      providerError: err?.data?.data?.provider_error || err?.response?.data?.data?.provider_error || '',
    }
    // 只有「压根没等到后端响应」（等待超时 / 连接中断）才补报中断：后端返回过失败结论时
    // 它自己已经记过日志，这里再补一次，同一次检测就会出现「失败」+「中断」两条记录。
    const gotBackendResult = !!(err?.data || err?.response)
    if (!gotBackendResult && isCapabilityTimeout(err) && editingId.value) {
      try {
        await resetAiModelCapabilities(editingId.value, { skipSuccessToast: true, skipErrorToast: true }, 'timeout')
        await loadModels()
      } catch (reportErr) {
        console.warn('能力检测中断上报失败', reportErr)
      }
    }
  } finally {
    if (capabilityAbortController === controller) {
      capabilityAbortController = null
      capabilityTesting.value = false
    }
  }
}

async function cancelCapabilityTest() {
  if (!capabilityTesting.value) return
  const modelId = editingId.value
  capabilityAbortController?.abort()
  resetCapabilityStateForConfigChange()
  capabilityDialogVisible.value = false
  if (!modelId) return
  try {
    await resetAiModelCapabilities(modelId, { skipSuccessToast: true, skipErrorToast: true })
    await loadModels()
  } catch (err) {
    ElMessage.error(err?.data?.message || err?.response?.data?.message || '能力检测状态重置失败')
  }
}

async function fetchModels() {
  if (!canEditModels.value) return
  if (!form.value.base_url) {
    ElMessage.warning('请先填写接口地址')
    return
  }
  fetchLoading.value = true
  try {
    const payload = { base_url: form.value.base_url, model_id: editingId.value }
    if (form.value.api_key) payload.api_key = form.value.api_key
    const res = await fetchAiModels(payload, { skipErrorToast: true, skipSuccessToast: true })
    const models = res?.models || []
    if (models.length === 0) {
      ElMessage.warning('未获取到模型列表')
      return
    }
    modelOptions.value = models
    modelKeywordFiltering.value = false
    const currentModel = String(form.value.model || '').trim()
    if (currentModel && !models.includes(currentModel)) {
    ElMessage.warning(`获取到 ${models.length} 个模型，当前模型名称不在返回列表中，请确认是否需要从输入框下拉建议中选择`)
    } else {
    ElMessage.success(`获取到 ${models.length} 个模型，可在模型名称输入框中选择`)
    }
    // 获取成功后直接聚焦输入框展开候选，省掉一次手动点击
    await nextTick()
    modelNameInputRef.value?.focus?.()
  } catch (err) {
    // Only show backend message (interceptor suppressed), no duplicate toast
    const msg = err?.data?.message || err?.response?.data?.message || '获取模型列表失败，请检查接口地址和 API Key'
    ElMessage.error(msg)
  } finally {
    fetchLoading.value = false
  }
}

async function doDelete(row) {
  if (!row.can_edit) return
  const message = `确定删除模型「${row.name}」？删除后将停止参与 AI 调用，历史用量统计会保留。`
  try {
    await ElMessageBox.confirm(message, '确认删除', { type: 'warning' })
    await deleteAiModel(row.id)
    await loadModels()
  } catch { /* cancelled */ }
}

async function toggleEnabled(row, val) {
  if (!row.can_edit) return
  await updateAiModel(row.id, { enabled: val })
  ElMessage.success(val ? '已启用' : '已停用')
  await loadModels()
}

onMounted(loadModels)
</script>

<style scoped>
.page-wrap { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.page-header { flex-shrink: 0; margin-bottom: 12px; }
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
.model-tabs-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.model-tabs { flex-shrink: 0; }
.model-tabs :deep(.el-tabs__header) { margin: 0 0 12px; }
.model-tabs :deep(.el-tabs__content) { display: none; }
.platform-quota-summary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px 14px;
  min-height: 38px;
  padding: 6px 12px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: linear-gradient(135deg, #eff6ff, #f8fbff);
  color: #475569;
  font-size: 13px;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(37, 99, 235, .06);
}
.platform-quota-title { color: #1d4ed8; font-weight: 700; }
.platform-quota-item { display: inline-flex; align-items: baseline; gap: 5px; }
.platform-quota-item strong { color: #1f2937; font-size: 14px; font-weight: 700; }
.platform-quota-warning { color: #b45309; font-size: 12px; }
.platform-quota-remaining strong { color: #16a34a; }
.platform-quota-remaining.is-low strong { color: #d97706; }
.platform-quota-remaining.is-empty strong { color: #dc2626; }
.list-toolbar { min-width: 0; padding: 12px 16px; }
/* 默认允许换行，工具项在窗口变窄时自动折行，避免筛选/按钮溢出被裁剪 */
.toolbar-form { display: flex; align-items: flex-start; flex-wrap: wrap; gap: 12px 12px; width: 100%; }
.toolbar-form :deep(.el-form-item) { flex: none; margin: 0; }
.toolbar-form :deep(.el-input) { width: 140px; }
.model-name-filter, .model-identifier-filter { width: 140px; }
.model-status-filter { width: 100px; }
.model-capability-filter { width: 110px; }
/* 默认与筛选项保持同一行，空间不足时由整个表单自然换行 */
.toolbar-button-item { flex: 0 0 auto; width: auto; min-width: 0; margin-left: 0; }
.toolbar-buttons { display: flex; align-items: center; flex-wrap: wrap; gap: 10px 12px; }
.filter-select { width: 120px; }
.scroll-area { flex: 1; overflow: auto; min-height: 0; }
.pagination-area { flex-shrink: 0; display: flex; justify-content: flex-end; padding: 12px 0 0; }

@media (max-width: 1200px) {
  .model-tabs-row { align-items: flex-start; flex-direction: column; gap: 0; }
  .platform-quota-summary { justify-content: flex-start; margin-bottom: 8px; }
  .toolbar-form { flex-wrap: wrap; align-items: flex-start; }
  .toolbar-button-item { flex: 0 0 auto; width: auto; }
  .toolbar-buttons { flex-wrap: wrap; }
}
.full-table { width: 100%; min-width: 0; }
.model-table { min-width: 1175px; }
.rules-section h4 { margin: 0 0 6px; font-size: 14px; color: #303133; }
.rules-section p { margin: 0 0 16px; line-height: 1.75; color: #606266; font-size: 13px; }
.quota-cell-button { height: auto; padding: 0; }
.config-summary-row { display: flex; align-items: center; gap: 10px; width: 100%; min-width: 0; }
.capability-status { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; width: 100%; }
.capability-status .form-tip { flex-basis: 100%; }
.capability-actions { display: flex; gap: 8px; width: 100%; }
.summary-text { flex: 1; min-width: 0; color: #909399; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.field-action-row { display: flex; gap: 10px; width: 100%; align-items: center; }
.field-main { flex: 1; min-width: 0; }
.model-name-input { width: 100%; }
.model-name-input :deep(.el-input__wrapper) { width: 100%; }
/* 候选项：长模型名省略号收敛，当前选中项标注「当前」便于在长列表里定位 */
.model-option { display: flex; align-items: center; justify-content: space-between; gap: 8px; max-width: 420px; }
.model-option-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.model-option.is-current .model-option-name { color: #409eff; font-weight: 600; }
.model-option-current { flex-shrink: 0; font-size: 12px; color: #409eff; }
.api-key-field { display: flex; flex-direction: column; gap: 6px; width: 100%; }
.masked-hint { font-size: 12px; color: #16a34a; line-height: 1.5; }
.form-tip { font-size: 12px; color: #909399; line-height: 1.5; }
.balance-cell { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
.billing-enable-row { display: flex; align-items: center; gap: 14px; min-height: 32px; }
.billing-credential-summary { color: #606266; font-size: 13px; line-height: 1.6; }
.billing-header-list { display: flex; width: 100%; flex-direction: column; gap: 8px; }
.billing-header-row { display: grid; grid-template-columns: minmax(120px, 1fr) minmax(160px, 1.5fr) auto; align-items: center; gap: 8px; }
.billing-response-panel { width: 100%; overflow: hidden; border: 1px solid #dbe7f5; border-radius: 7px; }
.billing-response-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 11px; background: #f4f8fd; color: #334155; font-size: 12px; font-weight: 600; }
.billing-response-json { max-height: 260px; margin: 0; padding: 12px; overflow-y: auto; background: #111827; color: #d1fae5; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.billing-candidate-block { padding: 10px 11px; background: #fff; border-top: 1px solid #e7eef7; }
.billing-candidate-title { margin-bottom: 7px; color: #475569; font-size: 12px; }
.billing-candidate-list { display: flex; flex-direction: column; gap: 6px; }
.billing-candidate-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-width: 0; }
.billing-candidate-path { min-width: 0; overflow: hidden; color: #1677c8; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.billing-candidate-value { margin-left: 10px; color: #16a34a; font-family: inherit; }
.billing-note {
  margin: 12px 0 0 0;
  padding: 10px 12px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafafa;
  color: #606266;
  font-size: 12px;
  line-height: 1.7;
}
.billing-note-title { margin-bottom: 2px; color: #303133; font-weight: 600; }
.model-form :deep(.el-form-item) { margin-bottom: 20px; }
.model-form :deep(.el-checkbox-group) { display: flex; flex-wrap: wrap; gap: 8px 18px; }
.model-dialog :deep(.el-dialog__body) { max-height: calc(90vh - 132px); padding: 18px 24px 10px; overflow-y: auto; }
/* 左侧集中展示模型连接属性，右侧展示额度和状态等配置。 */
.model-form-layout { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 32px; align-items: start; }
.model-form-column { min-width: 0; }
.model-form-column :deep(.el-form-item) { margin-bottom: 18px; min-width: 0; }
.model-form-column :deep(.el-form-item__content) { min-width: 0; }
.model-form-column :deep(.el-form-item__label) { flex-shrink: 0; }
.switch-pair-row :deep(.el-form-item__content) { gap: 20px; }
.capability-actions { align-items: center; }
@media (max-width: 900px) {
  .model-form-layout { grid-template-columns: 1fr; }
}
.hint-text { display: block; margin-top: 4px; font-size: 12px; color: #909399; line-height: 1.5; }
.max-tokens-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.max-tokens-input { width: 160px; }
.max-tokens-input :deep(.el-input__inner) { text-align: left; }
.max-tokens-unit { font-size: 13px; color: #606266; }
.max-tokens-ref { margin-left: auto; }
.token-ref-note { margin-bottom: 12px; font-size: 13px; color: #606266; line-height: 1.6; }
.token-ref-table { margin-bottom: 12px; }
.token-ref-tip { font-size: 12px; color: #909399; line-height: 1.5; }
.token-ref-table :deep(.el-table__cell .cell) { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.token-ref-table :deep(.el-table__cell:last-child .cell) { overflow: visible; }

:deep(.no-wrap-header .cell) { white-space: nowrap; }
.model-table :deep(.cell) { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.model-table :deep(.el-table__cell:last-child .cell) { overflow: visible; }

.connectivity-loading {
  min-height: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #606266;
  text-align: center;
}
.connectivity-loading-title { font-size: 16px; font-weight: 600; color: #303133; }
.connectivity-loading-tip { max-width: 360px; font-size: 13px; line-height: 1.6; color: #909399; }
.connectivity-result { padding: 8px 0; }
.result-status { margin-bottom: 16px; }
.result-detail { display: flex; flex-direction: column; gap: 10px; }
.result-item { display: flex; align-items: flex-start; gap: 12px; }
.result-label { flex: 0 0 72px; color: #909399; font-size: 13px; line-height: 22px; }
.result-value { color: #303133; font-size: 14px; line-height: 22px; word-break: break-all; }
.result-error { padding: 12px; background: #fef0f0; border-radius: 6px; color: #f56c6c; font-size: 13px; line-height: 1.6; }
.provider-error-entry { align-self: flex-start; height: auto; padding: 0; }
.provider-error-view { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.provider-error-title { font-size: 13px; color: #606266; }
.provider-error-text { margin: 0; padding: 12px; max-height: 46vh; overflow: auto; background: #f5f7fa; border-radius: 6px; color: #303133; font-size: 12px; line-height: 1.7; white-space: pre-wrap; word-break: break-all; }
</style>
