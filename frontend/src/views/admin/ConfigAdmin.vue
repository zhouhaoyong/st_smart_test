<template>
  <div class="page-wrap">
    <!-- lazy 不可省：页签默认会把所有页签的内容都渲染出来（仅用 v-show 隐藏），
         导致进入任一页签实际建出三整页表格、筛选区与弹窗 -->
    <el-tabs :model-value="activeTab" class="flex-tabs" @update:model-value="onTabChange">
      <el-tab-pane label="消息渠道" name="channels" lazy>
        <MessageChannels />
      </el-tab-pane>
      <el-tab-pane label="消息模板" name="templates" lazy>
        <MessageTemplates />
      </el-tab-pane>
      <el-tab-pane label="执行策略" name="policies" lazy>
        <SchedulePolicies />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent } from 'vue'
import { useRoute, useRouter } from 'vue-router'

// 三个页签各自是完整页面，静态导入会让进入任一页签都要下载并编译全部页签的代码，
// 配合上面的 lazy 改为按需加载：只加载当前页签
const MessageChannels = defineAsyncComponent(() => import('@/views/admin/MessageChannels.vue'))
const MessageTemplates = defineAsyncComponent(() => import('@/views/admin/MessageTemplates.vue'))
const SchedulePolicies = defineAsyncComponent(() => import('@/views/SchedulePolicies.vue'))

const route = useRoute()
const router = useRouter()
const activeTab = computed(() => route.meta.tab || 'channels')
const tabMap = { channels: '/config-admin/channels', templates: '/config-admin/templates', policies: '/config-admin/policies' }
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
