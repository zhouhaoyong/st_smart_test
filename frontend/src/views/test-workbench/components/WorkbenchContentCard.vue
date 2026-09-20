<template>
  <section class="workbench-content-card"><slot /></section>
</template>

<style scoped>
.workbench-content-card {
  position: relative;
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  padding: 16px;
  overflow: hidden;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  box-sizing: border-box;
}
.workbench-content-card :deep(.el-table th.el-table__cell) { white-space: nowrap; }
</style>
