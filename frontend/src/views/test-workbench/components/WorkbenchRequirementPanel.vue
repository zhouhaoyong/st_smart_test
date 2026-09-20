<template>
  <section class="asset-block">
    <div class="block-head">
      <div>
        <h3>最终需求</h3>
        <p>保存确认后的原始需求和结构化结果。</p>
      </div>
      <div class="block-actions">
        <el-button :disabled="!canPreview" @click="$emit('preview')">预览结构化结果</el-button>
        <el-button type="primary" :loading="saving" :disabled="!canSave" @click="$emit('save')">保存需求</el-button>
      </div>
    </div>

    <el-input :model-value="title" placeholder="需求标题" @update:model-value="$emit('update:title', $event)" />
    <el-input :model-value="content" class="mt-10" type="textarea" :rows="8" resize="none" placeholder="最终确认需求内容" @update:model-value="$emit('update:content', $event)" />
    <el-input :model-value="structureText" class="mt-10 json-editor" type="textarea" :rows="12" resize="none" placeholder="结构化需求 JSON" @update:model-value="$emit('update:structureText', $event)" />

    <el-table :data="requirements" class="mt-10 requirements-table">
      <el-table-column prop="title" label="需求" min-width="160" show-overflow-tooltip />
      <el-table-column prop="updated_at" label="更新时间" width="210" show-overflow-tooltip />
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="$emit('select', row)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  content: { type: String, default: '' },
  structureText: { type: String, default: '' },
  requirements: { type: Array, default: () => [] },
  canPreview: { type: Boolean, default: false },
  canSave: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
})

defineEmits(['update:title', 'update:content', 'update:structureText', 'preview', 'save', 'select'])
</script>

<style scoped>
.asset-block {
  min-height: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.block-head h3 { margin: 0; color: #303133; font-size: 16px; font-weight: 600; }
.block-head p { margin: 4px 0 0; color: #909399; font-size: 12px; }
.block-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.mt-10 { margin-top: 10px; }
.json-editor { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
.requirements-table { flex: 1; min-height: 180px; }
.requirements-table :deep(.el-table__header .cell), .requirements-table :deep(.el-table__body .cell) { white-space: nowrap; }
.requirements-table :deep(.el-table__body .cell) { overflow: hidden; text-overflow: ellipsis; }
</style>
