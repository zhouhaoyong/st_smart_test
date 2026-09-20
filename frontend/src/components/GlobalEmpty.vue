<template>
  <div class="global-empty" :class="{ 'global-empty--text-only': !showImage }">
    <el-empty :description="text" :image-size="imageSize">
      <el-button v-if="actionText" class="empty-action" type="primary" @click="emit('action')">{{ actionText }}</el-button>
      <slot />
    </el-empty>
  </div>
</template>

<script setup>
const props = defineProps({
  text: { type: String, default: '暂无数据' },
  imageSize: { type: Number, default: 72 },
  showImage: { type: Boolean, default: true },
  actionText: { type: String, default: '' },
})

const emit = defineEmits(['action'])
</script>

<style scoped>
.global-empty {
  width: 100%;
  user-select: none;
  text-align: center;
}
.global-empty :deep(.el-empty) { min-height: 300px; }
.global-empty :deep(.el-empty__description p) { color: #909399; font-size: 15px; }
.global-empty--text-only :deep(.el-empty__image) { display: none; }
.global-empty--text-only :deep(.el-empty__description) { margin-top: 0; }
.empty-action { margin-top: 4px; }
</style>
