<template>
  <div class="env-page">
    <div class="page-header">
      <div class="page-title">
        <h2>环境管理</h2>
        <span class="page-desc">管理运行环境、全局请求头、代理设置和令牌配置</span>
      </div>
      <el-button type="primary" @click="handleCreate" :icon="Plus">新建环境</el-button>
    </div>

    <div class="env-grid" v-if="environmentList.length > 0">
      <div v-for="env in environmentList" :key="env.id" class="env-card" @click="handleEdit(env)">
        <div class="env-card-top">
          <div class="env-avatar" :style="getResourceAvatarStyle(env.id)">{{ env.name?.charAt(0) || '-' }}</div>
          <div class="env-card-title">
            <span class="env-name-text">{{ env.name }}</span>
            <span class="meta-time title-time">{{ formatDate(env.created_at) }}</span>
          </div>
        </div>
        <div class="env-card-body">
          <div class="env-info-row">
            <span class="info-label">URL</span>
            <code class="info-code">{{ env.base_url ? env.base_url + (env.port ? ':' + env.port : '') : '-' }}</code>
          </div>
          <div class="env-info-row">
            <span class="info-label">请求头</span>
            <code class="info-code" v-if="hasVars(env.global_headers)">
              {{ Object.entries(env.global_headers).map(([k, v]) => `${k}: ${v}`).join('; ') }}
            </code>
            <span v-else class="info-value">-</span>
          </div>
        </div>
        <div class="env-card-footer">
          <div class="env-creator">
            <UserAvatar
              :size="24"
              :src="env.creator?.avatar"
              :name="env.creator?.real_name"
              :user-id="env.creator?.id"
            />
            <span>{{ env.creator?.real_name || '未知用户' }}</span>
          </div>
          <div class="env-actions">
            <el-button size="small" @click.stop="handleEdit(env)">编辑</el-button>
            <el-button size="small" type="success" @click.stop="handleCopy(env)">复制</el-button>
            <el-button size="small" type="danger" @click.stop="handleDelete(env)">删除</el-button>
          </div>
        </div>
      </div>
    </div>

    <GlobalEmpty v-else-if="!loading" text="暂无数据" action-text="新建环境" @action="handleCreate" />

    <div class="loading-state" v-if="loading">
      <el-skeleton :rows="3" animated />
    </div>

    <el-pagination
      v-if="total > pageSize"
      v-model:current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="total, prev, pager, next"
      @current-change="onPageChange"
      style="margin-top:20px;justify-content:flex-end;display:flex"
    />

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="min(640px, calc(100vw - 48px))" destroy-on-close :close-on-click-modal="false">
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="110px">
        <el-form-item label="环境名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入环境名称" size="large" maxlength="30" show-word-limit />
        </el-form-item>

        <el-form-item label="基础 URL" prop="base_url">
          <el-input v-model="formData.base_url" placeholder="http://api.example.com" size="large" maxlength="200" show-word-limit>
            <template #append>
              <span v-if="formData.port" style="color:#8c8c8c;font-size:13px">:{{ formData.port }}</span>
            </template>
          </el-input>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="端口">
              <el-input-number v-model="formData.port" :min="1" :max="65535" controls-position="right" style="width:100%" size="large" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="超时时间">
              <el-input-number v-model="formData.timeout" :min="1" :max="300" controls-position="right" style="width:100%" size="large" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="代理设置" class="env-summary-form-item">
          <div class="proxy-summary">
            <span>{{ proxySummary(formData.proxy_config) }}</span>
            <el-button size="small" @click="openProxyDialog('environment')">编辑代理</el-button>
          </div>
          <div class="form-tip">用于接口调试、用例运行和执行集请求。</div>
        </el-form-item>

        <el-form-item label="认证配置" class="env-summary-form-item">
          <div class="proxy-summary">
            <span>{{ authSummary(formData._authConfig) }}</span>
            <el-button size="small" @click="openAuthDialog">编辑认证</el-button>
          </div>
          <div class="form-tip">用于配置默认认证；服务可以覆盖默认认证。接口或用例手写认证请求头时优先使用手写值。</div>
        </el-form-item>

        <el-form-item label="服务配置" class="env-summary-form-item">
          <div class="proxy-summary">
            <span>{{ serviceSummary(formData.service_config) }}</span>
            <el-button size="small" @click="openServiceDialog">编辑服务</el-button>
          </div>
          <div class="form-tip">用于同一环境下区分多个服务路径，接口执行时会自动拼接完整地址。</div>
        </el-form-item>

        <el-form-item label="请求头">
          <div style="display:flex;gap:4px;margin-bottom:6px;align-items:center">
            <el-button-group size="small">
              <el-button @click="formatJson('global_headers_text')">格式化</el-button>
              <el-button @click="validateJson('global_headers_text')">校验</el-button>
            </el-button-group>
            <span v-if="jsonErrors.global_headers_text" style="color:#f56c6c;font-size:12px">{{ jsonErrors.global_headers_text }}</span>
            <span v-else-if="jsonValid.global_headers_text" style="color:#67c23a;font-size:12px">JSON 格式正确</span>
          </div>
          <el-input
            v-model="formData.global_headers_text"
            type="textarea"
            :rows="4"
            placeholder='{"Content-Type": "application/json"}'
            :class="{ 'code-input': true, 'json-error': jsonErrors.global_headers_text }"
            @input="clearJsonValid('global_headers_text')"
          />
          <div class="form-tip">这些 JSON 请求头会随环境一起保存。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">{{ formData.id ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="tokenDialogVisible"
      title="认证配置"
      width="min(1180px, calc(100vw - 64px))"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-alert
        class="auth-help-alert"
        type="info"
        :closable="false"
        show-icon
        title="默认认证用于未绑定服务的接口；服务绑定认证会覆盖默认认证；接口或用例手写认证请求头时优先使用手写值。动态认证 Token：单用例和执行集执行时优先复用环境缓存；缓存未命中时按认证配置获取，接口返回 401 时自动刷新。手写认证头或手动 Token 不会自动获取。"
      />
      <div class="auth-editor-layout">
        <div class="auth-editor-side">
          <div class="auth-toolbar">
            <el-select v-model="authDraft.default_auth_key" placeholder="不使用默认认证" clearable style="flex:1">
              <el-option v-for="item in authDraft.items" :key="item.key" :label="item.name || item.key" :value="item.key" />
            </el-select>
            <el-button type="primary" size="small" @click="addAuthItem">新增</el-button>
          </div>
          <el-table
            :data="authDraft.items"
            border
            height="260"
            style="width:100%"
            class="auth-list-table"
            :row-class-name="authRowClassName"
            @row-click="handleAuthRowClick"
          >
            <el-table-column label="认证名称" min-width="130">
              <template #default="{ row, $index }">
                <el-button link type="primary" @click.stop="selectAuthItem($index)">{{ row.name || row.key || '未命名认证' }}</el-button>
              </template>
            </el-table-column>
            <el-table-column label="模式" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.enabled ? 'success' : 'info'" effect="plain">{{ row.enabled ? '接口' : '手写' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="默认" width="70">
              <template #default="{ row }">
                <el-tag v-if="row.key === authDraft.default_auth_key" size="small" type="primary" effect="plain">默认</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="124" fixed="right" align="center" class-name="auth-actions-cell" label-class-name="auth-actions-header">
              <template #default="{ row, $index }">
                <el-button link type="primary" @click.stop="copyAuthItem(row)">复制</el-button>
                <el-button link type="danger" @click.stop="removeAuthItem($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div class="auth-editor-main">
          <GlobalEmpty v-if="selectedAuthIndex < 0" text="请选择或新增一套认证" />
          <el-form v-else :model="tokenForm" label-width="120px">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="认证标识">
                  <el-input v-model="tokenForm.key" placeholder="doctor_auth" :disabled="tokenForm._persisted" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="认证名称">
                  <el-input v-model="tokenForm.name" placeholder="家医端认证" />
                </el-form-item>
              </el-col>
            </el-row>
        <el-form-item label="自动获取">
          <el-switch v-model="tokenForm.enabled" />
          <span style="margin-left:8px;font-size:12px;color:#909399">{{ tokenForm.enabled ? '从接口响应中提取令牌' : '手动输入令牌' }}</span>
        </el-form-item>

        <el-form-item label="令牌前缀">
          <el-input v-model="tokenForm.token_prefix" placeholder="Bearer " style="width:200px" />
          <div style="font-size:12px;color:#909399;margin-top:4px">应用到请求头时会自动拼接此前缀。</div>
        </el-form-item>

        <template v-if="tokenForm.enabled">
          <el-form-item label="请求 URL">
            <el-input v-model="tokenForm.url" placeholder="http://api.example.com/auth/login" />
          </el-form-item>
          <el-form-item label="代理设置">
            <div class="proxy-summary">
              <span>{{ proxySummary(tokenForm.proxy_config) }}</span>
              <el-button size="small" @click="openProxyDialog('token')">编辑代理</el-button>
            </div>
            <div class="form-tip">仅用于获取令牌，不影响业务接口请求。</div>
          </el-form-item>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="请求方法">
                <el-select v-model="tokenForm.method" style="width:100%">
                  <el-option label="POST" value="POST" />
                  <el-option label="GET" value="GET" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="提取路径">
                <el-input v-model="tokenForm.jsonpath" placeholder="$.data.token" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item v-if="tokenForm.method === 'POST'" label="请求体">
            <div style="display:flex;gap:4px;margin-bottom:6px;align-items:center">
              <el-button-group size="small">
                <el-button @click="formatTokenBody">格式化</el-button>
                <el-button @click="validateTokenBody">校验</el-button>
              </el-button-group>
              <span v-if="tokenBodyError" style="color:#f56c6c;font-size:12px">{{ tokenBodyError }}</span>
              <span v-else-if="tokenBodyValid" style="color:#67c23a;font-size:12px">JSON 格式正确</span>
            </div>
            <el-input v-model="tokenForm.body_text" type="textarea" :rows="3" placeholder='{"username":"admin","password":"123456"}' :class="{ 'code-input': true, 'json-error': tokenBodyError }" @input="clearTokenBodyValid" />
          </el-form-item>
          <el-form-item label="请求头">
            <div v-for="(h, i) in tokenForm.headers" :key="i" class="kv-row" style="margin-bottom:4px">
              <el-input v-model="h.key" placeholder="键名" size="small" style="flex:1" />
              <el-input v-model="h.value" placeholder="键值" size="small" style="flex:2" />
              <el-button link type="danger" size="small" @click="tokenForm.headers.splice(i,1)"><el-icon><Delete /></el-icon></el-button>
            </div>
            <el-button size="small" @click="tokenForm.headers.push({ key: '', value: '' })">+ 添加请求头</el-button>
          </el-form-item>
          <el-form-item>
            <el-button size="default" @click="debugToken">调试</el-button>
            <el-button size="default" type="primary" @click="extractToken" :loading="tokenExtracting" style="margin-left:8px">获取令牌</el-button>
          </el-form-item>
          <el-form-item v-if="tokenExtracted" label="提取结果">
            <div style="width:100%">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                <el-tag :type="tokenResult ? 'success' : 'warning'" effect="dark">{{ tokenResult ? '已获取' : '未找到令牌' }}</el-tag>
                <el-button v-if="tokenResult" size="small" @click="copyTokenValue">复制</el-button>
              </div>
              <el-input :model-value="tokenResult || '（空）'" type="textarea" :rows="3" readonly class="token-result-box" />
            </div>
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="请求头名称">
            <el-select v-model="tokenForm.header_key" filterable allow-create placeholder="请选择或输入请求头名称" style="width:320px">
              <el-option v-for="h in tokenHeaderPresets" :key="h" :label="h" :value="h" />
            </el-select>
            <div style="font-size:12px;color:#909399;margin-top:4px">令牌会写入这个请求头。</div>
          </el-form-item>
          <el-form-item label="令牌">
            <el-input v-model="tokenForm.manual_token" type="textarea" :rows="4" placeholder="请输入令牌" />
          </el-form-item>
        </template>
          </el-form>
        </div>
      </div>

      <template #footer>
        <el-button @click="tokenDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="applyAuthDialog">保存认证配置</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="proxyDialogVisible" :title="proxyDialogTitle" width="min(780px, calc(100vw - 48px))" destroy-on-close :close-on-click-modal="false">
      <div class="proxy-editor">
        <div class="proxy-editor-head">
          <el-switch v-model="proxyDraft.enabled" active-text="启用代理" inactive-text="停用代理" />
          <el-button size="small" type="primary" @click="addProxyItem">新增代理</el-button>
        </div>
        <el-table :data="visibleProxyItems" border style="width:100%">
          <el-table-column label="名称" min-width="140">
            <template #default="{ row }">
              <el-input v-model="row.name" placeholder="代理名称" />
            </template>
          </el-table-column>
          <el-table-column label="类型" width="120">
            <template #default="{ row }">
              <el-select v-model="row.scheme" style="width:100%">
                <el-option label="HTTP" value="http" />
                <el-option label="HTTPS" value="https" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="代理地址" min-width="240">
            <template #default="{ row }">
              <el-input v-model="row.url" placeholder="http://127.0.0.1:7890" />
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="copyProxyItem(row)">复制</el-button>
              <el-button link type="danger" @click="removeProxyItem(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="form-tip">同类型配置多个代理时，会按列表顺序使用第一个启用且地址有效的代理。</div>
      </div>
      <template #footer>
        <el-button @click="proxyDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="applyProxyDialog">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="serviceDialogVisible"
      title="服务配置"
      width="min(1320px, calc(100vw - 64px))"
      class="service-config-dialog"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <div class="proxy-editor">
        <div class="service-dialog-header">
          <div class="service-dialog-titlebar">
            <div class="service-master-switch">
              <span class="switch-label">服务配置状态</span>
              <el-tag :type="serviceDraftEnabled ? 'success' : 'info'" effect="plain">
                {{ serviceDraftEnabled ? '已启用' : '已停用' }}
              </el-tag>
            </div>
            <el-button size="small" @click="serviceHelpVisible = true">使用说明</el-button>
            <el-button size="small" type="primary" @click="addServiceItem">新增服务</el-button>
          </div>
          <div class="service-batch-bar">
            <span class="service-selection-count">已选择 {{ selectedServiceRows.length }} 项</span>
            <el-button size="small" :disabled="!selectedServiceRows.length" @click="batchEnableServices">
              批量开启{{ selectedServiceRows.length ? ` ${selectedServiceRows.length}` : '' }}
            </el-button>
            <el-button size="small" :disabled="!selectedServiceRows.length" @click="openBatchServiceAuthDialog">
              批量认证设置{{ selectedServiceRows.length ? ` ${selectedServiceRows.length}` : '' }}
            </el-button>
            <el-button size="small" type="danger" plain :disabled="!selectedServiceRows.length" @click="batchDeleteServices">
              批量删除{{ selectedServiceRows.length ? ` ${selectedServiceRows.length}` : '' }}
            </el-button>
          </div>
        </div>
        <el-table
          class="service-config-table"
          :data="serviceDraft.items"
          border
          style="width:100%"
          @selection-change="handleServiceSelectionChange"
        >
          <el-table-column type="selection" width="44" />
          <el-table-column label="服务标识" min-width="160">
            <template #default="{ row }">
              <el-input v-model="row.key" placeholder="order-service" :disabled="row._persisted" />
            </template>
          </el-table-column>
          <el-table-column label="服务名称" min-width="160">
            <template #default="{ row }">
              <el-input v-model="row.name" placeholder="订单服务" />
            </template>
          </el-table-column>
          <el-table-column label="路径前缀" min-width="240">
            <template #default="{ row }">
              <el-input v-model="row.path_prefix" placeholder="/api/v1/orders" />
            </template>
          </el-table-column>
          <el-table-column label="认证配置" width="190">
            <template #default="{ row }">
              <el-select v-model="row.auth_key" placeholder="走默认认证" clearable style="width:100%">
                <el-option label="走默认认证" value="" />
                <el-option v-for="auth in authOptions" :key="auth.key" :label="auth.name || auth.key" :value="auth.key" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="启用服务" width="104" align="center" class-name="nowrap-table-cell" label-class-name="nowrap-table-header">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="112" fixed="right" align="center">
            <template #default="{ row, $index }">
              <el-button link type="primary" @click="copyServiceItem(row)">复制</el-button>
              <el-button link type="danger" @click="removeServiceItem($index)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="form-tip">服务标识由接口和用例保存，路径前缀与认证仅对当前环境生效；当前环境没有该服务或服务未启用时，将按基础地址和接口路径请求。</div>
      </div>
      <template #footer>
        <el-button @click="serviceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="applyServiceDialog">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="batchServiceAuthDialogVisible"
      title="批量设置认证"
      width="min(520px, calc(100vw - 48px))"
      append-to-body
      :close-on-click-modal="false"
    >
      <div class="batch-auth-dialog">
        <div class="form-tip">将为已选择的 {{ selectedServiceRows.length }} 个服务统一设置认证配置。</div>
        <el-radio-group v-model="batchServiceAuthKey" class="batch-auth-options">
          <el-radio label="__none__">不绑定，走环境默认认证</el-radio>
          <el-radio v-for="auth in authOptions" :key="auth.key" :label="auth.key">
            {{ auth.name || auth.key }}
          </el-radio>
        </el-radio-group>
        <GlobalEmpty v-if="!authOptions.length" text="暂无可选认证，可先选择走环境默认认证" />
      </div>
      <template #footer>
        <el-button @click="batchServiceAuthDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedServiceRows.length" @click="applyBatchServiceAuth">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="serviceHelpVisible" title="服务配置使用说明" width="min(700px, calc(100vw - 48px))">
      <div class="service-help">
        <p><strong>服务配置用于为当前环境设置服务的路径前缀和认证方式。</strong>接口和用例只保存服务标识，不绑定具体环境。</p>
        <p>请求地址 = 当前环境基础 URL + 服务路径前缀 + 接口路径。</p>
        <p>不同环境请保持服务标识一致，只调整各自的路径前缀和认证配置。当前环境没有该服务或服务未启用时，不拦截请求，直接按“基础 URL + 接口路径”执行。</p>
        <p>服务未绑定认证时使用环境默认认证。服务配置只影响当前环境，不会修改接口和用例中的服务标识。</p>
      </div>
    </el-dialog>

    <DebugPanel
      v-model="tokenDebugDialogVisible"
      title="令牌调试"
      :method="tokenDebugMethod"
      :request-url="tokenDebugUrl"
      :full-url="tokenDebugFullUrl"
      :req-headers="tokenDebugReqHeaders"
      :req-body="tokenDebugReqBody"
      :loading="tokenDebugLoading"
      :response="tokenDebugResponse"
      :resp-headers="tokenDebugRespHeaders"
      :error="tokenDebugError"
      :status-code="tokenDebugStatusCode"
      :duration="tokenDebugDuration"
      @send="debugToken"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, inject } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, FolderOpened, Delete } from '@element-plus/icons-vue'
import DebugPanel from '@/components/DebugPanel.vue'
import GlobalEmpty from '@/components/GlobalEmpty.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import { getEnvironments, createEnvironment, updateEnvironment, deleteEnvironment, copyEnvironment, fetchToken as fetchTokenApi, fetchTokenPreview } from '@/api/environment'
import { confirmDelete } from '@/utils/confirmDelete'
import { copyToClipboard } from '@/utils/clipboard'
import { formatBeijingDate } from '@/utils/beijingTime'
import { clearTokenCache } from '@/composables/useInterfaceDebug'

const route = useRoute()
const projectId = computed(() => route.params.id)
const refreshEnvironments = inject('refreshEnvironments', null)
const loading = ref(false)
const submitLoading = ref(false)
const environmentList = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('环境')
const formRef = ref(null)

const page = ref(1)
const pageSize = ref(10)
const total = ref(0)

const resourceAvatarTextColors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#f5222d', '#faad14']
const resourceAvatarBgColors = ['#e6f4ff', '#f0f5ff', '#e6fffb', '#fff7e6', '#f9f0ff', '#fff0f6', '#e6fffb', '#f6ffed']
const getResourceAvatarStyle = (id) => ({
  background: resourceAvatarBgColors[(id || 0) % resourceAvatarBgColors.length],
  color: resourceAvatarTextColors[(id || 0) % resourceAvatarTextColors.length],
})

const formatDate = (value) => value ? formatBeijingDate(value) || '-' : '-'

const formData = reactive({
  id: null, name: '', base_url: '', port: null, timeout: null,
  global_headers_text: '{}',
  proxy_config: { enabled: false, items: [] },
  service_config: { enabled: false, items: [] },
  proxy_http: '', proxy_https: '',
  _authConfig: { default_auth_key: '', items: [] }
})

const jsonErrors = reactive({ global_headers_text: '' })
const jsonValid = reactive({ global_headers_text: false })

const rules = {
  name: [{ required: true, message: '请输入环境名称', trigger: 'blur' }],
  base_url: [{ required: true, message: '请输入基础 URL', trigger: 'blur' }]
}

const hasVars = (obj) => obj && typeof obj === 'object' && Object.keys(obj).length > 0

const emptyProxyConfig = () => ({ enabled: false, items: [] })
const emptyServiceConfig = () => ({ enabled: false, items: [] })
const emptyAuthConfig = () => ({ default_auth_key: '', items: [] })

const isNewAuthConfig = (config) => config && typeof config === 'object' && ('items' in config || 'default_auth_key' in config)
const normalizeAuthItem = (item = {}, fallbackKey = 'default', fallbackName = '默认认证') => ({
  key: String(item.key || fallbackKey).trim(),
  name: String(item.name || fallbackName).trim(),
  enabled: item.enabled !== false,
  method: String(item.method || 'POST').toUpperCase(),
  url: String(item.url || '').trim(),
  jsonpath: String(item.jsonpath || '$.data.token').trim(),
  body: item.body ?? '{}',
  headers: item.headers && typeof item.headers === 'object' ? item.headers : {},
  proxy_config: normalizeProxyConfig(item.proxy_config),
  token_prefix: item.token_prefix !== undefined ? item.token_prefix : 'Bearer ',
  header_key: item.header_key || 'Authorization',
  manual_token: item.manual_token || '',
})

const normalizeAuthConfig = (config) => {
  if (!config || typeof config !== 'object') return emptyAuthConfig()
  if (!isNewAuthConfig(config)) {
    const legacy = normalizeAuthItem(config, 'default', '默认认证')
    return { default_auth_key: legacy.key, items: [legacy] }
  }
  const seen = new Set()
  const items = []
  ;(config.items || []).forEach((raw, index) => {
    const item = normalizeAuthItem(raw, `auth_${index + 1}`, raw?.name || `认证 ${index + 1}`)
    if (!item.key || seen.has(item.key)) return
    seen.add(item.key)
    items.push(item)
  })
  const defaultKey = items.some(item => item.key === config.default_auth_key) ? config.default_auth_key : ''
  return { default_auth_key: defaultKey, items }
}

const cloneAuthConfig = (config) => {
  const normalized = normalizeAuthConfig(config)
  return {
    default_auth_key: normalized.default_auth_key,
    items: normalized.items.map(item => ({
      ...item,
      headers: { ...(item.headers || {}) },
      proxy_config: normalizeProxyConfig(item.proxy_config),
      _persisted: !!item.key,
    })),
  }
}

const authSummary = (config) => {
  const normalized = normalizeAuthConfig(config)
  if (!normalized.items.length) return '暂未配置认证'
  const defaultAuth = normalized.items.find(item => item.key === normalized.default_auth_key)
  return `已配置 ${normalized.items.length} 套认证${defaultAuth ? `，默认：${defaultAuth.name}` : '，未选择默认认证'}`
}

const authOptions = computed(() => normalizeAuthConfig(formData._authConfig).items)
const authNameByKey = (key) => authOptions.value.find(item => item.key === key)?.name || ''

const cleanServicePath = (value) => {
  const path = String(value || '').trim()
  if (!path) return ''
  return '/' + path.replace(/^\/+/, '').replace(/\/+$/, '')
}

const normalizeServiceConfig = (config) => {
  const seen = new Set()
  const items = []
  ;(config?.items || []).forEach((item, index) => {
    const key = String(item?.key || '').trim()
    const pathPrefix = cleanServicePath(item?.path_prefix)
    if (!key || !pathPrefix || seen.has(key)) return
    seen.add(key)
    items.push({
      key,
      name: String(item?.name || key).trim(),
      path_prefix: pathPrefix,
      enabled: item?.enabled === true,
      description: item?.description || '',
      auth_key: String(item?.auth_key || '').trim(),
      priority: index + 1,
    })
  })
  return { enabled: items.some(item => item.enabled), items }
}

const cloneServiceConfig = (config) => ({
  enabled: !!config?.enabled,
  items: (config?.items || []).map((item, index) => ({
    key: item.key || '',
    name: item.name || item.key || '',
    path_prefix: item.path_prefix || '',
    enabled: item.enabled === true,
    description: item.description || '',
    auth_key: item.auth_key || '',
    priority: index + 1,
    _persisted: !!item.key,
  })),
})

const serviceSummary = (config) => {
  const normalized = normalizeServiceConfig(config)
  const configuredItems = normalized.items.filter(item => item.key && item.path_prefix)
  if (!configuredItems.length) return '暂未配置服务'
  const enabledItems = configuredItems.filter(item => item.enabled)
  if (!enabledItems.length) return '已配置，但未开启'
  return `已配置且已启用 ${enabledItems.length} 个服务`
}

const normalizeProxyConfig = (config, legacyHttp = '', legacyHttps = '') => {
  const items = []
  if (config?.items?.length) {
    config.items.forEach((item, index) => {
      const url = String(item?.url || '').trim()
      const isDeleted = item?.is_deleted === true
      if (!url && !isDeleted) return
      const scheme = item.scheme === 'https' ? 'https' : 'http'
      items.push({
        name: item.name || (scheme === 'http' ? 'HTTP代理' : 'HTTPS代理'),
        scheme,
        url,
        enabled: item.enabled !== false,
        priority: index + 1,
        is_deleted: isDeleted,
        deleted_at: item.deleted_at || null,
      })
    })
  }
  if (!items.length) {
    if (legacyHttp) items.push({ name: 'HTTP代理', scheme: 'http', url: legacyHttp, enabled: true, priority: 1, is_deleted: false, deleted_at: null })
    if (legacyHttps) items.push({ name: 'HTTPS代理', scheme: 'https', url: legacyHttps, enabled: true, priority: 2, is_deleted: false, deleted_at: null })
  }
  return { enabled: items.some(item => !item.is_deleted) && config?.enabled !== false, items }
}

const cloneProxyConfig = (config) => ({
  enabled: !!config?.enabled,
  items: (config?.items || []).map((item, index) => ({
    name: item.name || (item.scheme === 'https' ? 'HTTPS代理' : 'HTTP代理'),
    scheme: item.scheme === 'https' ? 'https' : 'http',
    url: item.url || '',
    enabled: item.enabled !== false,
    priority: index + 1,
    is_deleted: item.is_deleted === true,
    deleted_at: item.deleted_at || null,
  })),
})

const proxySummary = (config) => {
  const normalized = normalizeProxyConfig(config)
  const configuredItems = normalized.items.filter(item => !item.is_deleted && item.url)
  if (!configuredItems.length) return '暂未配置代理'
  const enabledItems = normalized.enabled ? configuredItems.filter(item => item.enabled) : []
  if (!normalized.enabled || !enabledItems.length) return '已配置，但未开启'
  return `已配置且已选择 ${enabledItems.length} 个代理`
}

const getLegacyProxyFields = (config) => {
  const normalized = normalizeProxyConfig(config)
  const enabledItems = normalized.enabled ? normalized.items.filter(item => !item.is_deleted && item.enabled && item.url) : []
  return {
    proxy_http: enabledItems.find(item => item.scheme === 'http')?.url || null,
    proxy_https: enabledItems.find(item => item.scheme === 'https')?.url || null,
  }
}

const proxyDialogVisible = ref(false)
const proxyDialogTarget = ref('environment')
const proxyDraft = reactive(emptyProxyConfig())
const proxyDialogTitle = computed(() => proxyDialogTarget.value === 'token' ? '令牌代理设置' : '环境代理设置')
const visibleProxyItems = computed(() => proxyDraft.items.filter(item => item.is_deleted !== true))
const serviceDialogVisible = ref(false)
const serviceHelpVisible = ref(false)
const serviceDraft = reactive(emptyServiceConfig())
const serviceDraftEnabled = computed(() => serviceDraft.items.some(item => item.enabled === true))
const selectedServiceRows = ref([])
const batchServiceAuthDialogVisible = ref(false)
const batchServiceAuthKey = ref('__none__')

const openServiceDialog = () => {
  const cloned = cloneServiceConfig(normalizeServiceConfig(formData.service_config))
  serviceDraft.enabled = cloned.enabled
  serviceDraft.items = cloned.items
  selectedServiceRows.value = []
  batchServiceAuthKey.value = '__none__'
  batchServiceAuthDialogVisible.value = false
  serviceDialogVisible.value = true
}

const addServiceItem = () => {
  serviceDraft.items.push({
    key: '',
    name: '',
    path_prefix: '',
    enabled: false,
    description: '',
    auth_key: '',
    priority: serviceDraft.items.length + 1,
    _persisted: false,
  })
}

const copyServiceItem = (item) => {
  serviceDraft.items.push({
    key: item?.key || '',
    name: item?.name || '',
    path_prefix: item?.path_prefix || '',
    enabled: item?.enabled === true,
    description: item?.description || '',
    auth_key: item?.auth_key || '',
    priority: serviceDraft.items.length + 1,
    _persisted: false,
  })
}

const handleServiceSelectionChange = (rows) => {
  selectedServiceRows.value = rows || []
}

const batchEnableServices = () => {
  selectedServiceRows.value.forEach(row => { row.enabled = true })
  ElMessage.success(`已开启 ${selectedServiceRows.value.length} 个服务`)
}

const openBatchServiceAuthDialog = () => {
  if (!selectedServiceRows.value.length) return
  const keys = new Set(selectedServiceRows.value.map(row => row.auth_key || ''))
  batchServiceAuthKey.value = keys.size === 1 ? (selectedServiceRows.value[0].auth_key || '__none__') : '__none__'
  batchServiceAuthDialogVisible.value = true
}

const applyBatchServiceAuth = () => {
  const value = batchServiceAuthKey.value === '__none__' ? '' : batchServiceAuthKey.value
  selectedServiceRows.value.forEach(row => { row.auth_key = value || '' })
  ElMessage.success(`已设置 ${selectedServiceRows.value.length} 个服务的认证配置`)
  batchServiceAuthDialogVisible.value = false
}

const batchDeleteServices = async () => {
  if (!selectedServiceRows.value.length) return
  try {
    await ElMessageBox.confirm(
      `确认删除当前环境中已选择的 ${selectedServiceRows.value.length} 个服务配置？接口和用例中的服务标识不会被删除。`,
      '确认批量删除服务配置',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  const selectedSet = new Set(selectedServiceRows.value)
  serviceDraft.items = serviceDraft.items.filter(item => !selectedSet.has(item))
  selectedServiceRows.value = []
  ElMessage.success('已删除所选服务')
}

const removeServiceItem = async (index) => {
  const item = serviceDraft.items[index]
  try {
    await ElMessageBox.confirm(
      `确认删除当前环境中的服务配置「${item?.name || item?.key || ''}」？接口和用例中的服务标识不会被删除。`,
      '确认删除服务配置',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  serviceDraft.items.splice(index, 1)
}

const applyServiceDialog = async () => {
  const keys = new Set()
  for (const item of serviceDraft.items) {
    if (!String(item.key || '').trim() && !String(item.path_prefix || '').trim()) continue
    if (!String(item.key || '').trim()) { ElMessage.warning('请填写服务标识'); return }
    if (!cleanServicePath(item.path_prefix)) { ElMessage.warning('请填写路径前缀'); return }
    if (keys.has(item.key.trim())) { ElMessage.warning(`服务标识「${item.key.trim()}」重复`); return }
    keys.add(item.key.trim())
  }
  formData.service_config = normalizeServiceConfig(serviceDraft)
  serviceDialogVisible.value = false
}

const openProxyDialog = (target) => {
  proxyDialogTarget.value = target
  const source = target === 'token' ? tokenForm.proxy_config : formData.proxy_config
  const cloned = cloneProxyConfig(normalizeProxyConfig(source))
  proxyDraft.enabled = cloned.enabled
  proxyDraft.items = cloned.items
  proxyDialogVisible.value = true
}

const addProxyItem = () => {
  proxyDraft.enabled = true
  proxyDraft.items.push({
    name: '',
    scheme: 'http',
    url: '',
    enabled: true,
    priority: proxyDraft.items.length + 1,
    is_deleted: false,
    deleted_at: null,
  })
}

const copyProxyItem = (row) => {
  proxyDraft.enabled = true
  const sourceIndex = proxyDraft.items.indexOf(row)
  const copied = {
    ...row,
    name: row.name ? `${row.name} 副本` : '',
    priority: proxyDraft.items.length + 1,
    is_deleted: false,
    deleted_at: null,
  }
  proxyDraft.items.splice(sourceIndex >= 0 ? sourceIndex + 1 : proxyDraft.items.length, 0, copied)
}

const removeProxyItem = (row) => {
  const index = proxyDraft.items.indexOf(row)
  if (index < 0) return
  const current = proxyDraft.items[index]
  if (!current.url && !current.name) {
    proxyDraft.items.splice(index, 1)
    return
  }
  current.is_deleted = true
  current.deleted_at = new Date().toISOString()
}

const applyProxyDialog = () => {
  if (proxyDraft.enabled && visibleProxyItems.value.some(item => !String(item.url || '').trim())) {
    ElMessage.warning('请填写代理地址')
    return
  }
  const config = normalizeProxyConfig(proxyDraft)
  if (proxyDialogTarget.value === 'token') {
    tokenForm.proxy_config = config
  } else {
    formData.proxy_config = config
    const legacy = getLegacyProxyFields(config)
    formData.proxy_http = legacy.proxy_http || ''
    formData.proxy_https = legacy.proxy_https || ''
  }
  proxyDialogVisible.value = false
}

const loadEnvironments = async () => {
  if (!projectId.value) { ElMessage.warning('请先选择项目'); return }
  loading.value = true
  try {
    const res = await getEnvironments(projectId.value, page.value, pageSize.value)
    environmentList.value = res.items || res || []
    total.value = res.total || (Array.isArray(res) ? res.length : 0)
  } catch { environmentList.value = [] }
  finally { loading.value = false }
}

const handleCreate = () => {
  dialogTitle.value = '新建环境'
  Object.assign(formData, { id: null, name: '', base_url: '', port: null, timeout: null, global_headers_text: '{}', proxy_config: emptyProxyConfig(), service_config: emptyServiceConfig(), proxy_http: '', proxy_https: '', _authConfig: emptyAuthConfig() })
  Object.assign(jsonErrors, { global_headers_text: '' })
  Object.assign(jsonValid, { global_headers_text: false })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑环境'
  formData.id = row.id; formData.name = row.name; formData.base_url = row.base_url
  formData.port = row.port; formData.timeout = row.timeout
  formData.proxy_config = normalizeProxyConfig(row.proxy_config, row.proxy_http || '', row.proxy_https || '')
  formData.service_config = normalizeServiceConfig(row.service_config)
  const legacy = getLegacyProxyFields(formData.proxy_config)
  formData.proxy_http = legacy.proxy_http || ''; formData.proxy_https = legacy.proxy_https || ''
  formData._authConfig = normalizeAuthConfig(row.token_config || {})
  formData.global_headers_text = typeof row.global_headers === 'string' ? row.global_headers : JSON.stringify(row.global_headers || {}, null, 2)
  Object.assign(jsonErrors, { global_headers_text: '' })
  Object.assign(jsonValid, { global_headers_text: false })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  const ok = await confirmDelete(row.name, '环境')
  if (!ok) return
  await deleteEnvironment(row.id)
  loadEnvironments()
  refreshEnvironments?.()
}

const handleCopy = async (row) => {
  try {
    await copyEnvironment(row.id)
    loadEnvironments()
    refreshEnvironments?.()
  } catch { }
}

const formatJson = (field) => {
  try {
    const obj = JSON.parse(formData[field] || '{}')
    formData[field] = JSON.stringify(obj, null, 2)
    jsonErrors[field] = ''
    jsonValid[field] = true
  } catch (e) {
    jsonErrors[field] = 'JSON 格式错误：' + e.message
    jsonValid[field] = false
  }
}

const validateJson = (field) => {
  try {
    JSON.parse(formData[field] || '{}')
    jsonErrors[field] = ''
    jsonValid[field] = true
    ElMessage.success('JSON 格式正确')
  } catch (e) {
    jsonErrors[field] = 'JSON 格式错误：' + e.message
    jsonValid[field] = false
  }
}

const clearJsonValid = (field) => {
  jsonValid[field] = false
}

const formatTokenBody = () => {
  try {
    const obj = JSON.parse(tokenForm.body_text || '{}')
    tokenForm.body_text = JSON.stringify(obj, null, 2)
    tokenBodyError.value = ''
    tokenBodyValid.value = true
  } catch (e) {
    tokenBodyError.value = 'JSON 格式错误：' + e.message
    tokenBodyValid.value = false
  }
}

const validateTokenBody = () => {
  try {
    JSON.parse(tokenForm.body_text || '{}')
    tokenBodyError.value = ''
    tokenBodyValid.value = true
    ElMessage.success('JSON 格式正确')
  } catch (e) {
    tokenBodyError.value = 'JSON 格式错误：' + e.message
    tokenBodyValid.value = false
  }
}

const clearTokenBodyValid = () => {
  tokenBodyValid.value = false
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitLoading.value = true
    try {
      let globalHeaders = {}
      try { globalHeaders = JSON.parse(formData.global_headers_text || '{}') } catch { ElMessage.error('全局请求头 JSON 格式错误'); submitLoading.value = false; return }
      const data = {
        project_id: parseInt(projectId.value), name: formData.name, base_url: formData.base_url.trim(),
        port: formData.port, timeout: formData.timeout || null, global_headers: globalHeaders,
        proxy_config: normalizeProxyConfig(formData.proxy_config),
        service_config: normalizeServiceConfig(formData.service_config),
        ...getLegacyProxyFields(formData.proxy_config),
        token_config: normalizeAuthConfig(formData._authConfig)
      }
      if (formData.id) { await updateEnvironment(formData.id, data) }
      else { await createEnvironment(data) }
      if (formData.id) clearTokenCache(formData.id)
      dialogVisible.value = false
      loadEnvironments()
      refreshEnvironments?.()
    } finally { submitLoading.value = false }
  })
}

const tokenDialogVisible = ref(false)
const tokenResult = ref('')
const tokenExtracted = ref(false)
const tokenExtracting = ref(false)
const authDraft = reactive(emptyAuthConfig())
const selectedAuthIndex = ref(-1)
const tokenHeaderPresets = [
  'Authorization', 'X-Auth-Token', 'X-API-Key', 'X-Access-Token',
  'Cookie', 'token', 'access_token', 'jwt'
]
const tokenForm = reactive({
  key: '', name: '', _persisted: false,
  url: '', method: 'POST', jsonpath: '$.data.token',
  body_text: '{}', headers: [{ key: 'Content-Type', value: 'application/json' }],
  proxy_config: emptyProxyConfig(),
  enabled: true, token_prefix: 'Bearer ', header_key: 'Authorization', manual_token: ''
})
const tokenBodyError = ref('')
const tokenBodyValid = ref(false)
const tokenDebugDialogVisible = ref(false)
const tokenDebugLoading = ref(false)
const tokenDebugMethod = ref('')
const tokenDebugUrl = ref('')
const tokenDebugFullUrl = ref('')
const tokenDebugReqHeaders = ref({})
const tokenDebugReqBody = ref('')
const tokenDebugResponse = ref(null)
const tokenDebugRespHeaders = ref(null)
const tokenDebugError = ref('')
const tokenDebugStatusCode = ref(0)
const tokenDebugDuration = ref(0)

const syncTokenFormToDraft = () => {
  if (selectedAuthIndex.value < 0 || !authDraft.items[selectedAuthIndex.value]) return
  authDraft.items[selectedAuthIndex.value] = {
    ...authDraft.items[selectedAuthIndex.value],
    key: String(tokenForm.key || '').trim(),
    name: String(tokenForm.name || tokenForm.key || '').trim(),
    enabled: tokenForm.enabled === true,
    method: tokenForm.method,
    url: tokenForm.url,
    jsonpath: tokenForm.jsonpath,
    body: tokenForm.body_text,
    headers: Object.fromEntries(tokenForm.headers.filter(h => h.key).map(h => [h.key, h.value])),
    proxy_config: normalizeProxyConfig(tokenForm.proxy_config),
    token_prefix: tokenForm.token_prefix,
    header_key: tokenForm.header_key || 'Authorization',
    manual_token: tokenForm.manual_token,
    _persisted: tokenForm._persisted,
  }
}

const loadAuthItemToForm = (item) => {
  tokenResult.value = ''
  tokenExtracted.value = false
  tokenExtracting.value = false
  tokenBodyError.value = ''
  tokenBodyValid.value = false
  tokenForm.key = item?.key || ''
  tokenForm.name = item?.name || item?.key || ''
  tokenForm._persisted = item?._persisted === true
  tokenForm.url = item?.url || formData.base_url || ''
  tokenForm.method = item?.method || 'POST'
  tokenForm.jsonpath = item?.jsonpath || '$.data.token'
  tokenForm.body_text = item?.body || '{}'
  tokenForm.headers = item?.headers && Object.keys(item.headers).length > 0
    ? Object.entries(item.headers).map(([k, v]) => ({ key: k, value: v }))
    : [{ key: 'Content-Type', value: 'application/json' }]
  tokenForm.proxy_config = normalizeProxyConfig(item?.proxy_config)
  tokenForm.enabled = item?.enabled !== undefined ? item.enabled : true
  tokenForm.token_prefix = item?.token_prefix !== undefined ? item.token_prefix : 'Bearer '
  tokenForm.header_key = item?.header_key || 'Authorization'
  tokenForm.manual_token = item?.manual_token || ''
}

const selectAuthItem = (index) => {
  syncTokenFormToDraft()
  selectedAuthIndex.value = index
  loadAuthItemToForm(authDraft.items[index])
}

const handleAuthRowClick = (_row, _column, event) => {
  if (event?.target?.closest?.('.el-button')) return
  const index = authDraft.items.indexOf(_row)
  if (index >= 0) selectAuthItem(index)
}

const authRowClassName = ({ rowIndex }) => (
  rowIndex === selectedAuthIndex.value ? 'is-selected-auth-row' : ''
)

const addAuthItem = () => {
  syncTokenFormToDraft()
  const next = authDraft.items.length + 1
  const item = normalizeAuthItem({ key: `auth_${Date.now()}`, name: `认证 ${next}` }, `auth_${next}`, `认证 ${next}`)
  authDraft.items.push({ ...item, _persisted: false })
  if (!authDraft.default_auth_key) authDraft.default_auth_key = item.key
  selectAuthItem(authDraft.items.length - 1)
}

const copyAuthItem = (item) => {
  syncTokenFormToDraft()
  const baseKey = String(item?.key || 'auth').trim() || 'auth'
  let nextKey = `${baseKey}_copy`
  let index = 2
  const usedKeys = new Set(authDraft.items.map(auth => auth.key))
  while (usedKeys.has(nextKey)) {
    nextKey = `${baseKey}_copy_${index}`
    index += 1
  }
  const copied = normalizeAuthItem({
    ...item,
    key: nextKey,
    name: `${item?.name || item?.key || '认证'} 副本`,
    headers: { ...(item?.headers || {}) },
    proxy_config: normalizeProxyConfig(item?.proxy_config),
  }, nextKey, `${item?.name || '认证'} 副本`)
  authDraft.items.push({ ...copied, _persisted: false })
  selectAuthItem(authDraft.items.length - 1)
}

const removeAuthItem = async (index) => {
  const item = authDraft.items[index]
  if (!item) return
  const authName = item.name || item.key
  const isDefaultAuth = authDraft.default_auth_key === item.key
  const message = [
    `确认删除认证「${authName}」？`,
    '删除后，原来绑定这套认证的服务会改为“不绑定认证”。',
    '这些服务下的接口和用例执行时，将回退使用“环境管理-请求头”里配置的认证信息；如果请求头里也没有认证信息，则不会自动注入认证。',
    isDefaultAuth ? '这套认证当前是默认认证，删除后将不再设置默认认证。是否确认删除？' : '是否确认删除？',
  ].filter(Boolean).join('\n')
  try {
    await ElMessageBox.confirm(message, '确认删除认证', {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch { return }
  authDraft.items.splice(index, 1)
  serviceDraft.items.forEach(service => {
    if (service.auth_key === item.key) service.auth_key = ''
  })
  if (authDraft.default_auth_key === item.key) authDraft.default_auth_key = ''
  selectedAuthIndex.value = Math.min(index, authDraft.items.length - 1)
  if (selectedAuthIndex.value >= 0) loadAuthItemToForm(authDraft.items[selectedAuthIndex.value])
}

const openAuthDialog = async () => {
  const cloned = cloneAuthConfig(formData._authConfig)
  authDraft.default_auth_key = cloned.default_auth_key
  authDraft.items = cloned.items
  selectedAuthIndex.value = authDraft.items.length ? 0 : -1
  if (selectedAuthIndex.value >= 0) loadAuthItemToForm(authDraft.items[0])
  else loadAuthItemToForm({})
  tokenDebugDialogVisible.value = false
  tokenDialogVisible.value = true
}

const openTokenDialog = openAuthDialog

const applyAuthDialog = () => {
  syncTokenFormToDraft()
  const keys = new Set()
  for (const item of authDraft.items) {
    if (!String(item.key || '').trim()) { ElMessage.warning('请填写认证标识'); return }
    if (!String(item.name || '').trim()) { ElMessage.warning('请填写认证名称'); return }
    if (keys.has(item.key)) { ElMessage.warning(`认证标识「${item.key}」重复`); return }
    keys.add(item.key)
    if (item.enabled && !String(item.url || '').trim()) { ElMessage.warning(`请填写认证「${item.name}」的请求 URL`); return }
    if (!item.enabled && !String(item.manual_token || '').trim()) { ElMessage.warning(`请填写认证「${item.name}」的手写令牌`); return }
  }
  formData._authConfig = normalizeAuthConfig(authDraft)
  formData.service_config = normalizeServiceConfig(formData.service_config)
  tokenDialogVisible.value = false
  ElMessage.success('认证配置已保存')
}

const debugToken = async () => {
  if (!tokenForm.url) { ElMessage.warning('请输入请求 URL'); return }

  tokenDebugError.value = ''; tokenDebugResponse.value = null
  tokenDebugMethod.value = tokenForm.method
  tokenDebugUrl.value = tokenForm.url
  tokenDebugFullUrl.value = tokenForm.url
  tokenDebugReqHeaders.value = Object.fromEntries(tokenForm.headers.filter(h => h.key).map(h => [h.key, h.value]))
  tokenDebugReqBody.value = tokenForm.body_text
  tokenDebugDialogVisible.value = true
  tokenDebugLoading.value = true

  try {
    const tokenRequest = {
      project_id: projectId.value,
      url: tokenForm.url,
      method: tokenForm.method,
      jsonpath: tokenForm.jsonpath,
      body: tokenForm.body_text,
      headers: Object.fromEntries(tokenForm.headers.filter(h => h.key).map(h => [h.key, h.value])),
      proxy_config: normalizeProxyConfig(tokenForm.proxy_config),
    }
    const result = formData.id
      ? await fetchTokenApi(formData.id, tokenRequest, { skipSuccessToast: true, skipErrorToast: true })
      : await fetchTokenPreview(tokenRequest, { skipSuccessToast: true, skipErrorToast: true })
    tokenDebugStatusCode.value = result?.status_code || 0
    tokenDebugDuration.value = result?.duration || 0
    tokenDebugRespHeaders.value = result?.resp_headers || {}
    tokenDebugResponse.value = result?.response || result?.response_text || null
    const remoteStatus = Number(result?.status_code || 0)
    if (remoteStatus >= 200 && remoteStatus < 300 && result?.token) {
      ElMessage.success(`调试成功（远端 ${remoteStatus}，已提取 Token）`)
    } else if (remoteStatus >= 200 && remoteStatus < 300 && result?.response == null && result?.response_text) {
      ElMessage.error('调试失败：远端响应不是 JSON，无法提取 Token')
    } else if (remoteStatus >= 200 && remoteStatus < 300) {
      ElMessage.error('调试失败：远端请求成功，但未提取到 Token，请检查 JSONPath')
    } else if (remoteStatus) {
      ElMessage.error(`调试失败：远端返回 ${remoteStatus}`)
    } else {
      ElMessage.error('调试失败：未收到远端响应')
    }
  } catch (e) {
    const message = e?.data?.message || e?.response?.data?.message || e?.response?.data?.detail || e?.message || '请求失败'
    tokenDebugError.value = message
    ElMessage.error(message)
  } finally {
    tokenDebugLoading.value = false
  }
}

const extractToken = async () => {
  if (!tokenForm.url) { ElMessage.warning('请输入请求 URL'); return }

  tokenExtracting.value = true
  tokenResult.value = ''
  tokenExtracted.value = false

  try {
    const tokenRequest = {
      project_id: projectId.value,
      url: tokenForm.url,
      method: tokenForm.method,
      jsonpath: tokenForm.jsonpath,
      body: tokenForm.body_text,
      headers: Object.fromEntries(tokenForm.headers.filter(h => h.key).map(h => [h.key, h.value])),
      proxy_config: normalizeProxyConfig(tokenForm.proxy_config),
    }
    const result = formData.id
      ? await fetchTokenApi(formData.id, tokenRequest, { skipSuccessToast: true, skipErrorToast: true })
      : await fetchTokenPreview(tokenRequest, { skipSuccessToast: true, skipErrorToast: true })
    tokenResult.value = result?.token || ''
    tokenExtracted.value = true
    if (result?.token) {
      ElMessage.success('令牌获取成功')
    } else {
      ElMessage.warning('未提取到令牌，请检查提取路径')
    }
  } catch {
    tokenExtracted.value = true
  } finally {
    tokenExtracting.value = false
  }
}

const copyTokenValue = async () => {
  if (!tokenResult.value) return
  try {
    if (await copyToClipboard(tokenResult.value)) ElMessage.success('令牌已复制')
    else ElMessage.warning('复制失败')
  } catch {
    ElMessage.warning('复制失败')
  }
}

const onPageChange = (val) => {
  page.value = val
  loadEnvironments()
}

onMounted(() => { loadEnvironments() })
</script>

<style scoped>
.env-page { max-width: 100%; height: 100%; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; flex-shrink: 0; }
.page-title h2 { margin: 0 0 6px; font-size: 20px; font-weight: 600; color: #1a1a1a; }
.page-desc { font-size: 14px; color: #8c8c8c; }

.env-grid { display: grid; grid-template-columns: repeat(auto-fill, 390px); gap: 20px; flex: 1; min-height: 0; overflow-y: auto; align-content: start; }
.env-grid {
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  scrollbar-color: #aeb8c4 #f7f9fc;
}
.env-grid::-webkit-scrollbar { width: 8px; height: 8px; }
.env-grid::-webkit-scrollbar-track { background: #f7f9fc; border-radius: 4px; }
.env-grid::-webkit-scrollbar-thumb { background: #aeb8c4; border: 2px solid #f7f9fc; border-radius: 4px; }
.env-grid::-webkit-scrollbar-thumb:hover { background: #8996a5; }
.env-card {
  background: #fff;
  border: 1px solid #e8edf3;
  border-radius: 14px;
  padding: 24px;
  overflow: hidden;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  min-height: 220px;
  transition: box-shadow .2s ease, border-color .2s ease, transform .2s ease;
}
.env-card.is-default { border-color: #b7eb8f; background: #f6ffed; }
.env-card:hover { box-shadow: 0 10px 26px rgba(15,23,42,.09); border-color: #cfd8e3; transform: translateY(-2px); }
.env-card-top { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
.env-avatar {
  width: 48px; height: 48px; border-radius: 12px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; font-weight: 700;
  transition: transform .24s cubic-bezier(0.2,0,0,1);
}
.env-card:hover .env-avatar { transform: scale(1.06); }
.env-card-title { display: flex; align-items: center; gap: 10px; font-size: 17px; font-weight: 600; color: #1a1a1a; min-width: 0; flex: 1; }
.env-name-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; }
.env-card-body { display: flex; flex-direction: column; gap: 10px; flex: 1; }
.env-card-footer {
  display: flex; align-items: center; justify-content: space-between; gap: 14px;
  margin-top: 14px; padding-top: 14px; border-top: 1px solid #f1f3f6;
}

.env-creator { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #8c8c8c; min-width: 0; flex: 1; }
.env-creator > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meta-time { color: #bfbfbf; font-size: 12px; white-space: nowrap; }
.title-time { flex-shrink: 0; font-weight: 400; }
.env-actions { display: flex; align-items: center; gap: 12px; justify-content: flex-end; flex-shrink: 0; }
.env-actions .el-button + .el-button { margin-left: 0; }
.env-actions .el-button { min-width: 54px; height: 30px; padding: 6px 11px; border-radius: 6px; }
.env-info-row { display: flex; align-items: baseline; gap: 10px; overflow: hidden; }
.info-label { font-size: 13px; color: #8c8c8c; flex-shrink: 0; min-width: 50px; }
.info-value { font-size: 14px; color: #595959; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: calc(100% - 60px); }
.info-code { background: #f5f5f5; padding: 2px 8px; border-radius: 4px; font-family: SFMono-Regular, Consolas, monospace; font-size: 13px; display: inline-block; max-width: calc(100% - 60px); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-state { flex: 1; min-height: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 72px 0; color: #8c8c8c; }
.loading-state { flex-shrink: 0; padding: 24px; overflow-y: auto; }
.form-tip { color: #909399; font-size: 12px; line-height: 1.6; margin-top: 6px; }
.code-input :deep(textarea), .token-result-box :deep(textarea) { font-family: SFMono-Regular, Consolas, monospace; }
.json-error :deep(textarea) { border-color: #f56c6c; }
.kv-row { display: flex; align-items: center; gap: 6px; width: 100%; }
.proxy-summary { width: 100%; min-height: 36px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 12px; border: 1px solid #dcdfe6; border-radius: 6px; color: #606266; background: #fff; }
.env-summary-form-item :deep(.el-form-item__label) { display: flex; align-items: center; min-height: 36px; padding-top: 0; }
.proxy-editor { display: flex; flex-direction: column; gap: 12px; }
.proxy-editor-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.auth-help-alert { margin-bottom: 12px; }
.auth-editor-layout { display: grid; grid-template-columns: 430px minmax(0, 1fr); gap: 20px; align-items: flex-start; }
.auth-editor-side, .auth-editor-main { min-width: 0; }
.auth-toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.auth-list-table :deep(.el-table__row) {
  cursor: pointer;
}
.auth-list-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #f5f9ff;
}
.auth-list-table :deep(.is-selected-auth-row > td.el-table__cell) {
  background: #edf5ff;
}
.auth-list-table :deep(.el-button) {
  position: relative;
  z-index: 1;
}
.auth-list-table :deep(.auth-actions-cell .cell) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  white-space: nowrap;
}
.auth-list-table :deep(.auth-actions-cell .el-button + .el-button) {
  margin-left: 0;
}
.auth-list-table :deep(.el-table__inner-wrapper),
.auth-list-table :deep(.el-table__body-wrapper),
.auth-list-table :deep(.el-scrollbar__wrap) {
  overflow-x: hidden;
}
.service-dialog-header {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.service-dialog-titlebar,
.service-batch-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.service-dialog-titlebar {
  justify-content: flex-start;
}
.service-dialog-titlebar .service-master-switch {
  margin-right: auto;
}
.service-batch-bar {
  padding: 10px 12px;
  border: 1px solid #edf1f7;
  border-radius: 8px;
  background: #f8fafc;
}
.service-selection-count {
  color: #606266;
  font-size: 13px;
  margin-right: 2px;
}
.service-master-switch {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: #606266;
  font-size: 13px;
}
.switch-label {
  color: #303133;
  font-weight: 600;
}
.service-help { line-height: 1.8; color: #606266; }
.service-help p { margin: 0 0 8px; }
.usage-text { color: #606266; font-size: 12px; }
.batch-auth-dialog {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.batch-auth-options {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
}
:global(.service-config-dialog .el-dialog__body) {
  overflow-x: hidden;
}
:global(.service-config-table .el-table__inner-wrapper),
:global(.service-config-table .el-table__body-wrapper),
:global(.service-config-table .el-scrollbar__wrap) {
  overflow-x: hidden;
}
:global(.service-config-table .el-input__wrapper),
:global(.service-config-table .el-select__wrapper) {
  min-width: 0;
}
:global(.service-config-table .nowrap-table-header),
:global(.service-config-table .nowrap-table-cell .cell) {
  white-space: nowrap;
}

@media (max-width: 768px) {
  .env-grid { grid-template-columns: minmax(0, 1fr); }
  .env-card { padding: 18px; }
  .page-header { gap: 12px; flex-direction: column; }
}
@media (max-width: 480px) {
  .env-card-footer { align-items: flex-start; flex-direction: column; }
  .env-actions { justify-content: center; flex-wrap: wrap; }
}
</style>
