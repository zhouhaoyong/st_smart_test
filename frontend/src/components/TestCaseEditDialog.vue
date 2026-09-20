<template>
  <el-dialog
    v-model="visible"
    width="min(1000px, calc(100vw - 48px))"
    append-to-body
    :show-close="false"
    :close-on-click-modal="false"
    :class="['case-edit-dialog', 'smart-dialog', { maximized: editMaxed }]"
    @closed="editMaxed = false"
  >
    <template #header>
      <SmartDialogHeader
        :title="title"
        :maximized="editMaxed"
        @toggle-maximize="editMaxed = !editMaxed"
        @close="visible = false"
      />
    </template>

    <el-alert
      v-if="props.showPendingNotice"
      type="info"
      title="当前内容尚未保存"
      description="当前为 AI 生成预览，尚未入库；完成导入保存后才会生成并展示 ID、创建人、创建时间等信息。"
      :closable="false"
      show-icon
      class="pending-metadata-notice"
    />
    <el-form :model="model" label-width="100px" :disabled="props.readonly">
      <el-tabs v-model="detailSection">
        <el-tab-pane label="配置" name="config">
          <el-row :gutter="16">
            <el-col :span="14">
              <el-form-item label="用例名称" required>
                <el-input v-model="model.name" placeholder="用例名称" maxlength="50" show-word-limit />
              </el-form-item>
            </el-col>
            <el-col :span="10">
              <el-form-item label="请求方法">
                <el-select v-model="model.method" style="width: 100%">
                  <el-option v-for="method in methods" :key="method" :label="method" :value="method" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="14">
              <el-form-item label="URL">
                <el-input v-model="model.url" placeholder="/api/v1/users" />
              </el-form-item>
            </el-col>
            <el-col :span="10">
              <el-form-item label="优先级">
                <el-select v-model="model.priority" style="width: 100%">
                  <el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="14">
              <el-form-item label="描述">
                <el-input v-model="model.description" type="textarea" :rows="1" maxlength="50" show-word-limit class="case-description-input" />
              </el-form-item>
            </el-col>
            <el-col :span="10">
              <el-form-item label="确认状态">
                <el-select v-model="model.confirm_status" style="width: 100%">
                  <el-option label="待确认" value="pending" />
                  <el-option label="已确认" value="confirmed" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <!--
            参数类型与是否必填都属于接口契约，只在接口定义处声明；用例只提供取值，
            避免用例改出与接口不一致的声明。用例里验证必填，靠填值、留空、删掉整行三种取值即可。
          -->
          <RequestConfigTabs
            v-model:active-tab="activeTab"
            :model="model"
            :response-sample-loader="props.responseSampleLoader"
            :param-show-type="false"
            :param-show-required="false"
            show-assertions
          />
        </el-tab-pane>
        <el-tab-pane v-if="props.showInfo && hasPersistedMetadata" label="信息" name="info">
          <RecordMetadataTable :record="model" />
        </el-tab-pane>
      </el-tabs>
    </el-form>

    <template #footer>
      <div v-if="props.readonly" class="case-edit-dialog__readonly-footer">
        <el-button @click="visible = false">关闭</el-button>
      </div>
      <div v-else class="case-edit-dialog__footer">
        <el-button v-if="props.showRun" type="success" :loading="runLoading" :disabled="!model.url" @click="emit('run')">运行</el-button>
        <div>
          <el-button @click="visible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="emit('save')">保存</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import RequestConfigTabs from '@/components/RequestConfigTabs.vue'
import RecordMetadataTable from '@/components/RecordMetadataTable.vue'
import SmartDialogHeader from '@/components/SmartDialogHeader.vue'

defineOptions({ name: 'TestCaseEditDialog' })

const props = defineProps({
  modelValue: Boolean,
  model: { type: Object, required: true },
  title: { type: String, default: '编辑用例' },
  showInfo: { type: Boolean, default: true },
  showPendingNotice: { type: Boolean, default: false },
  readonly: { type: Boolean, default: false },
  showRun: { type: Boolean, default: true },
  activeTab: { type: String, default: 'query' },
  saving: Boolean,
  runLoading: Boolean,
  // 断言表达式的字段选取需要一份真实响应，由各调用方按自己的运行方式提供
  responseSampleLoader: { type: Function, default: null },
})
const emit = defineEmits(['update:modelValue', 'update:activeTab', 'save', 'run'])

const editMaxed = ref(false)
const detailSection = ref('config')
const hasPersistedMetadata = computed(() => Boolean(props.model?.id))
const methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})
const activeTab = computed({
  get: () => props.activeTab,
  set: value => emit('update:activeTab', value),
})

watch(() => props.modelValue, visibleValue => {
  if (visibleValue) detailSection.value = 'config'
})
watch([() => props.modelValue, hasPersistedMetadata], ([open, hasInfo]) => {
  if (open && !hasInfo) detailSection.value = 'config'
})
</script>

<style scoped>
.case-edit-dialog__footer { display: flex; justify-content: space-between; width: 100%; }
.case-edit-dialog__readonly-footer { display: flex; justify-content: flex-end; width: 100%; }
.case-edit-dialog :deep(.el-tabs__content) { max-height: 55vh; overflow-y: auto; }
.pending-metadata-notice { margin-bottom: 16px; }
.case-description-input :deep(.el-textarea__inner) { padding-right: 58px; resize: none; }
</style>

<style>
.el-dialog.case-edit-dialog.smart-dialog.maximized {
  width: 100vw !important;
  max-width: 100vw !important;
  height: 100vh !important;
  max-height: 100vh !important;
  margin: 0 !important;
  border-radius: 0 !important;
  display: flex !important;
  flex-direction: column !important;
}
.el-dialog.case-edit-dialog.smart-dialog.maximized .el-dialog__body {
  flex: 1 !important;
  max-height: none !important;
  min-height: 0 !important;
  overflow-y: auto !important;
}
</style>
