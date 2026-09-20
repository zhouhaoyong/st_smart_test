<template>
  <section class="workbench-list-section">
    <WorkbenchPageHeader title="系统管理" />
    <WorkbenchContentCard><WorkbenchAssetListPage asset-type="system" /></WorkbenchContentCard>
  </section>
</template>

<script setup>
import WorkbenchAssetListPage from '@/views/test-workbench/components/WorkbenchAssetListPage.vue'
import WorkbenchContentCard from '@/views/test-workbench/components/WorkbenchContentCard.vue'
import WorkbenchPageHeader from '@/views/test-workbench/components/WorkbenchPageHeader.vue'
</script>

<style scoped>
.workbench-list-section { height: 100%; min-height: 0; display: flex; flex-direction: column; gap: 16px; }
</style>
