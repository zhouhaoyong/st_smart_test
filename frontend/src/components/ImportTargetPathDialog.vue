<template>
  <el-dialog
    v-model="visible"
    title="当前导入接口集层级"
    width="600px"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
  >
    <div class="target-path-dialog">
      <div class="target-path-status">
        <span>当前选择</span>
        <el-tag type="primary" effect="plain">{{ targetCollectionName }}</el-tag>
      </div>
      <div class="target-path-box">
        <div class="target-path-title">完整层级</div>
        <div class="target-path-value">{{ targetCollectionPath }}</div>
      </div>
      <div class="target-path-hint">导入会进入当前接口集；如果层级不正确，请关闭导入弹窗后先在左侧选择正确接口集。</div>
    </div>
    <template #footer>
      <el-button type="primary" @click="visible = false">我知道了</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { formatCollectionPath } from '@/utils/interfaceCollections'

const props = defineProps({
  modelValue: Boolean,
  targetCollection: { type: Object, default: null },
  collectionTree: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const visible = ref(false)
const targetCollectionName = computed(() => props.targetCollection?.name || '-')
const targetCollectionPath = computed(() => formatCollectionPath(props.collectionTree, props.targetCollection))

watch(() => props.modelValue, value => { visible.value = value })
watch(visible, value => emit('update:modelValue', value))
</script>

<style scoped>
.target-path-dialog { display: flex; flex-direction: column; gap: 14px; }
.target-path-status { display: flex; align-items: center; gap: 10px; color: #606266; }
.target-path-box { border: 1px solid #edf1f7; border-radius: 8px; padding: 14px 16px; background: #fbfcff; }
.target-path-title { margin-bottom: 6px; color: #909399; font-size: 12px; }
.target-path-value { color: #303133; font-size: 13px; overflow-wrap: anywhere; word-break: break-word; }
.target-path-hint { color: #909399; font-size: 12px; line-height: 1.7; }
</style>
