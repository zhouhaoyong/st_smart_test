<template>
  <section class="requirement-tabs-page">
    <WorkbenchPageHeader title="需求管理">
      <template #actions><el-button @click="statusGuideVisible = true">需求状态说明</el-button></template>
    </WorkbenchPageHeader>
    <WorkbenchContentCard>
      <el-tabs v-model="activeTab" class="requirement-tabs" @tab-change="changeTab">
        <el-tab-pane label="原始需求" name="original">
          <RequirementManagementPage v-if="activeTab === 'original'" />
        </el-tab-pane>
        <el-tab-pane label="AI补全需求" name="completed">
          <RequirementManagementPage v-if="activeTab === 'completed'" requirement-type="completed" />
        </el-tab-pane>
        <el-tab-pane label="AI合并需求" name="merged">
          <WorkbenchMergedRequirementPage v-if="activeTab === 'merged'" />
        </el-tab-pane>
      </el-tabs>
    </WorkbenchContentCard>
    <el-dialog v-model="statusGuideVisible" title="需求状态说明" width="520px" append-to-body>
      <div class="status-guide">
        <section><h4>待确认</h4><p>需求可继续编辑或进行 AI 补全，暂不能参与合并或作为 AI 生成测试用例的来源。</p></section>
        <section><h4>已确认</h4><p>需求可参与合并，并可作为 AI 生成测试用例的来源。</p></section>
        <section><h4>确认规则</h4><p>原始需求正文非空即可确认，AI 补全是可选能力。已确认需求的「需求内容」（原始需求正文或补全 Markdown 正文）发生变更时，会自动回退为待确认；仅修改标题不影响确认状态。</p></section>
      </div>
    </el-dialog>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RequirementManagementPage from '@/views/test-workbench/components/RequirementManagementPage.vue'
import WorkbenchMergedRequirementPage from '@/views/test-workbench/pages/WorkbenchMergedRequirementPage.vue'
import WorkbenchContentCard from '@/views/test-workbench/components/WorkbenchContentCard.vue'
import WorkbenchPageHeader from '@/views/test-workbench/components/WorkbenchPageHeader.vue'

const route = useRoute()
const router = useRouter()
const statusGuideVisible = ref(false)
const activeTab = ref(route.name === 'TestWorkbenchMergedRequirements' ? 'merged' : route.query.requirement_type === 'completed' ? 'completed' : 'original')

const changeTab = (tab) => {
  const query = { ...route.query }
  if (tab === 'completed') query.requirement_type = 'completed'
  else delete query.requirement_type
  router.push({
    name: tab === 'merged' ? 'TestWorkbenchMergedRequirements' : 'TestWorkbenchRequirements',
    params: { id: route.params.id },
    query,
  })
}

watch(() => [route.name, route.query.requirement_type], ([name, requirementType]) => {
  activeTab.value = name === 'TestWorkbenchMergedRequirements' ? 'merged' : requirementType === 'completed' ? 'completed' : 'original'
})
</script>

<style scoped>
.requirement-tabs-page { height: 100%; min-height: 0; display: flex; flex-direction: column; gap: 16px; }
.status-guide { color: #606266; font-size: 14px; line-height: 1.7; }
.status-guide section + section { margin-top: 16px; }
.status-guide h4 { margin: 0 0 4px; color: #303133; font-size: 15px; }
.status-guide p { margin: 0; }
.requirement-tabs { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.requirement-tabs :deep(.el-tabs__header) {
  margin: 0 0 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}
.requirement-tabs :deep(.el-tabs__nav-wrap)::after { display: none; }
.requirement-tabs :deep(.el-tabs__item) {
  height: 34px;
  line-height: 34px;
  font-size: 14px;
  font-weight: 500;
  color: #606266;
}
.requirement-tabs :deep(.el-tabs__item.is-active) { color: #409eff; font-weight: 600; }
.requirement-tabs :deep(.el-tabs__content),
.requirement-tabs :deep(.el-tab-pane) { flex: 1; min-height: 0; height: 100%; }
</style>
