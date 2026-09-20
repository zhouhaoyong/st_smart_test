<template>
  <el-dialog
    :model-value="modelValue"
    title="用例详情"
    width="60vw"
    top="8vh"
    append-to-body
    :close-on-click-modal="false"
    class="ai-case-edit-dialog"
    @update:model-value="handleVisible"
    @open="loadFromProp"
  >
    <el-form label-width="88px" class="case-form">
      <el-form-item label="所属接口">
        <span class="ro-text">{{ ifaceName || '-' }}</span>
      </el-form-item>
      <el-form-item label="用例类型">
        <el-tag :type="caseTypeTag(form.case_type)" size="small">{{ caseTypeText(form.case_type) }}</el-tag>
      </el-form-item>
      <el-form-item label="用例名称">
        <el-input v-model="form.name" placeholder="用例名称" maxlength="50" show-word-limit />
      </el-form-item>
      <el-form-item label="用例描述">
        <el-input v-model="form.description" type="textarea" :rows="2" placeholder="用例描述" maxlength="50" show-word-limit />
      </el-form-item>
      <el-form-item label="请求配置">
        <div class="ro-json">
          <div class="ro-json-tip">请求配置由 AI 按所选模式生成（只读展示）；如需调整请对该接口重新生成。</div>
          <pre class="ro-json-pre">{{ paramOverridesText }}</pre>
        </div>
      </el-form-item>
      <el-form-item label="断言">
        <el-input
          v-model="assertionsText"
          type="textarea"
          :rows="5"
          placeholder='断言数组，如 [{"type":"jsonpath","expression":"$.code","operator":"eq","expected":"200"}]'
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleVisible(false)">取消</el-button>
      <el-button type="primary" @click="onSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: Boolean,
  caseData: { type: Object, default: null },
  ifaceName: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'save'])

const form = reactive({ name: '', description: '', case_type: 'main' })
const assertionsText = ref('[]')
const paramOverridesText = ref('{}')

function loadFromProp() {
  const c = props.caseData || {}
  form.name = c.name || ''
  form.description = c.description || ''
  form.case_type = c.case_type || 'main'
  assertionsText.value = safeStringify(c.assertions ?? [])
  paramOverridesText.value = safeStringify(c.param_overrides ?? {})
}

function safeStringify(v) {
  try { return JSON.stringify(v, null, 2) } catch { return '' }
}

function caseTypeTag(t) {
  return { main: 'success', reverse: 'warning', abnormal: 'danger' }[t] || 'info'
}
function caseTypeText(t) {
  return { main: '主流程', reverse: '逆向', abnormal: '异常' }[t] || '主流程'
}

function onSave() {
  let assertions
  try {
    assertions = JSON.parse(assertionsText.value)
  } catch {
    ElMessage.error('断言不是合法 JSON，请修正后再保存')
    return
  }
  if (!Array.isArray(assertions)) {
    ElMessage.error('断言必须是数组')
    return
  }
  if (!form.name.trim()) {
    ElMessage.warning('用例名称不能为空')
    return
  }
  // 只回传可编辑字段，其余字段（param_overrides/priority 等）由父级保留
  emit('save', {
    name: form.name.trim(),
    description: form.description,
    assertions,
  })
  emit('update:modelValue', false)
}

function handleVisible(val) {
  emit('update:modelValue', val)
}
</script>

<style scoped>
.case-form { max-width: 100%; }
.ro-text { color: var(--el-text-color-primary); }
.ro-json { width: 100%; }
.ro-json-tip { font-size: 12px; color: var(--el-text-color-secondary); margin-bottom: 4px; line-height: 1.5; }
.ro-json-pre {
  margin: 0; padding: 8px 10px;
  max-height: 220px; overflow: auto;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-light); border-radius: 6px;
  font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-break: break-all;
}
</style>

<style>
.ai-case-edit-dialog { max-width: 900px; display: flex; flex-direction: column; max-height: 84vh; }
.ai-case-edit-dialog .el-dialog__body { flex: 1; overflow-y: auto; }
</style>
