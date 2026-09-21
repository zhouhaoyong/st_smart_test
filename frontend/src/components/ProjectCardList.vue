<template>
  <div class="project-grid" v-loading="loading">
    <div
      v-for="project in projects"
      :key="project.id"
      class="project-card"
      tabindex="0"
      @click="$emit('enter', project)"
      @keyup.enter="$emit('enter', project)"
    >
      <el-tag v-if="project.is_public" class="public-tag" size="small" type="success" effect="dark">公开</el-tag>
      <div class="project-card-top">
        <div class="project-avatar" :style="{ background: project.color || avatarBgColors[project.id % avatarBgColors.length], color: '#fff' }">
          {{ project.name?.charAt(0)?.toUpperCase() || '项' }}
        </div>
        <div class="project-card-body">
          <div class="project-name">{{ project.name }}</div>
          <div class="project-desc" v-if="project.description">{{ project.description }}</div>
          <div class="project-desc" v-else>暂无描述</div>
        </div>
      </div>
      <div class="project-tags" v-if="project.tags && project.tags.length">
        <el-tag v-for="(tag, index) in project.tags" :key="tag + index" size="small" effect="dark" :style="{ background: tagColors[index % tagColors.length], border: 'none' }">{{ tag }}</el-tag>
      </div>
      <div class="project-tags" v-else>
        <span class="project-tags-empty">暂无标签</span>
      </div>
      <div class="project-meta">
        <div class="project-owner" v-if="project.owner">
          <UserAvatar
            :size="24"
            :src="project.owner.avatar"
            :name="project.owner.real_name"
            :user-id="project.owner.id"
          />
          <span>{{ project.owner.real_name }}</span>
        </div>
        <span class="meta-text">{{ formatDate(project.created_at) }}</span>
      </div>
      <div class="project-card-footer">
        <div class="project-actions" @click.stop>
          <el-button size="small" @click="$emit('enter', project)">进入</el-button>
          <el-button size="small" @click="$emit('edit', project)">编辑</el-button>
          <el-button v-if="showCopy" size="small" type="success" @click="$emit('copy', project)">复制</el-button>
          <el-button size="small" type="danger" @click="$emit('delete', project)">删除</el-button>
        </div>
      </div>
    </div>
  </div>

  <div v-if="!loading && projects.length === 0" class="empty-state">
    <el-icon :size="48" color="#bfbfbf"><FolderOpened /></el-icon>
    <p>{{ emptyText }}</p>
    <el-button v-if="showEmptyAction" type="primary" :icon="Plus" @click="$emit('create')">{{ emptyActionText }}</el-button>
  </div>
</template>

<script setup>
import { formatBeijingDate } from '@/utils/beijingTime'
import { FolderOpened, Plus } from '@element-plus/icons-vue'
import UserAvatar from '@/components/UserAvatar.vue'

defineProps({
  projects: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  emptyText: { type: String, default: '暂无项目，点击上方按钮创建' },
  emptyActionText: { type: String, default: '新建项目' },
  showEmptyAction: { type: Boolean, default: true },
  showCopy: { type: Boolean, default: false },
})

defineEmits(['enter', 'edit', 'delete', 'copy', 'create'])

const tagColors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#f5222d', '#faad14']
const avatarBgColors = [
  'linear-gradient(135deg, #74b3ff 0%, #3f7fdb 100%)',
  'linear-gradient(135deg, #77c98a 0%, #3b9b62 100%)',
  'linear-gradient(135deg, #f2b36b 0%, #d9842f 100%)',
  'linear-gradient(135deg, #af83e9 0%, #7954c6 100%)',
  'linear-gradient(135deg, #eb8db7 0%, #cc578a 100%)',
  'linear-gradient(135deg, #63c9cb 0%, #238f98 100%)',
  'linear-gradient(135deg, #ee9187 0%, #d8554c 100%)',
  'linear-gradient(135deg, #8fa7eb 0%, #5873c9 100%)',
]
const formatDate = (d) => d ? formatBeijingDate(d) || '-' : '-'
</script>

<style scoped>
.project-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 20px; }
.project-card {
  position: relative;
  background: #fff; border: 1px solid #e8edf3; border-radius: 14px; padding: 24px;
  cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,.04); transition: all .2s; min-height: 160px;
  display: flex; flex-direction: column;
}
.project-card:hover { border-color: #cfd8e3; box-shadow: 0 10px 26px rgba(15,23,42,0.09); transform: translateY(-2px); }
.project-card:focus-visible { border-color: #1677ff; box-shadow: 0 0 0 3px rgba(22,119,255,0.16); }
.public-tag { position: absolute; top: 16px; right: 16px; z-index: 1; }
.project-card-top { display: flex; gap: 16px; margin-bottom: 14px; }
.project-avatar {
  width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center;
  font-size: 20px; font-weight: 700; flex-shrink: 0; box-shadow: inset 0 1px 0 rgba(255,255,255,.26), 0 4px 10px rgba(31, 62, 104, .12); text-shadow: 0 1px 2px rgba(0,0,0,.13);
}
.project-card-body { min-width: 0; flex: 1; padding-right: 50px; }
.project-name { font-size: 17px; font-weight: 600; color: #1a1a1a; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.project-desc { margin-top: 6px; color: #8c8c8c; font-size: 13px; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 38px; }
.project-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; min-height: 20px; }
.project-tags-empty { font-size: 12px; color: #c0c4cc; }
.project-meta { margin-top: auto; display: flex; justify-content: space-between; align-items: center; gap: 8px; color: #8c8c8c; font-size: 13px; }
.project-owner { display: flex; align-items: center; gap: 8px; min-width: 0; }
.meta-text { white-space: nowrap; }
.project-card-footer { margin-top: 14px; padding-top: 14px; border-top: 1px solid #eef2f6; }
.project-actions { display: flex; justify-content: center; gap: 8px; }
.empty-state {
  margin-top: 72px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  text-align: center;
  color: #8c8c8c;
}
.empty-state p { margin: 0; font-size: 16px; }
@media (max-width: 1024px) { .project-grid { grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; } }
@media (max-width: 768px) { .project-grid { grid-template-columns: 1fr; } }
@media (max-width: 480px) {
  .project-card { padding: 16px; }
  .project-card-body { padding-right: 40px; }
  .project-avatar { width: 40px; height: 40px; font-size: 17px; }
  .project-name { font-size: 15px; }
  .project-actions .el-button { font-size: 12px !important; padding: 5px 10px; }
}
</style>
