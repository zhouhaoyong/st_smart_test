<template>
  <div class="page-wrap">
    <!-- lazy 不可省：页签默认会把所有页签的内容都渲染出来（仅用 v-show 隐藏），
         导致进入审计日志时把数据清理整页也建了出来 -->
    <el-tabs :model-value="activeTab" class="flex-tabs" @update:model-value="onTabChange">
      <el-tab-pane label="审计日志" name="audit" lazy>
        <AuditLogs />
      </el-tab-pane>
      <el-tab-pane label="数据清理" name="cleanup" lazy>
        <DataCleanup />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent } from 'vue'
import { useRoute, useRouter } from 'vue-router'

// 两个页签各自是完整页面，静态导入会让进入任一页签都要下载并编译全部页签的代码，
// 配合上面的 lazy 改为按需加载：只加载当前页签
const AuditLogs = defineAsyncComponent(() => import('@/views/AuditLogs.vue'))
const DataCleanup = defineAsyncComponent(() => import('@/views/DataCleanup.vue'))

const route = useRoute()
const router = useRouter()
const activeTab = computed(() => route.meta.tab || 'audit')
const tabMap = { audit: '/data-admin/audit', cleanup: '/data-admin/cleanup' }
function onTabChange(tab) {
  const target = tabMap[tab]
  if (target) router.push(target)
}
</script>

<style scoped>
.page-wrap { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.flex-tabs { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.flex-tabs :deep(.el-tabs__content) { flex: 1; min-height: 0; }
.flex-tabs :deep(.el-tab-pane) { height: 100%; }
</style>
