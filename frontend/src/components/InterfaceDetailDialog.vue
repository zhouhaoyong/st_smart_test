<template>
  <el-dialog
    :model-value="modelValue"
    :title="props.title"
    width="1100px"
    append-to-body
    destroy-on-close
    class="iface-dialog"
    @update:model-value="handleVisible"
  >
    <div v-if="currentInterface">
      <el-alert
        v-if="props.showPendingNotice"
        type="info"
        title="当前内容尚未保存"
        description="当前为 AI 生成预览，尚未入库；完成导入保存后才会生成并展示 ID、创建人、创建时间等信息。"
        :closable="false"
        show-icon
        class="pending-metadata-notice"
      />
      <el-form :model="currentInterface" label-width="100px" :disabled="props.readonly">
        <el-tabs v-model="detailSection">
          <el-tab-pane label="配置" name="config">
            <el-row :gutter="16">
          <el-col :span="14">
            <el-form-item label="接口名称">
              <el-input v-model="currentInterface.name" placeholder="如：获取用户信息" maxlength="50" show-word-limit />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="请求方法">
              <el-select v-model="currentInterface.method" style="width: 100%">
                <el-option label="GET" value="GET" />
                <el-option label="POST" value="POST" />
                <el-option label="PUT" value="PUT" />
                <el-option label="DELETE" value="DELETE" />
                <el-option label="PATCH" value="PATCH" />
                <el-option label="HEAD" value="HEAD" />
                <el-option label="OPTIONS" value="OPTIONS" />
              </el-select>
            </el-form-item>
          </el-col>
            </el-row>

            <el-form-item label="URL">
              <el-input v-model="currentInterface.url" placeholder="/api/v1/users" />
            </el-form-item>

            <el-form-item label="描述">
              <el-input
                v-model="currentInterface.description"
                type="textarea"
                :rows="2"
                maxlength="50"
                show-word-limit
                class="interface-description-input"
              />
            </el-form-item>

            <!-- 请求体的字段类型不展示：发请求时用不到，只在导入判重的结构指纹和 AI 生成里用，
                 数据照常保存和参与比对，界面上不再占位 -->
            <RequestConfigTabs
              v-model:active-tab="detailTab"
              :model="currentInterface"
              :body-rows="8"
              body-placeholder='{"key": "value"}'
            />
          </el-tab-pane>
          <el-tab-pane v-if="props.showInfo && hasPersistedMetadata" label="信息" name="info">
            <RecordMetadataTable :record="currentInterface" />
          </el-tab-pane>
        </el-tabs>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="handleVisible(false)">关闭</el-button>
      <el-button v-if="props.showSave" type="primary" :loading="props.saving" @click="saveChanges">保存修改</el-button>
      <el-button v-if="props.showDebug" type="success" @click="$emit('debug-interface', currentInterface)">调试</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import RecordMetadataTable from '@/components/RecordMetadataTable.vue'
import RequestConfigTabs from '@/components/RequestConfigTabs.vue'

const props = defineProps({
  modelValue: Boolean,
  interfaceData: { type: Object, default: null },
  title: { type: String, default: '接口详情' },
  readonly: { type: Boolean, default: false },
  showInfo: { type: Boolean, default: true },
  showPendingNotice: { type: Boolean, default: false },
  showDebug: { type: Boolean, default: true },
  showSave: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'save', 'debug-interface'])

const draftInterface = ref(null)
const currentInterface = computed(() => draftInterface.value)
const hasPersistedMetadata = computed(() => Boolean(currentInterface.value?.id))
const detailSection = ref('config')
const detailTab = ref('query')
function normalizeParamList(value) {
  return (Array.isArray(value) ? value : []).map(item => {
    const row = {
      ...item,
      value: item.value ?? '',
      type: item.type || 'string',
      type_source: item.type_source || 'default',
    }
    // 没声明是否必填就保持没声明：打开一次详情就把「不知道」固化成「确定可不传」，
    // 之后 AI 生成用例会把这个假结论当事实用
    if (row.required === undefined || row.required === null) delete row.required
    else row.required = Boolean(row.required)
    return row
  })
}

function prepareInterfaceData() {
  const target = props.interfaceData
  if (!target) {
    draftInterface.value = null
    return
  }
  const draft = JSON.parse(JSON.stringify(target))
  draft.query_params = normalizeParamList(draft.query_params)
  draft.path_params = normalizeParamList(draft.path_params)
  draft.headers = normalizeParamList(draft.headers)
  if (!draft.body_schema_types || typeof draft.body_schema_types !== 'object') draft.body_schema_types = {}
  draftInterface.value = draft
  detailSection.value = 'config'
  detailTab.value = draft.method === 'GET' || (!draft.body_type && !draft.body_content) ? 'query' : 'body'
}

function saveChanges() {
  if (!currentInterface.value || props.saving) return
  emit('save', JSON.parse(JSON.stringify(currentInterface.value)))
}

watch(() => props.modelValue, open => {
  if (open) prepareInterfaceData()
})
watch(() => props.interfaceData, value => {
  if (props.modelValue && value) prepareInterfaceData()
})
watch([() => props.modelValue, hasPersistedMetadata], ([open, hasInfo]) => {
  if (open && !hasInfo) detailSection.value = 'config'
})

function handleVisible(value) {
  emit('update:modelValue', value)
}
</script>

<style scoped>
.code-editor :deep(.el-textarea__inner) {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
}

.pending-metadata-notice {
  margin-bottom: 16px;
}

.interface-description-input :deep(.el-textarea__inner) {
  padding-right: 58px;
  resize: none;
}
</style>
