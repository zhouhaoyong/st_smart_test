<template>
  <!--
    有页签的管理页统一布局壳：
    自上而下为「页签 → 搜索工具栏 → 列表 → 分页」的三段式骨架。
    页面把各自的 page-header / model-tabs-row / list-toolbar / scroll-area / pagination-area
    作为默认插槽内容传入；具体的竖排、工具栏卡片化等视觉统一由管理中心全局样式
    （layout/index.vue 中 .main.is-admin-module .admin-tabs-shell 相关规则）负责，
    以便所有带页签的管理页复用同一套间距与分段样式。
  -->
  <div class="page-wrap admin-tabs-shell">
    <slot />
  </div>
</template>

<script setup>
// 纯布局壳组件，无逻辑。
</script>

<style scoped>
.admin-tabs-shell {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
