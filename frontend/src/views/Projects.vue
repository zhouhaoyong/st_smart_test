<template>
  <div class="projects-page">
    <div class="page-header">
      <div class="page-title">
        <h2>项目管理</h2>
        <span class="page-desc">管理您的 API 测试项目</span>
      </div>
    </div>

    <ProjectSearchBar
      v-model="searchKeyword"
      :loading="loading"
      @search="doSearch"
      @clear="doSearch"
      @create="handleCreate"
    >
      <template #actions>
        <el-button plain size="default" :icon="QuestionFilled" @click="guideVisible = true">使用指南</el-button>
      </template>
    </ProjectSearchBar>

    <div v-if="loadError" class="load-error">
      <span>加载失败，请重试</span>
      <el-button link type="primary" @click="loadProjects">重新加载</el-button>
    </div>

    <ProjectCardList
      :projects="projectList"
      :loading="loading"
      show-copy
      @enter="handleEnterProject"
      @edit="handleEdit"
      @copy="handleCopy"
      @delete="handleDelete"
      @create="handleCreate"
    />

    <el-pagination
      v-if="total > 0"
      v-model:current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="total, sizes, prev, pager, next"
      :page-sizes="[10, 50, 100]"
      @current-change="onPageChange"
      @size-change="onPageSizeChange"
      class="page-pagination"
    />

    <ProjectFormDialog
      v-model="dialogVisible"
      :title="dialogTitle"
      :submit-text="formData.id ? '保存' : '创建'"
      :loading="submitLoading"
      :form-data="formData"
      @submit="handleSubmit"
    />

    <ApiTestGuideDialog v-model="guideVisible" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { QuestionFilled } from '@element-plus/icons-vue'
import { getProjects, createProject, updateProject, deleteProject, copyProject } from '@/api/project'
import { confirmDelete } from '@/utils/confirmDelete'
import ProjectCardList from '@/components/ProjectCardList.vue'
import ProjectFormDialog from '@/components/ProjectFormDialog.vue'
import ProjectSearchBar from '@/components/ProjectSearchBar.vue'
import ApiTestGuideDialog from '@/components/ApiTestGuideDialog.vue'

defineOptions({ name: 'Projects' })

const router = useRouter()
const guideVisible = ref(false)
const loading = ref(false)
const submitLoading = ref(false)
const projectList = ref([])
const searchKeyword = ref('')
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const loadError = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新建项目')
const formData = reactive({ id: null, name: '', description: '', tags: [], color: '', is_public: true })

const loadProjects = async () => {
  loading.value = true
  try {
    const params = { skip: (page.value - 1) * pageSize.value, limit: pageSize.value }
    if (searchKeyword.value) params.search = searchKeyword.value
    const res = await getProjects(params)
    projectList.value = res.items || []
    total.value = res.total || 0
    loadError.value = false
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

const onPageChange = (val) => {
  page.value = val
  loadProjects()
}

const onPageSizeChange = (size) => {
  pageSize.value = size
  page.value = 1
  loadProjects()
}

const doSearch = () => {
  page.value = 1
  loadProjects()
}

const handleCreate = () => {
  dialogTitle.value = '新建项目'
  Object.assign(formData, { id: null, name: '', description: '', tags: [], color: '', is_public: true })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑项目'
  Object.assign(formData, { id: row.id, name: row.name, description: row.description || '', tags: row.tags || [], color: row.color || '', is_public: row.is_public })
  dialogVisible.value = true
}

const handleEnterProject = (row) => router.push(`/project/${row.id}/dashboard`)

const handleDelete = async (row) => {
  const ok = await confirmDelete(row.name, '项目')
  if (!ok) return
  await deleteProject(row.id)
  loadProjects()
}

const handleCopy = async (row) => {
  try {
    await copyProject(row.id)
    loadProjects()
  } catch {}
}

const handleSubmit = async () => {
  submitLoading.value = true
  try {
    const data = {
      name: formData.name,
      description: formData.description || null,
      tags: formData.tags,
      color: formData.color || null,
      is_public: formData.is_public,
    }
    if (formData.id) await updateProject(formData.id, data)
    else await createProject(data)
    dialogVisible.value = false
    loadProjects()
  } catch {
  } finally {
    submitLoading.value = false
  }
}

onMounted(loadProjects)
</script>

<style scoped>
.projects-page { max-width: 100%; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.page-title h2 { margin: 0 0 6px; font-size: 20px; font-weight: 600; color: #1a1a1a; }
.page-desc { font-size: 15px; color: #8c8c8c; }
.page-pagination { margin-top: 24px; justify-content: flex-end; display: flex; }
.load-error { margin: -12px 0 16px; color: #f56c6c; display: flex; align-items: center; gap: 8px; }
@media (max-width: 720px) {
  .page-header { align-items: stretch; flex-direction: column; gap: 14px; }
}
</style>
