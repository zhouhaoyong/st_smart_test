<template>
  <div class="ps-page">
    <div class="page-header">
      <div class="page-title">
        <h2>参数集管理</h2>
        <span class="page-desc">按环境或业务场景管理可复用参数，接口和用例通过 $.key 引用。</span>
      </div>
    </div>

    <div class="list-toolbar-frame">
      <div class="toolbar">
        <el-input v-model="searchText" placeholder="搜索参数集名称" clearable style="width:260px" :prefix-icon="Search" />
        <el-button type="primary" @click="onSearch" :icon="Search">搜索</el-button>
      </div>
      <div class="list-toolbar-actions">
        <el-button type="primary" plain :icon="QuestionFilled" @click="helpDialogVisible = true">使用说明</el-button>
        <el-button type="primary" @click="handleCreate" :icon="Plus">新建参数集</el-button>
      </div>
    </div>

    <div class="ps-grid" v-if="list.length > 0">
      <div v-for="ps in list" :key="ps.id" class="ps-card" @click="router.push(`/project/${projectId}/parameter-sets/${ps.id}`)">
        <div class="ps-card-top">
          <div class="ps-avatar" :style="getAvatarStyle(ps.id)">{{ ps.name.charAt(0) }}</div>
          <div class="ps-card-title">
            <div class="ps-title-text">
              <div class="ps-name-text">{{ ps.name }}</div>
              <div class="ps-card-desc" :title="ps.description || '暂无描述'">{{ ps.description || '暂无描述' }}</div>
            </div>
            <span class="meta-time title-time">{{ formatDate(ps.created_at) }}</span>
          </div>
        </div>
        <div class="ps-card-body">
          <div class="ps-info-row">
            <span class="info-label">参数</span>
            <span class="info-value" v-if="ps.item_count">{{ ps.item_count }} 项</span>
            <span v-else class="info-value">暂未配置</span>
          </div>
        </div>
        <div class="ps-card-footer">
          <div class="ps-creator">
            <div class="creator-avatar" :style="ps.creator_avatar ? {} : getCreatorAvatarStyle(ps.created_by)">
              <img v-if="ps.creator_avatar" :src="ps.creator_avatar" class="avatar-img" />
              <span v-else>{{ ps.creator_name?.charAt(0) || '?' }}</span>
            </div>
            <span>{{ ps.creator_name || '未知' }}</span>
          </div>
          <div class="ps-card-actions">
            <el-button size="small" @click.stop="router.push(`/project/${projectId}/parameter-sets/${ps.id}`)">进入</el-button>
            <el-button size="small" @click.stop="handleEdit(ps)">编辑</el-button>
            <el-button size="small" type="success" @click.stop="handleCopy(ps)">复制</el-button>
            <el-button size="small" type="danger" @click.stop="handleDelete(ps)">删除</el-button>
          </div>
        </div>
      </div>
    </div>

    <GlobalEmpty
      v-else-if="!loading"
      :text="searchKeyword ? '未找到匹配的参数集' : '当前项目暂无参数集'"
      :action-text="!searchKeyword ? '立即创建' : ''"
      @action="handleCreate"
    />

    <div class="loading-state" v-if="loading">
      <el-skeleton :rows="3" animated />
    </div>

    <el-pagination
      v-if="total > 0"
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 50, 100]"
      layout="total, sizes, prev, pager, next"
      @current-change="onPageChange"
      @size-change="onPageSizeChange"
      style="margin-top:20px;justify-content:flex-end;display:flex"
    />

    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" destroy-on-close :close-on-click-modal="false" class="ps-dialog">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="72px" class="ps-form">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：测试参数集" maxlength="50" show-word-limit class="compact-input" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选" maxlength="50" show-word-limit class="compact-input" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">{{ form.id ? '保存修改' : '创建参数集' }}</el-button>
      </template>
    </el-dialog>

    <!-- 使用说明 -->
    <el-dialog v-model="helpDialogVisible" title="参数集怎么用？" width="640px" destroy-on-close class="ps-help-dialog">
      <div class="help-content">
        <p class="help-intro">参数集用于集中管理不同环境或业务场景下的可复用参数，接口和用例通过变量引用使用。</p>
        <div class="help-steps">
          <div class="help-step">
            <span class="help-step-index">1</span>
            <div>
              <h3>创建参数集</h3>
              <p>按环境或业务场景分组，例如“测试环境账号”或“预发布环境配置”。</p>
            </div>
          </div>
          <div class="help-step">
            <span class="help-step-index">2</span>
            <div>
              <h3>添加参数</h3>
              <p>填写参数名称、Key 和 Value；参数名称便于识别，Key 用于在接口和用例中引用。</p>
            </div>
          </div>
          <div class="help-step">
            <span class="help-step-index">3</span>
            <div>
              <h3>引用参数</h3>
              <p>在查询参数、路径参数、请求体或请求头中填写 <code>$.key</code>。</p>
            </div>
          </div>
        </div>
        <div class="help-tip"><strong>运行提示：</strong>运行时会读取当前参数值，修改 Value 后无需逐个修改接口和用例。</div>
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
import { Plus, Search, Delete, QuestionFilled } from '@element-plus/icons-vue'
import { getParameterSets, getParameterSet, createParameterSet, updateParameterSet, deleteParameterSet, copyParameterSet } from '@/api/parameterSet'
import { confirmDelete } from '@/utils/confirmDelete'
import { formatBeijingDate } from '@/utils/beijingTime'
import GlobalEmpty from '@/components/GlobalEmpty.vue'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => route.params.id)
const refreshParameterSets = inject('refreshParameterSets', null)

const list = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const searchText = ref('')
const searchKeyword = ref('')

const dialogVisible = ref(false)
const helpDialogVisible = ref(false)
const dialogTitle = ref('')
const submitLoading = ref(false)
const formRef = ref(null)
const form = reactive({ id: null, name: '', description: '' })
const rules = { name: [{ required: true, message: '请输入参数集名称', trigger: 'blur' }] }

const avatarTextColors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#f5222d', '#faad14']
const avatarBgColors = ['#e6f4ff', '#f0f5ff', '#e6fffb', '#fff7e6', '#f9f0ff', '#fff0f6', '#e6fffb', '#f6ffed']
function getAvatarStyle(id) {
  return {
    background: avatarBgColors[(id || 0) % avatarBgColors.length],
    color: avatarTextColors[(id || 0) % avatarTextColors.length],
  }
}
const getCreatorAvatarStyle = getAvatarStyle
const formatDate = (value) => value ? formatBeijingDate(value) || '-' : '-'

function onSearch() {
  searchKeyword.value = searchText.value.trim()
  page.value = 1
  loadData()
}

async function loadData() {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await getParameterSets(projectId.value, page.value, pageSize.value, { name: searchKeyword.value })
    list.value = res?.items || []
    total.value = res?.total || 0
  } catch { list.value = [] }
  finally { loading.value = false }
}

function handleCreate() {
  dialogTitle.value = '新建参数集'
  Object.assign(form, { id: null, name: '', description: '' })
  dialogVisible.value = true
  setTimeout(() => formRef.value?.clearValidate(), 100)
}

async function handleEdit(ps) {
  dialogTitle.value = '编辑参数集'
  const res = await getParameterSet(ps.id)
  Object.assign(form, { id: res.id, name: res.name, description: res.description || '' })
  dialogVisible.value = true
  setTimeout(() => formRef.value?.clearValidate(), 100)
}

async function handleCopy(ps) {
  try { await copyParameterSet(ps.id); loadData(); refreshParameterSets?.() } catch { }
}

async function handleDelete(ps) {
  const ok = await confirmDelete(ps.name, '参数集')
  if (!ok) return
  try { await deleteParameterSet(ps.id); loadData(); refreshParameterSets?.() } catch { }
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitLoading.value = true
    try {
      const data = { name: form.name, description: form.description || null, project_id: parseInt(projectId.value) }
      if (form.id) { await updateParameterSet(form.id, data) } else { await createParameterSet({ ...data, items: [] }) }
      dialogVisible.value = false
      loadData()
      refreshParameterSets?.()
    } catch { }
    finally { submitLoading.value = false }
  })
}

function onPageChange(val) {
  page.value = val
  loadData()
}

function onPageSizeChange(val) {
  pageSize.value = val
  page.value = 1
  loadData()
}

onMounted(() => { loadData() })
</script>

<style scoped>
.ps-page { max-width: 100%; height: 100%; display: flex; flex-direction: column; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 20px; }
.page-title h2 { margin: 0 0 6px; font-size: 20px; font-weight: 600; color: #1a1a1a; }
.page-desc { font-size: 14px; color: #8c8c8c; line-height: 1.6; display: block; max-width: 680px; }
.toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 0; }
.loading-state { padding: 20px 0; }

.ps-grid { display: grid; grid-template-columns: repeat(auto-fill, 392px); gap: 20px; }
.ps-card { background: #fff; border: 1px solid #e8edf3; border-radius: 14px; padding: 24px; overflow: hidden; cursor: pointer; display: flex; flex-direction: column; min-height: 174px; transition: box-shadow .2s ease, border-color .2s ease, transform .2s ease; }
.ps-card:hover { box-shadow: 0 10px 26px rgba(15,23,42,.09); border-color: #cfd8e3; transform: translateY(-2px); }
.ps-card-top { display: flex; align-items: center; gap: 14px; margin-bottom: 16px; }
.ps-avatar { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: 700; flex-shrink: 0; transition: transform .24s cubic-bezier(0.2,0,0,1); }
.ps-card:hover .ps-avatar { transform: scale(1.06); }
.ps-card-title { display:flex; align-items:flex-start; gap:10px; flex:1; min-width:0; }
.ps-title-text { flex:1; min-width:0; }
.ps-name-text { flex:1; min-width:0; font-size:17px; font-weight:600; color:#1a1a1a; display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ps-card-desc { font-size:13px; color:#8c8c8c; font-weight:400; display:block; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-top:4px; }
.ps-card-body { display: flex; flex-direction: column; gap: 10px; flex: 1; }
.ps-info-row { display: flex; align-items: baseline; gap: 10px; overflow: hidden; }
.ps-card-footer { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-top: 14px; padding-top: 14px; border-top: 1px solid #f1f3f6; }
.ps-creator { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #8c8c8c; min-width: 0; flex: 1; }
.ps-creator > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meta-time { color: #bfbfbf; font-size: 12px; white-space: nowrap; }
.title-time { flex-shrink: 0; font-weight: 400; }
.creator-avatar { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; flex-shrink: 0; overflow: hidden; }
.avatar-img { width: 100%; height: 100%; object-fit: cover; }
.ps-card-actions { display: flex; align-items: center; gap: 12px; justify-content: flex-end; flex-shrink: 0; }
.ps-card-actions .el-button + .el-button { margin-left: 0; }
.ps-card-actions .el-button { min-width: 52px; height: 30px; padding: 6px 10px; border-radius: 6px; }
.info-label { font-size: 13px; color: #8c8c8c; flex-shrink: 0; min-width: 50px; }
.info-value { font-size: 14px; color: #595959; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ps-dialog :deep(.el-dialog__body) { padding: 18px 24px 8px; }
.ps-form { max-width: 420px; margin: 0 auto; }
.compact-input { width: 100%; }
.ps-help-dialog :deep(.el-dialog__body) { padding: 20px 28px 8px; }
.help-content { color: #606266; }
.help-intro { margin: 0 0 20px; color: #4e5969; font-size: 14px; line-height: 1.8; }
.help-steps { display: flex; flex-direction: column; gap: 18px; }
.help-step { display: flex; align-items: flex-start; gap: 12px; }
.help-step-index { width: 24px; height: 24px; border-radius: 50%; background: #eaf3ff; color: #1677ff; display: inline-flex; align-items: center; justify-content: center; flex: 0 0 24px; font-size: 13px; font-weight: 600; }
.help-step h3 { margin: 0 0 5px; color: #303133; font-size: 14px; font-weight: 600; }
.help-step p { margin: 0; color: #606266; font-size: 13px; line-height: 1.75; }
.help-step code { padding: 2px 6px; border-radius: 4px; background: #eef6ff; color: #1677ff; font-family: Monaco, Consolas, monospace; }
.help-tip { margin-top: 22px; padding: 11px 13px; border: 1px solid #dbeafe; border-radius: 6px; background: #f5f9ff; color: #58708f; font-size: 13px; line-height: 1.7; }
.help-tip strong { color: #1677ff; font-weight: 600; }

@media (max-width: 768px) {
  .page-header { gap: 12px; flex-direction: column; }
  .ps-grid { grid-template-columns: minmax(0, 1fr); }
  .ps-card { padding: 18px; min-height: 0; }
  .ps-dialog :deep(.el-dialog) { width: 92vw !important; }
  .ps-help-dialog :deep(.el-dialog) { width: 92vw !important; }
  .ps-form { max-width: none; }
}

@media (max-width: 480px) {
  .ps-card-footer { align-items: flex-start; flex-direction: column; }
  .ps-card-actions { justify-content: center; flex-wrap: wrap; }
}

</style>
