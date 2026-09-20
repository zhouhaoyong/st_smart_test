<template>
  <div class="param-editor">
    <div class="param-toolbar">
      <span class="param-title">{{ title }}</span>
      <el-button size="small" type="primary" plain :icon="Plus" @click="addRow">{{ addLabel }}</el-button>
    </div>

    <el-table
      v-if="rows.length"
      :data="rows"
      size="small"
      border
      class="param-table"
      :header-cell-style="{ background: '#f7f9fc', color: '#606266', fontWeight: 600 }"
    >
      <el-table-column label="参数名" width="180">
        <template #default="{ $index }">
          <el-input v-model="rows[$index].key" placeholder="参数名" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="参数值" min-width="220">
        <template #default="{ $index }">
          <el-input v-model="rows[$index].value" placeholder="参数值" size="small" />
        </template>
      </el-table-column>
      <el-table-column v-if="showType" label="类型" width="112">
        <template #default="{ $index }">
          <el-select v-model="rows[$index].type" size="small" placeholder="类型" @change="rows[$index].type_source = 'manual'">
            <el-option v-for="option in typeOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column v-if="showRequired" label="必填" width="64" align="center">
        <template #default="{ $index }">
          <el-checkbox v-model="rows[$index].required" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="说明" width="180">
        <template #default="{ $index }">
          <el-input v-model="rows[$index].description" placeholder="说明" size="small" maxlength="50" />
        </template>
      </el-table-column>
      <el-table-column label="" width="48" align="center">
        <template #default="{ $index }">
          <el-tooltip content="删除" placement="top" effect="light">
            <el-button link type="danger" size="small" :icon="Delete" @click="removeRow($index)" />
          </el-tooltip>
        </template>
      </el-table-column>
    </el-table>

    <div v-else class="param-empty">
      <span>{{ emptyText }}</span>
      <el-button link type="primary" :icon="Plus" @click="addRow">{{ addLabel }}</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Plus, Delete } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  title: { type: String, default: '参数' },
  addLabel: { type: String, default: '添加参数' },
  emptyText: { type: String, default: '暂无参数' },
  showRequired: { type: Boolean, default: false },
  showType: { type: Boolean, default: true },
  // 只给真会被消费的六种类型：其余几种既不做取值转换也不做校验，选了等于没选，
  // 反而会被 AI 生成与参数集当成一次真实声明，制造无意义的差异
  typeOptions: {
    type: Array,
    default: () => [
      { value: 'string', label: 'string' },
      { value: 'int', label: 'int' },
      { value: 'float', label: 'float' },
      { value: 'bool', label: 'bool' },
      { value: 'list', label: 'list' },
      { value: 'object', label: 'object' },
    ],
  },
})

const emit = defineEmits(['update:modelValue'])

const rows = computed({
  get: () => props.modelValue || [],
  set: value => emit('update:modelValue', value),
})

function addRow() {
  // 是否必填不预置：勾选框只有勾/不勾两态，替用户落一个「不必填」等于把「不知道」
  // 说成了「确定可不传」，而这个结论会被 AI 生成用例当成事实。留空即表示未声明。
  const row = { key: '', value: '', description: '' }
  // 同理，不展示类型列时不替用户按「手填」落一个 string：那会与接口声明的类型冲突，
  // 也会让参数集把它当成一次人工声明；留空则由后端按取值推断。
  if (props.showType) Object.assign(row, { type: 'string', type_source: 'manual' })
  rows.value = [...rows.value, row]
}

function removeRow(index) {
  rows.value = rows.value.filter((_, i) => i !== index)
}
</script>

<style scoped>
.param-editor {
  border: 1px solid #e8edf3;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}
.param-toolbar {
  height: 42px;
  padding: 0 10px 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fbfcfe;
  border-bottom: 1px solid #edf1f7;
}
.param-title {
  color: #303133;
  font-weight: 600;
  font-size: 13px;
}
.param-table :deep(.el-table__cell) {
  padding: 4px 0;
}
.param-table :deep(.el-input__wrapper) {
  box-shadow: none;
  background: transparent;
}
.param-empty {
  height: 92px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #909399;
  font-size: 13px;
  background: #fafcff;
}
</style>
