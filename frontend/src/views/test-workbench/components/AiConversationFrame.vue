<template>
  <section class="ai-conversation-frame">
    <slot />
  </section>
</template>

<style scoped>
.ai-conversation-frame {
  position: relative;
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
  box-sizing: border-box;
}
</style>
