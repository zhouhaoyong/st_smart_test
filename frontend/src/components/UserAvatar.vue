<template>
  <el-avatar
    :size="size"
    :shape="shape"
    fit="cover"
    :src="src || undefined"
    :alt="altText"
    class="user-avatar"
    :style="avatarStyle"
  >
    <span class="avatar-fallback">{{ avatarText }}</span>
  </el-avatar>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  src: { type: String, default: '' },
  name: { type: String, default: '' },
  userId: { type: [Number, String], default: 0 },
  size: { type: [Number, String], default: 32 },
  shape: { type: String, default: 'circle' },
  alt: { type: String, default: '' },
})

const avatarBgColors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#f5222d', '#faad14']

const avatarText = computed(() => {
  const value = String(props.name || '用').trim()
  return value ? value.charAt(0).toUpperCase() : '用'
})

const avatarBgColor = computed(() => {
  const id = Number(props.userId) || 0
  return avatarBgColors[id % avatarBgColors.length]
})

const fallbackFontSize = computed(() => {
  const avatarSize = Number.parseInt(String(props.size), 10)
  return Number.isFinite(avatarSize) ? `${Math.max(Math.round(avatarSize * 0.42), 10)}px` : '14px'
})

const avatarStyle = computed(() => ({
  background: avatarBgColor.value,
  color: '#fff',
  '--user-avatar-fallback-font-size': fallbackFontSize.value,
}))

const altText = computed(() => props.alt || `${props.name || '用户'}头像`)
</script>

<style scoped>
.user-avatar {
  flex-shrink: 0;
  font-weight: 700;
  overflow: hidden;
}

.avatar-fallback {
  font-size: var(--user-avatar-fallback-font-size);
  line-height: 1;
}
</style>
