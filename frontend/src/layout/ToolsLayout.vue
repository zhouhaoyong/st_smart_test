<template>
  <div class="tools-layout">
    <TopBar />
    <div class="tools-body">
      <aside v-if="isTool" class="tools-sidebar">
      <div class="sidebar-section">
        <h4>工具箱</h4>
        <div
          v-for="group in toolGroups"
          :key="group.key"
          class="sidebar-group"
          :class="{ 'is-open': openGroups[group.key] }"
        >
          <button type="button" class="sidebar-group-title" @click="toggleGroup(group.key)">
            <span class="group-title-main">
              <el-icon :size="18"><component :is="group.icon" /></el-icon>
              <span>{{ group.label }}</span>
            </span>
            <el-icon :size="14" class="group-arrow"><ArrowDown /></el-icon>
          </button>
          <div v-show="openGroups[group.key]" class="sidebar-group-items">
            <router-link
              v-for="item in group.items"
              :key="item.path"
              :to="item.path"
              class="sidebar-item"
              :class="['sidebar-sub-item', {active: isToolItemActive(item.path)}]"
            >
              <span>{{ item.label }}</span>
            </router-link>
          </div>
        </div>
      </div>
    </aside>
    <main class="tools-main">
      <router-view v-slot="{ Component }">
        <KeepAlive include="NavigationApps">
          <component :is="Component" />
        </KeepAlive>
      </router-view>
    </main>
  </div>
</div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import TopBar from '@/layout/TopBar.vue'
import { UserFilled, Location, ChatDotRound, Timer, ArrowDown, Document, Finished, PictureFilled, Key, ChatLineSquare, Promotion, Connection } from '@element-plus/icons-vue'

defineOptions({ name: 'ToolsLayout' })

const route = useRoute()
const userStore = useUserStore()

const isNav = computed(() => route.path.includes('/tools/navigation'))
const isTool = computed(() => route.path.includes('/tools/') && !isNav.value)

const toolGroups = [
  {
    key: 'text',
    label: '文本处理',
    icon: ChatDotRound,
    items: [
      { path: '/tools/markdown-preview', label: 'Markdown预览', icon: Document },
      { path: '/tools/json-format', label: 'JSON格式化', icon: Finished },
      { path: '/tools/json-path-extractor', label: 'JSONPath提取', icon: Connection },
      { path: '/tools/text-diff', label: '文本对比', icon: ChatDotRound },
      { path: '/tools/translate', label: '多语言翻译', icon: ChatLineSquare },
      { path: '/tools/url-codec', label: 'URL 编解码', icon: Connection },
      { path: '/tools/base64', label: 'Base64', icon: Key },
      { path: '/tools/hash', label: '哈希', icon: Finished },
    ],
  },
  {
    key: 'generate',
    label: '生成工具',
    icon: Timer,
    items: [
      { path: '/tools/id-card', label: '身份证生成', icon: UserFilled },
      { path: '/tools/qrcode', label: '二维码生成', icon: PictureFilled },
      { path: '/tools/timestamp', label: '时间戳', icon: Timer },
      { path: '/tools/xmind', label: 'XMind用例', icon: Document },
      { path: '/tools/geocode', label: '地址转经纬度', icon: Location },
    ],
  },
  {
    key: 'assist',
    label: '调试辅助',
    icon: Promotion,
    items: [
      { path: '/tools/curl', label: 'cURL解析', icon: Promotion },
      { path: '/tools/cron', label: 'Cron 表达式', icon: Timer },
    ],
  },
]

const openGroups = reactive(Object.fromEntries(toolGroups.map(group => [group.key, true])))
const isToolItemActive = (path) => route.path === path || route.path.startsWith(`${path}/`)
const activeGroupKey = computed(() => toolGroups.find(group => group.items.some(item => isToolItemActive(item.path)))?.key || '')

const toggleGroup = (key) => {
  openGroups[key] = !openGroups[key]
}

watch(activeGroupKey, (key) => {
  if (key) openGroups[key] = true
}, { immediate: true })

</script>

<style scoped>
.tools-layout { display: flex; flex-direction: column; height: 100vh; background: #f7f8fa; }
/* 主体 */
.tools-body { flex: 1; display: flex; overflow: hidden; }
.tools-sidebar {
  width: 240px; background: #fafafa; border-right: 1px solid #f0f0f0;
  display: flex; flex-direction: column; flex-shrink: 0; overflow-y: auto; padding: 10px;
}
.sidebar-section { display: flex; flex-direction: column; gap: 4px; }
.sidebar-section h4 {
  font-size: 12px; color: #8c8c8c; letter-spacing: .5px;
  margin: 4px 6px 6px; font-weight: 600;
}
.sidebar-item {
  position: relative;
  display: grid; grid-template-columns: 22px minmax(0, 1fr); column-gap: 10px; align-items: center; padding: 10px 12px;
  border-radius: 8px; font-size: 15px; font-weight: 500; color: #595959;
  text-decoration: none; transition: background .2s, color .2s;
}
.sidebar-item .el-icon { width: 22px; justify-content: center; flex-shrink: 0; }
.sidebar-item span { min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.4; }
.sidebar-item:hover { background: #f0f0f0; color: #1a1a1a; }
.sidebar-item.active {
  background: #e6f4ff;
  color: #1677ff;
  font-weight: 600;
}
.sidebar-group {
  margin-top: 6px;
}
.sidebar-group-title {
  width: 100%;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 0;
  background: transparent;
  color: #8c8c8c;
  border-radius: 8px;
  padding: 0 10px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: .2px;
  transition: background .2s, color .2s;
}
.sidebar-group-title:hover {
  background: #f0f0f0;
  color: #1a1a1a;
}
.group-title-main {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.group-arrow {
  flex-shrink: 0;
  transition: transform .2s;
}
.sidebar-group.is-open .group-arrow {
  transform: rotate(180deg);
}
.sidebar-group-items {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 2px;
  padding-left: 0;
}
.sidebar-group-items .sidebar-item {
  grid-template-columns: 22px minmax(0, 1fr);
  padding-left: 12px;
  font-size: 15px;
}
.sidebar-sub-item {
  padding-top: 9px;
  padding-bottom: 9px;
}
.sidebar-sub-item::before {
  content: "";
  width: 22px;
}
.sidebar-sub-item span {
  display: block;
}
.tools-main { flex: 1; min-width: 0; overflow-y: auto; padding: 20px 24px; background: #fff; }
.tools-main :deep(.el-textarea__inner) {
  padding-left: 12px;
  box-shadow: 0 0 0 1px #dcdfe6 inset !important;
}
.tools-main :deep(.el-textarea__inner:hover) {
  box-shadow: 0 0 0 1px #cfd8e3 inset !important;
}
.tools-main :deep(.el-textarea__inner:focus) {
  border-color: transparent;
  box-shadow: 0 0 0 1px #1677ff inset !important;
}
@media (max-width: 1600px) {
  .tools-sidebar { width: 220px; }
  .tools-main { padding: 18px 20px; }
}
@media (max-width: 1440px) {
  .tools-sidebar { width: 200px; }
  .tools-main { padding: 16px; }
}
/* 平板 */
@media (max-width: 768px) {
  .tools-sidebar { width: 180px; }
  .sidebar-item { grid-template-columns: 20px minmax(0, 1fr); column-gap: 8px; padding: 10px 12px; font-size: 14px; }
  .sidebar-item .el-icon { width: 20px; }
  .sidebar-group-items .sidebar-item { grid-template-columns: 20px minmax(0, 1fr); }
  .sidebar-sub-item::before { width: 20px; }
  .tools-main { padding: 14px; }
}
/* 手机 */
@media (max-width: 480px) {
  .tools-sidebar { width: 52px; }
  .sidebar-item span, .sidebar-section h4, .sidebar-group-title span { display: none; }
  .sidebar-item { display: flex; justify-content: center; padding: 10px 0; }
  .sidebar-group-items { padding-left: 0; }
  .sidebar-group-title { justify-content: center; padding: 0; }
  .tools-main { padding: 10px; }
}
</style>
