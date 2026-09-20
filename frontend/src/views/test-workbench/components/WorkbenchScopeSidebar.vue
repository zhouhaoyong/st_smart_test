<template>
  <aside class="wb-sidebar">
    <nav class="workbench-nav" aria-label="项目功能">
      <span class="nav-title">项目功能</span>
      <button
        v-for="item in navItems"
        :key="item.key"
        class="nav-item"
        :class="{ active: activeSection === item.key, disabled: item.disabled }"
        :disabled="item.disabled"
        @click="$emit('select-section', item.key)"
      >
        <el-icon :size="22"><component :is="navItemIcons[item.key]" /></el-icon>
        <span class="nav-label">{{ item.label }}</span>
        <el-badge
          v-if="item.badge"
          class="nav-badge"
          :value="item.badge"
          :max="99"
          type="danger"
        />
      </button>
    </nav>

    <section v-if="hasSystems" class="scope-selector" aria-label="当前作用域">
      <div class="scope-selector__header">
        <span class="scope-selector__title">系统与版本</span>
        <el-button link type="primary" @click="$emit('edit-scope')">编辑</el-button>
      </div>
      <button class="scope-selector__value" type="button" @click="$emit('open-scope-tab', 'system')">
        <span>系统</span>
        <strong>{{ systemLabel }}</strong>
      </button>
      <button class="scope-selector__value" type="button" @click="$emit('open-scope-tab', 'version')">
        <span>版本</span>
        <strong>{{ versionLabel }}</strong>
      </button>
    </section>
    <section v-else class="scope-empty" aria-label="当前作用域为空">
      <span class="scope-empty__title">系统与版本</span>
      <strong>暂无系统</strong>
      <span>请先在系统管理中创建系统</span>
    </section>

  </aside>
</template>

<script setup>
import { AlarmClock, CollectionTag, DataAnalysis, Document, FolderOpened, Monitor, Tickets, Warning } from '@element-plus/icons-vue'

const navItemIcons = {
  dashboard: DataAnalysis,
  pending: AlarmClock,
  systems: Monitor,
  versions: CollectionTag,
  requirements: Document,
  cases: Tickets,
  bugs: Warning,
  legacy: FolderOpened,
}

const props = defineProps({
  activeSection: { type: String, default: 'dashboard' },
  navItems: { type: Array, default: () => [] },
  systemLabel: { type: String, default: '全部系统' },
  versionLabel: { type: String, default: '全部版本' },
  hasSystems: { type: Boolean, default: false },
})
defineEmits(['select-section', 'edit-scope', 'open-scope-tab'])
</script>

<style scoped>
.wb-sidebar {
  border-right: 1px solid #f0f0f0;
  background: #fafafa;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.workbench-nav {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  padding: 10px;
}
.nav-title {
  padding: 6px 14px 2px;
  margin-bottom: 2px;
  color: #909399;
  font-size: 12px;
  font-weight: 500;
}
.nav-item {
  width: 100%;
  border: 0;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 8px;
  cursor: pointer;
  color: #595959;
  font-size: 15px;
  font-weight: 500;
  text-align: left;
  transition: all .2s;
}
.nav-item:hover:not(:disabled) { background: #f0f0f0; color: #1a1a1a; }
.nav-item.active { background: #e6f4ff; color: #1677ff; font-weight: 600; }
.nav-item.disabled { color: #c0c4cc; cursor: not-allowed; }
.nav-label { flex: 1; }
.nav-badge { margin-left: auto; }
.nav-badge :deep(.el-badge__content) { position: static; transform: none; border: 0; }
.scope-selector { display: flex; flex-direction: column; gap: 10px; margin: 0 10px 10px; padding: 12px; border: 1px solid #e1efff; border-radius: 10px; background: linear-gradient(145deg, #f5faff 0%, #fff 100%); box-shadow: 0 4px 12px rgba(64, 158, 255, .06); }
.scope-selector__header { display: flex; align-items: center; justify-content: space-between; min-height: 24px; padding: 0 2px; }
.scope-selector__title { color: #409eff; font-size: 14px; font-weight: 700; letter-spacing: .2px; }
.scope-selector__header :deep(.el-button) { padding: 3px 4px; font-size: 13px; font-weight: 600; }
.scope-selector__value { display: flex; width: 100%; align-items: center; justify-content: space-between; gap: 10px; min-height: 40px; padding: 6px 8px; border: 1px solid #edf3fc; border-radius: 7px; background: rgba(255, 255, 255, .72); color: #606266; cursor: pointer; font-size: 13px; text-align: left; transition: border-color .2s, background .2s; }
.scope-selector__value:hover { border-color: #b3d8ff; background: #f0f8ff; }
.scope-selector__value > span { display: inline-flex; align-items: center; justify-content: center; min-width: 38px; min-height: 24px; padding: 0 6px; border-radius: 5px; background: #edf5ff; color: #409eff; font-size: 13px; font-weight: 600; }
.scope-selector__value strong { min-width: 0; flex: 1; display: block; overflow: hidden; color: #303133; font-size: 14px; font-weight: 600; text-align: right; text-overflow: ellipsis; white-space: nowrap; }
.scope-empty { display: flex; flex-direction: column; gap: 6px; margin: 0 10px 10px; padding: 14px; border: 1px dashed #d9e8fb; border-radius: 10px; background: #f8fbff; color: #909399; font-size: 13px; line-height: 20px; }
.scope-empty__title { color: #409eff; font-size: 14px; font-weight: 700; }
.scope-empty strong { color: #606266; font-size: 14px; }

@media (max-width: 1440px) {
  .workbench-nav { padding: 8px; }
  .nav-item { gap: 10px; padding: 10px 12px; font-size: 14px; }
  .scope-selector { gap: 8px; padding: 10px; }
}

</style>
