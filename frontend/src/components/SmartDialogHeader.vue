<template>
  <div class="smart-dialog-header">
    <span class="smart-dialog-title">{{ title }}</span>
    <div class="smart-dialog-actions">
      <el-button
        link
        class="smart-dialog-icon-btn"
        :title="maximized ? '还原' : '最大化'"
        @click.stop="$emit('toggle-maximize')"
      >
        <el-icon :size="17"><Operation v-if="maximized" /><FullScreen v-else /></el-icon>
      </el-button>
      <el-button link class="smart-dialog-icon-btn" title="关闭" @click.stop="$emit('close')">
        <el-icon :size="17"><Close /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { Close, FullScreen, Operation } from '@element-plus/icons-vue'

defineProps({
  title: { type: String, default: '' },
  maximized: { type: Boolean, default: false },
})

defineEmits(['toggle-maximize', 'close'])
</script>

<style scoped>
.smart-dialog-header { display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 32px; }
.smart-dialog-title { color: #1f2d3d; font-size: 18px; font-weight: 700; letter-spacing: .2px; }
.smart-dialog-actions { display: inline-flex; align-items: center; gap: 4px; height: 32px; }
.smart-dialog-icon-btn { width: 32px; height: 32px; min-height: 32px; padding: 0; margin: 0 !important; display: inline-flex; align-items: center; justify-content: center; color: #7b8794; border-radius: 8px; }
.smart-dialog-icon-btn:hover { color: var(--nexus-primary, #1677ff); background: #eef6ff; }
</style>
