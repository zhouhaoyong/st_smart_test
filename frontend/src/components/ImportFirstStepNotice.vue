<template>
  <div class="import-first-step-notice">
    <div class="import-first-step-notice__base">
      新接口放入所选接口集，文档模块作为下级目录；已有接口保持原位置。服务标识可在下一步批量调整，运行时按当前环境解析路径和认证。
    </div>
    <div v-if="serviceUnavailableTip" class="import-first-step-notice__service">
      <span>{{ serviceUnavailableTip }}</span>
      <router-link
        v-if="projectId"
        :to="`/project/${projectId}/environments`"
        target="_blank"
        class="import-first-step-notice__link"
      >去环境管理配置</router-link>
    </div>
  </div>
</template>

<script setup>
defineProps({
  projectId: { type: [Number, String], default: null },
  serviceUnavailableTip: { type: String, default: '' },
})
</script>

<style scoped>
.import-first-step-notice {
  margin-top: -8px;
  margin-bottom: 18px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 18px;
}

.import-first-step-notice__base,
.import-first-step-notice__service {
  display: block;
}

.import-first-step-notice__service {
  margin-top: 4px;
  color: var(--el-color-warning-dark-2);
}

.import-first-step-notice__link {
  margin-left: 6px;
  color: var(--el-color-primary);
}
</style>
