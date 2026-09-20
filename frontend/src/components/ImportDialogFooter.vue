<template>
  <div class="import-dialog-footer">
    <div class="footer-actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.import-dialog-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  width: 100%;
}
.footer-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}
.footer-actions :deep(.el-button) {
  margin: 0 !important;
  white-space: nowrap;
}
@media (max-width: 900px) {
  .import-dialog-footer { align-items: stretch; }
  .footer-actions { width: 100%; }
}
</style>
