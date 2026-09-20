<template>
  <el-dialog
    v-model="visible"
    width="min(1000px, calc(100vw - 48px))"
    append-to-body
    :show-close="false"
    :close-on-click-modal="false"
    :class="['iface-dialog', 'smart-dialog', { maximized: interfaceMaxed }]"
    @closed="handleClosed"
  >
    <template #header>
      <SmartDialogHeader
        :title="props.title"
        :maximized="interfaceMaxed"
        @toggle-maximize="interfaceMaxed = !interfaceMaxed"
        @close="visible = false"
      />
    </template>

    <el-form
      v-if="props.model"
      ref="interfaceFormRef"
      :model="props.model"
      :rules="props.rules"
      label-width="112px"
      :validate-on-rule-change="false"
    >
      <el-tabs v-model="interfaceDetailTab">
        <el-tab-pane label="配置" name="config">
          <InterfaceBasicFields :form="props.model" :methods="props.methods">
            <template #status>
              <el-form-item label="接口状态" prop="workflow_status">
                <el-select v-model="props.model.workflow_status" :disabled="!props.model.id" style="width:100%">
                  <el-option label="待处理" value="pending" />
                  <el-option label="已处理" value="done" />
                </el-select>
              </el-form-item>
            </template>
            <template #collection>
              <el-form-item label="所属接口集" prop="collection_id" required class="nowrap-form-label">
                <CollectionSingleSelect
                  ref="interfaceCollectionSelectRef"
                  v-model="props.model.collection_id"
                  :collection-tree="props.collectionTree"
                  display-mode="cascader"
                  :show-all-levels="false"
                  clearable
                  placeholder="请选择接口集"
                  class="interface-collection-select"
                  style="width:100%"
                />
              </el-form-item>
            </template>
            <template #service>
              <el-form-item label="服务标识" class="nowrap-form-label">
                <el-select v-model="props.model.service_key" placeholder="不使用服务标识" clearable allow-create filterable style="width:100%">
                  <el-option v-for="service in props.environmentServices" :key="service.key" :label="serviceOptionLabel(service)" :value="service.key" />
                </el-select>
              </el-form-item>
            </template>
            <template #description>
              <el-form-item label="描述" class="nowrap-form-label">
                <el-input
                  v-model="props.model.description"
                  type="textarea"
                  :rows="1"
                  maxlength="50"
                  show-word-limit
                  class="interface-description-input"
                />
              </el-form-item>
            </template>
            <template #pending-reason>
              <el-form-item label="待处理原因" class="nowrap-form-label">
                <span class="interface-pending-reason-value" :title="interfacePendingReasonLabel">
                  {{ interfacePendingReasonLabel }}
                </span>
              </el-form-item>
            </template>
          </InterfaceBasicFields>

          <InterfaceRequestConfig
            ref="interfaceRequestConfigRef"
            v-model:active-tab="requestTab"
            :model="props.model"
          />
        </el-tab-pane>
        <el-tab-pane v-if="props.showInfo && props.model.id" label="信息" name="info">
          <RecordMetadataTable :record="props.model" />
        </el-tab-pane>
      </el-tabs>
    </el-form>

    <template #footer>
      <div class="interface-editor-footer">
        <div class="interface-editor-footer-actions">
          <el-button v-if="props.showDebug" type="success" @click="handleDebug" :disabled="!props.model?.url">调试</el-button>
          <el-button v-if="props.showCaseManagement && props.model?.id" type="warning" plain @click="emit('manage-cases', props.model)">用例管理</el-button>
        </div>
        <div class="interface-editor-footer-actions">
          <el-button @click="visible = false">取消</el-button>
          <el-button type="primary" @click="handleSave" :loading="props.saving">保存</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import InterfaceBasicFields from '@/components/InterfaceBasicFields.vue'
import InterfaceRequestConfig from '@/components/InterfaceRequestConfig.vue'
import RecordMetadataTable from '@/components/RecordMetadataTable.vue'
import SmartDialogHeader from '@/components/SmartDialogHeader.vue'
import CollectionSingleSelect from '@/components/CollectionSingleSelect.vue'
import { formatServiceOptionLabel } from '@/utils/serviceEnvironment'

defineOptions({ name: 'InterfaceEditDialog' })

const props = defineProps({
  modelValue: Boolean,
  model: { type: Object, default: () => ({}) },
  title: { type: String, default: '编辑接口' },
  collectionTree: { type: Array, default: () => [] },
  environmentServices: { type: Array, default: () => [] },
  methods: { type: Array, default: () => ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'] },
  rules: {
    type: Object,
    default: () => ({
      name: [{ required: true, message: '请输入接口名称', trigger: 'submit' }],
      method: [{ required: true, message: '请选择请求方法', trigger: 'submit' }],
      url: [{ required: true, message: '请输入URL', trigger: 'submit' }],
      collection_id: [{ required: true, message: '请选择所属接口集', trigger: 'submit' }],
    }),
  },
  saving: Boolean,
  showInfo: { type: Boolean, default: true },
  showDebug: { type: Boolean, default: true },
  showCaseManagement: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'save', 'debug-interface', 'manage-cases'])

const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})
const interfaceFormRef = ref(null)
const interfaceCollectionSelectRef = ref(null)
const interfaceRequestConfigRef = ref(null)
const interfaceMaxed = ref(false)
const interfaceDetailTab = ref('config')
const requestTab = ref('query')
const serviceOptionLabel = formatServiceOptionLabel

const interfacePendingReasonLabel = computed(() => {
  if (props.model?.workflow_status !== 'pending') return '-'
  return props.model?.pending_reason_label || (props.model?.id ? '存量数据待确认' : '-')
})

const defaultRequestTab = method => {
  if (String(method || '').toUpperCase() === 'GET') return 'query'
  return props.model?.body_type || props.model?.body_content ? 'body' : 'query'
}

const readTags = () => {
  if (typeof props.model?.tags_text === 'string') {
    return props.model.tags_text.split(',').map(tag => tag.trim()).filter(Boolean)
  }
  return Array.isArray(props.model?.tags) ? [...props.model.tags] : []
}

const buildInterfaceData = () => ({
  id: props.model?.id || null,
  name: props.model?.name,
  method: props.model?.method,
  url: props.model?.url,
  ...(props.model?.id ? { workflow_status: props.model.workflow_status } : {}),
  service_key: props.model?.service_key || null,
  description: props.model?.description || null,
  tags: readTags(),
  collection_id: props.model?.collection_id || null,
  query_params: props.model?.query_params || [],
  path_params: props.model?.path_params || [],
  headers: props.model?.headers || [],
  body_type: props.model?.body_type || null,
  body_content: props.model?.body_content || null,
  body_schema_types: props.model?.body_schema_types || {},
  pre_script: props.model?.pre_script || null,
  post_script: props.model?.post_script || null,
})

const syncHeaderJsonMode = () => interfaceRequestConfigRef.value?.syncHeaderJsonMode() !== false

const handleSave = async () => {
  try {
    await interfaceFormRef.value?.validate()
  } catch {
    return
  }
  if (!syncHeaderJsonMode()) return
  emit('save', buildInterfaceData())
}

const handleDebug = () => {
  if (!syncHeaderJsonMode()) return
  emit('debug-interface', buildInterfaceData())
}

const prepareEditor = () => {
  interfaceDetailTab.value = 'config'
  requestTab.value = defaultRequestTab(props.model?.method)
  nextTick(() => interfaceRequestConfigRef.value?.resetEditors())
}

const handleClosed = () => {
  interfaceMaxed.value = false
  interfaceCollectionSelectRef.value?.close()
}

watch(() => props.modelValue, open => {
  if (open) prepareEditor()
})
watch(() => props.model, value => {
  if (props.modelValue && value) prepareEditor()
})
</script>

<style scoped>
.interface-editor-footer {
  display: flex;
  justify-content: space-between;
  width: 100%;
}
.interface-editor-footer-actions {
  display: flex;
  gap: 8px;
}
.interface-pending-reason-value {
  display: block;
  overflow: hidden;
  color: #909399;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.iface-dialog :deep(.el-dialog) {
  display: flex;
  flex-direction: column;
  max-height: min(92vh, 800px);
  min-height: 60vh;
  border-radius: 16px;
}
.iface-dialog :deep(.el-dialog__header) {
  padding: 18px 20px 14px 28px;
  border-bottom: 1px solid #edf1f7;
  background: linear-gradient(135deg, #f8fbff 0%, #ffffff 65%);
}
.iface-dialog :deep(.el-dialog__body) {
  flex: 1;
  overflow-y: auto;
  padding: 22px 30px;
  font-size: 15px;
  background: #fbfcff;
}
.iface-dialog :deep(.el-form-item__label) { font-size: 15px; }
.iface-dialog :deep(.nowrap-form-label .el-form-item__label) {
  flex: 0 0 112px;
  white-space: nowrap;
  word-break: keep-all;
}
.iface-dialog :deep(.el-input__inner) { font-size: 15px; }
.iface-dialog :deep(.el-tabs__item) { font-size: 14px; }
.iface-dialog :deep(.collection-single-select-wrapper),
.iface-dialog :deep(.collection-single-select__cascader),
.iface-dialog :deep(.collection-single-select__cascader .el-input) {
  display: block;
  width: 100% !important;
  min-width: 0;
}
.iface-dialog :deep(.interface-collection-select .el-cascader) { width: 100% !important; }
.interface-description-input :deep(.el-textarea__inner) { padding-right: 58px; resize: none; }
</style>

<style>
.el-dialog.iface-dialog.smart-dialog.maximized {
  width: 100vw !important;
  max-width: 100vw !important;
  height: 100vh !important;
  max-height: 100vh !important;
  margin: 0 !important;
  border-radius: 0 !important;
  display: flex !important;
  flex-direction: column !important;
}
.el-dialog.iface-dialog.smart-dialog.maximized .el-dialog__body {
  flex: 1 !important;
  max-height: none !important;
  min-height: 0 !important;
  overflow-y: auto !important;
}
</style>
