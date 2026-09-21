<template>
  <div class="page-wrap">
    <div class="admin-page-title"><h2>问题反馈</h2></div>
    <div class="search-area">
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索标题/内容" clearable style="width:220px" @keyup.enter="searchList" />
        <el-select v-model="filterType" placeholder="反馈类型" clearable style="width:130px">
          <el-option label="Bug" value="bug" />
          <el-option label="建议" value="suggestion" />
          <el-option label="其他" value="other" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="状态" clearable style="width:130px">
          <el-option label="全部" value="all" />
          <el-option label="待处理" value="pending" />
          <el-option label="处理中" value="processing" />
          <el-option label="待确认" value="pending_confirm" />
          <el-option label="已完成" value="completed" />
        </el-select>
        <el-button type="default" @click="searchList"><el-icon><Search /></el-icon>搜索</el-button>
        <el-button type="primary" @click="showCreate = true"><el-icon><Plus /></el-icon>提交反馈</el-button>
        <el-button @click="showFlowHelp = true">流程说明</el-button>
      </div>
    </div>

    <div class="scroll-area" v-loading="loading">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane name="my">
          <template #label>
            <span class="feedback-tab-label">
              <span>我的反馈</span>
              <span v-if="myFeedbackBadgeCount > 0" class="tab-count">{{ formatBadgeCount(myFeedbackBadgeCount) }}</span>
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane v-if="isSuperAdmin" name="todo">
          <template #label>
            <span class="feedback-tab-label">
              <span>待解决</span>
              <span v-if="todoFeedbackBadgeCount > 0" class="tab-count">{{ formatBadgeCount(todoFeedbackBadgeCount) }}</span>
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane v-if="isSuperAdmin" label="全部反馈" name="all" />
      </el-tabs>

      <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" class="load-error">
        <el-button link type="danger" @click="loadList">重试</el-button>
      </el-alert>

      <!-- 表格列表 -->
      <el-table :data="feedbacks" stripe style="width:100%" @row-click="openDetail">
        <el-table-column prop="type" label="反馈类型" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag :type="typeTag(row.type)" size="small">{{ typeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click.stop="openDetail(row)">{{ row.title || '-' }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="反馈时间" show-overflow-tooltip>
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small" effect="plain">{{ statusLabel(row.status) }}</el-tag>
            <el-tag v-if="row.is_reply_unread && row.user_id === currentUserId" size="small" type="danger" effect="dark" style="margin-left:6px">新回复</el-tag>
            <el-tag v-if="row.is_reopen_unread && row.resolved_by === currentUserId" size="small" type="warning" effect="dark" style="margin-left:6px">重新打开</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="user_name" label="反馈人" show-overflow-tooltip />
        <el-table-column prop="resolver_name" label="处理人" show-overflow-tooltip>
          <template #default="{ row }">{{ row.resolver_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="resolved_at" label="处理时间" show-overflow-tooltip>
          <template #default="{ row }">{{ row.resolved_at ? formatTime(row.resolved_at) : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="openDetail(row)">查看</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无反馈记录" />
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
        @current-change="handlePageChange"
        @size-change="handlePageSizeChange"
      />
    </div>

    <!-- ====== 流程说明弹窗 ====== -->
    <el-dialog v-model="showFlowHelp" title="问题反馈流程说明" width="620px" destroy-on-close>
      <div class="flow-help">
        <div class="flow-step"><span>1</span><div><b>提交反馈</b><p>提交后进入“待处理”，有处理权限的人会收到提醒。</p></div></div>
        <div class="flow-step"><span>2</span><div><b>沟通处理</b><p>处理人可以“仅回复”，提交人也可以补充说明；所有互动都会保留在详情里。</p></div></div>
        <div class="flow-step"><span>3</span><div><b>解决确认</b><p>处理人点击“解决”后进入“待确认”，等待提交人验收。</p></div></div>
        <div class="flow-step"><span>4</span><div><b>最终收口</b><p>提交人认可后点击“确认完成”；如果仍有问题，点击“继续反馈”，问题会回到“待处理”。</p></div></div>
        <div class="flow-note">列表规则：普通用户和管理员只看自己提交的反馈；超管可查看全部反馈，“待解决”展示所有尚未完成的反馈。</div>
      </div>
    </el-dialog>

    <!-- ====== 提交反馈弹窗 ====== -->
    <el-dialog v-model="showCreate" title="提交问题反馈" width="680px" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px">
        <el-form-item label="反馈类型">
          <el-radio-group v-model="form.type">
            <el-radio value="bug">Bug</el-radio>
            <el-radio value="suggestion">建议</el-radio>
            <el-radio value="other">其他</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="简要描述问题（最多50字）" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="详细描述" required>
          <el-input v-model="form.content" type="textarea" :rows="5" placeholder="请详细描述遇到的问题或建议（最多500字）" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="所在页面">
          <el-input v-model="form.page_url" placeholder="出现问题/建议涉及的页面路径（自动获取）" />
        </el-form-item>
        <el-form-item label="截图">
          <div class="screenshot-input" :class="{ 'has-images': form.image_urls.length > 0 }" tabindex="0" @click="$event.currentTarget.focus()">
            <div class="screenshot-body">
              <template v-if="form.image_urls.length > 0">
                <div v-for="(url, i) in form.image_urls" :key="i" class="upload-preview">
                  <el-image :src="url" fit="cover" />
                  <el-icon class="remove-btn" @click.stop="removeImage(i)"><CircleClose /></el-icon>
                </div>
              </template>
              <span v-else class="placeholder-text">点击此处或 Ctrl+V 粘贴截图</span>
            </div>
            <el-upload
              v-if="form.image_urls.length < 6"
              :http-request="handleUpload"
              :show-file-list="false"
              accept="image/*"
              class="screenshot-upload"
            >
              <div class="plus-btn"><el-icon :size="22"><Plus /></el-icon></div>
            </el-upload>
          </div>
          <div class="upload-tip">最多 6 张，单张不超过 5MB</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitFeedback">提交</el-button>
      </template>
    </el-dialog>

    <!-- ====== 详情弹窗 ====== -->
    <el-dialog v-model="showDetail" title="反馈详情" width="720px" :close-on-click-modal="false" @closed="detail=null">
      <template v-if="detail">
        <div class="detail-top">
          <el-tag :type="typeTag(detail.type)" size="small">{{ typeLabel(detail.type) }}</el-tag>
          <el-tag :type="statusTag(detail.status)" size="small" effect="plain" style="margin-left:8px">{{ statusLabel(detail.status) }}</el-tag>
          <span class="detail-title">{{ detail.title }}</span>
        </div>
        <div class="detail-meta">
          <span>{{ detail.user_name }}</span>
          <span class="dot">·</span>
          <span>{{ formatTime(detail.created_at) }}</span>
        </div>
        <div class="detail-section">
          <div class="detail-label">详细描述</div>
          <div class="detail-content">{{ detail.content }}</div>
        </div>

        <div v-if="detail.image_urls && detail.image_urls.length" class="detail-section">
          <div class="detail-label">截图</div>
          <div class="detail-images">
            <el-image
              v-for="(url, i) in detail.image_urls"
              :key="i"
              :src="url"
              :preview-src-list="detail.image_urls"
              :initial-index="i"
              fit="cover"
              class="detail-thumb"
            />
          </div>
        </div>

        <div v-if="detailInteractions.length" class="detail-section">
          <div class="detail-label">互动记录</div>
          <div class="interaction-list">
            <div v-for="(item, index) in detailInteractions" :key="index" class="interaction-item">
              <div class="interaction-head">
                <span class="interaction-action">{{ interactionLabel(item.type) }}</span>
                <span class="interaction-user">{{ item.user_name || '-' }}</span>
                <span class="interaction-time">{{ formatTime(item.created_at) }}</span>
                <el-tag v-if="item.status" :type="statusTag(item.status)" size="small" effect="plain">{{ statusLabel(item.status) }}</el-tag>
              </div>
              <div class="interaction-content">{{ item.content || '-' }}</div>
              <div v-if="interactionPageUrl(item, index)" class="interaction-page">
                <span class="interaction-page-label">页面地址：</span>
                <span class="interaction-page-url" :title="interactionPageUrl(item, index)">{{ interactionPageUrl(item, index) }}</span>
                <el-button link type="primary" size="small" @click.stop="copyUrl(interactionPageUrl(item, index))">复制</el-button>
                <el-button link type="primary" size="small" @click.stop="openPageUrl(interactionPageUrl(item, index))">打开</el-button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="canConfirmFeedback" class="owner-confirm-actions">
          <el-divider />
          <div class="detail-label">提出人确认</div>
          <div class="confirm-tip">请确认处理结果是否符合预期。如果仍有问题，可以补充说明并继续反馈。</div>
          <el-input v-model="reopenReason" type="textarea" :rows="2" placeholder="继续反馈时可填写补充说明（可选）" maxlength="200" show-word-limit />
          <div class="confirm-actions">
            <el-button type="success" :loading="confirming" @click="handleConfirmClose">确认完成</el-button>
            <el-button type="warning" :loading="reopening" @click="handleReopen">继续反馈</el-button>
          </div>
        </div>

        <div v-if="canReplyFeedback" class="detail-actions">
          <template v-if="!isFinishedStatus(detail.status)">
            <div class="detail-section">
              <div class="detail-label">{{ replySectionTitle }}</div>
              <div v-if="isFeedbackLockedForConfirm" class="confirm-waiting-tip">处理结果已提交，等待反馈人确认；确认前不能继续回复或再次解决。</div>
              <el-input v-model="replyForm.admin_reply" type="textarea" :rows="3" :placeholder="replyPlaceholder" maxlength="200" show-word-limit :disabled="isFeedbackLockedForConfirm" />
              <div style="margin-top:10px;display:flex;gap:8px">
                <el-button type="primary" :loading="replying" :disabled="isFeedbackLockedForConfirm" @click="submitReply">{{ replyButtonText }}</el-button>
                <el-button v-if="canResolveFeedback" type="success" :loading="resolving" :disabled="isFeedbackLockedForConfirm" @click="handleResolve">解决</el-button>
              </div>
            </div>
          </template>
          <el-divider />
          <el-button type="danger" plain @click="handleDelete">删除此反馈</el-button>
        </div>

        <div v-else-if="detail.user_id === currentUserId" class="detail-actions">
          <el-divider />
          <el-button type="danger" plain @click="handleDelete">删除此反馈</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatBeijingMinute } from '@/utils/beijingTime'
import { Plus, CircleClose, Search } from '@element-plus/icons-vue'
import { confirmCloseFeedback, createFeedback, getFeedback, getFeedbackReminders, getFeedbacks, reopenFeedback, replyFeedback, resolveFeedback, deleteFeedback, uploadFeedbackImage } from '@/api/feedback'
import { copyToClipboard } from '@/utils/clipboard'

const userStore = useUserStore()
const route = useRoute()
const isSuperAdmin = computed(() => userStore.userInfo?.is_superuser)
const currentUserId = computed(() => userStore.userInfo?.id)
const isDetailOwner = computed(() => detail.value?.user_id === currentUserId.value)
const canConfirmFeedback = computed(() => isDetailOwner.value && detail.value?.status === 'pending_confirm')
const canHandleFeedback = computed(() => isSuperAdmin.value && !isDetailOwner.value)
const canResolveFeedback = computed(() => isSuperAdmin.value && detail.value && !isFinishedStatus(detail.value.status) && detail.value.status !== 'pending_confirm')
const isFeedbackLockedForConfirm = computed(() => detail.value?.status === 'pending_confirm')
const canReplyFeedback = computed(() => !isFinishedStatus(detail.value?.status) && (canHandleFeedback.value || (isDetailOwner.value && !isFeedbackLockedForConfirm.value)))
const replySectionTitle = computed(() => isDetailOwner.value ? '补充说明' : '回复 / 处理')
const replyPlaceholder = computed(() => isDetailOwner.value ? '补充问题现象、复现步骤或最新信息（最多200字）' : '回复内容（最多200字）')
const replyButtonText = computed(() => isDetailOwner.value ? '提交补充' : '仅回复')
const detailInteractions = computed(() => Array.isArray(detail.value?.interaction_logs) ? detail.value.interaction_logs : [])
const reminderCounts = ref({ todo_count: 0, my_attention_count: 0 })
const myFeedbackBadgeCount = computed(() => Number(reminderCounts.value.my_attention_count || 0))
const todoFeedbackBadgeCount = computed(() => Number(reminderCounts.value.todo_count || 0))

const activeTab = ref('my')
const keyword = ref('')
const filterStatus = ref(null)
const filterType = ref(null)
const feedbacks = ref([])
const loading = ref(false)
const showFlowHelp = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const errorMessage = ref('')

// Create
const showCreate = ref(false)
const submitting = ref(false)
const form = ref({ type: 'bug', title: '', content: '', page_url: '', image_urls: [] })

// Detail
const showDetail = ref(false)
const detail = ref(null)
const replying = ref(false)
const replyForm = ref({ admin_reply: '', status: 'processing' })
const resolving = ref(false)
const confirming = ref(false)
const reopening = ref(false)
const reopenReason = ref('')

function typeTag(t) { return t === 'bug' ? 'danger' : t === 'suggestion' ? 'success' : 'info' }
function typeLabel(t) { return t === 'bug' ? 'Bug' : t === 'suggestion' ? '建议' : '其他' }
function isFinishedStatus(s) { return s === 'resolved' || s === 'completed' }
function statusTag(s) { return s === 'pending' ? 'warning' : s === 'processing' ? '' : s === 'pending_confirm' ? 'danger' : 'success' }
function statusLabel(s) { return s === 'pending' ? '待处理' : s === 'processing' ? '处理中' : s === 'pending_confirm' ? '待确认' : isFinishedStatus(s) ? '已完成' : '未知' }
function interactionLabel(t) {
  const labels = {
    submit: '提交反馈',
    supplement: '补充说明',
    reply: '处理回复',
    resolve: '提交处理结果',
    reopen: '继续反馈',
    confirm_close: '确认完成',
    confirm_complete: '确认完成',
  }
  return labels[t] || '互动'
}

function formatTime(t) {
  return formatBeijingMinute(t)
}

function formatBadgeCount(count) {
  const value = Number(count || 0)
  return value > 99 ? '99+' : value
}

function interactionPageUrl(item, index) {
  if (item?.type !== 'submit') return ''
  return item.page_url || (index === 0 ? detail.value?.page_url : '') || ''
}

async function copyUrl(url) {
  if (await copyToClipboard(url)) ElMessage.success('链接已复制')
}

function openPageUrl(url) {
  if (url) window.open(url, '_blank', 'noopener,noreferrer')
}

async function loadReminderCounts() {
  try {
    const data = await getFeedbackReminders()
    reminderCounts.value = {
      todo_count: Number(data?.todo_count || 0),
      my_attention_count: Number(data?.my_attention_count || 0),
    }
  } catch {
    reminderCounts.value = { todo_count: 0, my_attention_count: 0 }
  }
}

function onFeedbackRemindersRefresh() {
  loadReminderCounts()
}

onMounted(async () => {
  form.value.page_url = window.location.href
  applyRouteQuery()
  await loadList()
  await loadReminderCounts()
  await openRouteFeedback()
  window.addEventListener('feedback-reminders-refresh', onFeedbackRemindersRefresh)
})

onBeforeUnmount(() => {
  window.removeEventListener('feedback-reminders-refresh', onFeedbackRemindersRefresh)
})

// 弹窗打开期间监听全局粘贴（弹窗内任意位置 Ctrl+V 生效，不重复触发）
watch(showCreate, (v) => {
  if (!v) return
  const handler = (e) => {
    if (form.value.image_urls.length >= 6) return
    const items = e.clipboardData?.items
    if (!items) return
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault()
        const blob = item.getAsFile()
        if (blob) uploadFile(blob)
        return
      }
    }
  }
  document.addEventListener('paste', handler)
  watch(showCreate, (v) => { if (!v) document.removeEventListener('paste', handler) }, { once: true })
})

async function loadList() {
  loading.value = true
  errorMessage.value = ''
  try {
    const params = {}
    if (keyword.value) params.keyword = keyword.value
    if (filterStatus.value && filterStatus.value !== 'all') params.status = filterStatus.value
    if (filterType.value) params.type = filterType.value
    params.scope = activeTab.value
    params.skip = (page.value - 1) * pageSize.value
    params.limit = pageSize.value
    const res = await getFeedbacks(params)
    feedbacks.value = Array.isArray(res) ? res : (res?.items || [])
    total.value = Array.isArray(res) ? res.length : Number(res?.total || 0)
  } catch (error) { errorMessage.value = error?.message || '反馈列表加载失败，请重试' }
  finally { loading.value = false }
}

function applyRouteQuery() {
  if (route.query.tab === 'todo' && isSuperAdmin.value) activeTab.value = 'todo'
  else if (route.query.tab === 'all' && isSuperAdmin.value) activeTab.value = 'all'
  else activeTab.value = 'my'
  filterStatus.value = route.query.status || null
}

async function openRouteFeedback() {
  const feedbackId = Number(route.query.feedback_id)
  if (!feedbackId) return
  await openDetail({ id: feedbackId })
  window.dispatchEvent(new Event('feedback-reminders-refresh'))
}

function handleTabChange() {
  page.value = 1
  loadList()
}

function handlePageChange(val) {
  page.value = val
  loadList()
}

function handlePageSizeChange(size) {
  pageSize.value = size
  page.value = 1
  loadList()
}

function searchList() {
  page.value = 1
  loadList()
}

function clearStatusFilterForFlowChange() {
  filterStatus.value = null
}

// --- Create ---
async function handleUpload({ file }) { await uploadFile(file) }

async function uploadFile(file) {
  if (file.size > 5 * 1024 * 1024) { ElMessage.error('图片不能超过 5MB'); return }
  try {
    const res = await uploadFeedbackImage(file, { skipErrorToast: true })
    form.value.image_urls.push(res.url)
  } catch { ElMessage.error('上传失败') }
}

function removeImage(i) { form.value.image_urls.splice(i, 1) }

async function submitFeedback() {
  if (!form.value.title.trim()) { ElMessage.warning('请输入标题'); return }
  if (!form.value.content.trim()) { ElMessage.warning('请输入详细描述'); return }
  submitting.value = true
  try {
    await createFeedback({ ...form.value })
    showCreate.value = false
    form.value = { type: 'bug', title: '', content: '', page_url: window.location.href, image_urls: [] }
    loadList()
    window.dispatchEvent(new Event('feedback-reminders-refresh'))
  } catch {} finally { submitting.value = false }
}

// --- Detail ---
async function openDetail(fb) {
  const wasReopenUnread = Boolean(fb.is_reopen_unread)
  try {
    const res = await getFeedback(fb.id)
    detail.value = res || fb
    resetDetailForm()
    reopenReason.value = ''
    showDetail.value = true
    if (fb.is_reply_unread) {
      fb.is_reply_unread = false
      window.dispatchEvent(new Event('feedback-reminders-refresh'))
    }
    if (wasReopenUnread) {
      fb.is_reopen_unread = false
      window.dispatchEvent(new Event('feedback-reminders-refresh'))
    }
  } catch {
    detail.value = fb
    resetDetailForm()
    reopenReason.value = ''
    showDetail.value = true
  }
}

function resetDetailForm() {
  replyForm.value = { admin_reply: '', status: 'processing' }
  reopenReason.value = ''
}

async function refreshDetail() {
  if (!detail.value?.id) return
  const res = await getFeedback(detail.value.id)
  if (res) detail.value = res
}

async function submitReply() {
  if (!replyForm.value.admin_reply.trim()) { ElMessage.warning('请输入回复内容'); return }
  replying.value = true
  try {
    const payload = isDetailOwner.value
      ? { admin_reply: replyForm.value.admin_reply }
      : { admin_reply: replyForm.value.admin_reply, status: 'processing' }
    await replyFeedback(detail.value.id, payload)
    await refreshDetail()
    resetDetailForm()
    clearStatusFilterForFlowChange()
    loadList()
    window.dispatchEvent(new Event('feedback-reminders-refresh'))
  } catch {} finally { replying.value = false }
}

async function handleResolve() {
  if (!replyForm.value.admin_reply.trim()) { ElMessage.warning('解决时必须填写回复内容'); return }
  resolving.value = true
  try {
    await ElMessageBox.confirm('确认标记为已解决，等待提出人确认？', '确认', { type: 'warning' })
    const res = await resolveFeedback(detail.value.id, { status: 'pending_confirm', admin_reply: replyForm.value.admin_reply })
    if (res) detail.value = res
    await refreshDetail()
    resetDetailForm()
    clearStatusFilterForFlowChange()
    loadList()
    window.dispatchEvent(new Event('feedback-reminders-refresh'))
  } catch {} finally { resolving.value = false }
}

async function handleConfirmClose() {
  confirming.value = true
  try {
    await ElMessageBox.confirm('确认完成此反馈？确认后表示该问题已处理完成。', '确认完成', { type: 'success' })
    const res = await confirmCloseFeedback(detail.value.id)
    if (res) detail.value = res
    await refreshDetail()
    resetDetailForm()
    clearStatusFilterForFlowChange()
    loadList()
    window.dispatchEvent(new Event('feedback-reminders-refresh'))
  } catch {} finally { confirming.value = false }
}

async function handleReopen() {
  reopening.value = true
  try {
    await ElMessageBox.confirm('确认继续反馈？该问题会重新进入待处理。', '继续反馈', { type: 'warning' })
    const res = await reopenFeedback(detail.value.id, { reason: reopenReason.value })
    if (res) detail.value = res
    await refreshDetail()
    resetDetailForm()
    clearStatusFilterForFlowChange()
    loadList()
    window.dispatchEvent(new Event('feedback-reminders-refresh'))
  } catch {} finally { reopening.value = false }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm('确认删除此反馈？', '确认', { type: 'warning' })
    await deleteFeedback(detail.value.id)
    showDetail.value = false
    loadList()
    window.dispatchEvent(new Event('feedback-reminders-refresh'))
  } catch {}
}

watch(() => route.query, async () => {
  applyRouteQuery()
  await loadList()
  await openRouteFeedback()
})
</script>

<style scoped>
.page-wrap { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.page-header { flex-shrink: 0; }
.page-title { font-size: 22px; font-weight: 700; margin: 0 0 14px; }
.search-area { flex-shrink: 0; margin-bottom: 16px; }
.toolbar { display: flex; gap: 10px; align-items: center; }
.scroll-area { flex: 1; overflow-y: auto; min-height: 0; }
.load-error { margin-bottom: 10px; }
.pagination-area { flex-shrink: 0; display: flex; justify-content: flex-end; padding: 12px 0 0; }
.feedback-tab-label { display: inline-flex; align-items: center; gap: 6px; }
.tab-count { min-width: 16px; height: 16px; padding: 0 4px; border-radius: 8px; background: #f56c6c; color: #fff; font-size: 11px; font-weight: 600; line-height: 16px; text-align: center; }

/* 截图输入框 */
.screenshot-input {
  display: flex; align-items: center; min-height: 60px;
  border: 1px solid #dcdfe6; border-radius: 6px;
  padding: 8px 10px; cursor: text; transition: border-color .2s;
  background: #fff; width: 100%; box-sizing: border-box;
}
.screenshot-input:focus-within,
.screenshot-input:focus { border-color: var(--nexus-primary, #1677ff); outline: none; }

.screenshot-body { flex: 1; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.placeholder-text { color: #c0c4cc; font-size: 14px; user-select: none; }

.upload-preview { position: relative; width: 72px; height: 72px; flex-shrink: 0; }
.upload-preview :deep(.el-image) { width: 100%; height: 100%; border-radius: 4px; border: 1px solid #eee; }
.upload-preview .remove-btn {
  position: absolute; top: -6px; right: -6px; color: #f56c6c; cursor: pointer;
  font-size: 18px; background: #fff; border-radius: 50%; z-index: 1;
}

.screenshot-upload { flex-shrink: 0; margin-left: 6px; }
.plus-btn {
  width: 46px; height: 46px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: #909399; transition: all .2s; background: #f5f5f5;
}
.plus-btn:hover { background: #e6f4ff; color: var(--nexus-primary, #1677ff); }

.upload-tip { font-size: 12px; color: #c0c4cc; margin-top: 6px; }

/* 详情弹窗 */
.detail-top { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.detail-title { font-size: 18px; font-weight: 600; }
.detail-meta { font-size: 13px; color: #909399; margin-bottom: 16px; display: flex; align-items: center; gap: 6px; }
.detail-section { margin-bottom: 16px; }
.detail-label { font-size: 14px; font-weight: 600; color: #333; margin-bottom: 8px; }
.detail-content { color: #333; line-height: 1.7; white-space: pre-wrap; font-size: 14px; }
.detail-images { display: flex; gap: 8px; flex-wrap: wrap; }
.detail-thumb { width: 100px; height: 100px; border-radius: 6px; cursor: pointer; border: 1px solid #eee; }
.interaction-list { display: flex; flex-direction: column; gap: 10px; }
.interaction-item { border: 1px solid #ebeef5; border-radius: 6px; padding: 10px 12px; background: #fff; }
.interaction-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.interaction-action { font-size: 13px; font-weight: 700; color: var(--nexus-primary, #1677ff); }
.interaction-user { font-size: 13px; color: #303133; }
.interaction-time { font-size: 12px; color: #909399; }
.interaction-content { color: #333; line-height: 1.6; white-space: pre-wrap; font-size: 14px; }
.interaction-page { display: flex; align-items: center; gap: 6px; margin-top: 8px; min-width: 0; color: #606266; font-size: 13px; }
.interaction-page-label { flex: 0 0 auto; }
.interaction-page-url { min-width: 0; overflow: hidden; color: #606266; text-overflow: ellipsis; white-space: nowrap; }
.interaction-page :deep(.el-button) { flex: 0 0 auto; height: 24px; padding: 0 4px; }
.detail-actions { margin-top: 8px; }
.owner-confirm-actions { margin-top: 8px; }
.confirm-tip { color: #606266; font-size: 13px; line-height: 1.6; margin-bottom: 10px; }
.confirm-waiting-tip {
  padding: 9px 12px;
  margin-bottom: 10px;
  border: 1px solid #d9ecff;
  border-radius: 6px;
  background: #f5faff;
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
}
.confirm-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 10px; }
.flow-help { display: flex; flex-direction: column; gap: 16px; }
.flow-step { display: flex; gap: 12px; align-items: flex-start; }
.flow-step span {
  width: 28px; height: 28px; border-radius: 50%; background: #e6f4ff; color: var(--nexus-primary, #1677ff);
  display: inline-flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0;
}
.flow-step b { display: block; color: #303133; margin-bottom: 4px; }
.flow-step p { margin: 0; color: #606266; font-size: 14px; line-height: 1.7; }
.flow-note {
  padding: 12px 14px;
  border: 1px solid #d9ecff;
  border-radius: 6px;
  background: #f5faff;
  color: #606266;
  font-size: 13px;
  line-height: 1.7;
}

:deep(.el-table .cell) {
  white-space: nowrap;
}
</style>
