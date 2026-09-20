<template>
  <el-dialog v-model="visibleProxy" :title="title" width="520px" destroy-on-close :close-on-click-modal="false" @closed="$emit('closed')">
    <el-form ref="formRef" :model="formData" :rules="rules" label-width="90px">
      <el-form-item label="项目名称" prop="name">
        <el-input v-model="formData.name" placeholder="项目名称（20字以内）" size="large" maxlength="20" show-word-limit />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="formData.description" type="textarea" :rows="3" placeholder="项目描述（可选）" maxlength="200" show-word-limit />
      </el-form-item>
      <el-form-item label="标签">
        <div class="tag-row">
          <el-tag v-for="(tag, index) in formData.tags" :key="tag + index" closable size="default" effect="dark" :style="{ background: tagColors[index % tagColors.length], border: 'none' }" @close="formData.tags.splice(index, 1)">{{ tag }}</el-tag>
          <el-input v-if="formData.tags.length < 4" v-model="tagInput" size="small" class="tag-input" maxlength="5" @keyup.enter="addTag" />
        </div>
        <span class="form-tip">最多4个标签，每个不超过5个字，回车添加</span>
      </el-form-item>
      <el-form-item label="主题色">
        <div class="color-row">
          <div
            v-for="color in presetColors"
            :key="color"
            class="color-swatch"
            :class="{ active: formData.color === color }"
            :style="{ background: color }"
            @click="formData.color = color"
          />
          <el-color-picker v-model="formData.color" size="small" :predefine="presetColors" />
          <el-button v-if="formData.color" size="small" :icon="Close" circle @click="formData.color = ''" />
        </div>
        <span class="form-tip">{{ formData.color ? '已选择主题色' : '自定义项目卡片背景色，点击上方色块选择' }}</span>
      </el-form-item>
      <el-form-item label="公开访问">
        <div class="public-access-row">
          <el-switch v-model="formData.is_public" size="large" />
          <span class="form-tip">开启后其他人可只读访问</span>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visibleProxy = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">{{ submitText }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '新建项目' },
  submitText: { type: String, default: '创建' },
  loading: { type: Boolean, default: false },
  formData: { type: Object, required: true },
})

const emit = defineEmits(['update:modelValue', 'submit', 'closed'])

const formRef = ref(null)
const tagInput = ref('')
const tagColors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#f5222d', '#faad14']
const presetColors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2', '#f5222d', '#faad14', '#fa541c', '#2f54eb', '#a0d911', '#595959']
const rules = { name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }] }

const visibleProxy = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const addTag = () => {
  const val = tagInput.value.trim()
  if (!val) return
  if (val.length > 5) { ElMessage.warning('标签不能超过5个字'); tagInput.value = ''; return }
  if (props.formData.tags.includes(val)) { ElMessage.warning('标签已存在'); tagInput.value = ''; return }
  if (props.formData.tags.length >= 4) { ElMessage.warning('最多4个标签'); tagInput.value = ''; return }
  props.formData.tags.push(val)
  tagInput.value = ''
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate((valid) => {
    if (!valid) return
    emit('submit')
  })
}
</script>

<style scoped>
.tag-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.tag-input { width: 100px; }
.form-tip { display: block; margin-top: 4px; font-size: 12px; color: #8c8c8c; line-height: 1.6; }
.public-access-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.public-access-row .form-tip { margin-top: 0; }
.color-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.color-swatch {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  border: 2px solid #e8e8e8;
  box-sizing: border-box;
}
.color-swatch.active { border-color: #1a1a1a; transform: scale(1.15); }
</style>
