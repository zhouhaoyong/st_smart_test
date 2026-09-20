<template>
  <div class="tool-page">
    <div class="page-header"><h2>{{ pageTitle }}</h2></div>
    <el-card>
      <el-tabs v-model="activeTab" class="gen-tabs">

        <!-- ========== 时间戳转换 ========== -->
        <el-tab-pane label="时间戳" name="timestamp">
          <!-- 实时时钟 -->
          <div class="clock-section">
            <div class="clock-item">
              <div class="clock-label">当前时间</div>
              <div class="clock-value">{{ ts.currentInfo.current_time }}</div>
            </div>
            <div class="clock-divider"></div>
            <div class="clock-item">
              <div class="clock-label">秒时间戳</div>
              <div class="clock-value mono">{{ ts.currentInfo.current_ts_s }}</div>
            </div>
            <div class="clock-divider"></div>
            <div class="clock-item">
              <div class="clock-label">毫秒时间戳</div>
              <div class="clock-value mono">{{ ts.currentInfo.current_ts_ms }}</div>
            </div>
          </div>
          <el-divider />
          <el-row :gutter="32">
            <el-col :span="12">
              <div class="convert-panel">
                <div class="convert-title"><el-icon :size="18"><Right /></el-icon> 时间 → 时间戳</div>
                <div class="convert-body">
                  <el-input v-model="ts.timeForm.value" placeholder="YYYY-MM-DD HH:MM:SS" size="large" style="margin-bottom:10px" />
                  <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px">
                    <el-select v-model="ts.timeForm.unit" size="default" style="width:100px">
                      <el-option label="秒" value="s" /><el-option label="毫秒" value="ms" />
                    </el-select>
                    <el-button type="primary" @click="tsConvert('time_to_ts')" :loading="ts.loading">转换</el-button>
                  </div>
                  <div class="convert-result" v-if="ts.tsResult">
                    <el-tag size="small" type="success" effect="dark" style="margin-right:8px">结果</el-tag>
                    <code>{{ ts.tsResult }}</code>
                    <CopyButton :value="ts.tsResult" label="复制" tooltip="复制时间戳" />
                  </div>
                </div>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="convert-panel">
                <div class="convert-title"><el-icon :size="18"><Right style="transform:rotate(180deg)" /></el-icon> 时间戳 → 时间</div>
                <div class="convert-body">
                  <el-input v-model="ts.tsForm.value" placeholder="输入秒或毫秒时间戳" size="large" style="margin-bottom:10px" />
                  <el-button type="primary" @click="tsConvert('ts_to_time')" :loading="ts.loading" style="margin-bottom:10px">转换</el-button>
                  <div class="convert-result" v-if="ts.timeResult">
                    <el-tag size="small" type="success" effect="dark" style="margin-right:8px">结果</el-tag>
                    <code>{{ ts.timeResult }}</code>
                    <CopyButton :value="ts.timeResult" label="复制" tooltip="复制时间" />
                  </div>
                </div>
              </div>
            </el-col>
          </el-row>
        </el-tab-pane>

        <!-- ========== 身份证生成 ========== -->
        <el-tab-pane label="身份证生成" name="idcard">
          <el-form :model="id.form" label-width="100px" style="max-width:600px">
            <el-form-item label="性别">
              <el-radio-group v-model="id.form.gender">
                <el-radio :value="1">男</el-radio>
                <el-radio :value="2">女</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="年龄范围">
              <el-row :gutter="12" style="width:100%">
                <el-col :span="11"><el-input-number v-model="id.form.min_age" :min="0" :max="120" controls-position="right" style="width:100%" /> 岁</el-col>
                <el-col :span="2" style="text-align:center">~</el-col>
                <el-col :span="11"><el-input-number v-model="id.form.max_age" :min="0" :max="120" controls-position="right" style="width:100%" /> 岁</el-col>
              </el-row>
            </el-form-item>
            <el-form-item label="生成数量">
              <el-input-number v-model="id.form.count" :min="1" :max="100" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="idGenerate" :loading="id.loading">生成</el-button>
            </el-form-item>
          </el-form>
          <el-table v-if="id.records.length" :data="id.records" border class="id-result-table">
            <el-table-column label="身份证" min-width="260">
              <template #default="{ row }">
                <div class="id-copy-cell">
                  <code class="id-card-value">{{ row.id_card }}</code>
                  <CopyButton :value="row.id_card" tooltip="复制身份证" />
                </div>
              </template>
            </el-table-column>
            <el-table-column label="姓名" min-width="180">
              <template #default="{ row }">
                <div class="id-copy-cell">
                  <span>{{ row.name }}</span>
                  <CopyButton :value="row.name" tooltip="复制姓名" />
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Right } from '@element-plus/icons-vue'
import request from '@/utils/request'
import CopyButton from '@/components/CopyButton.vue'

const activeTab = ref('timestamp')
const route = useRoute()
const pageTitle = computed(() => route.meta.title || '生成工具')

watch(
  () => route.meta.toolTab,
  (tab) => {
    activeTab.value = tab || 'timestamp'
  },
  { immediate: true },
)

// ====== 时间戳 ======
const ts = reactive({
  loading: false, currentInfo: { current_time: '', current_ts_s: '', current_ts_ms: '' },
  timeForm: { value: '', unit: 's' }, tsForm: { value: '' }, tsResult: '', timeResult: '',
})
let timer = null

const tsLoadCurrent = async () => { try { const r = await request({ url: '/tools/timestamp', method: 'get' }); Object.assign(ts.currentInfo, r) } catch {} }

const tsConvert = async (dir) => {
  const value = dir === 'time_to_ts' ? ts.timeForm.value : ts.tsForm.value
  if (!value.trim()) { ElMessage.warning('请输入值'); return }
  ts.loading = true
  try {
    const data = { value, direction: dir, unit: dir === 'time_to_ts' ? ts.timeForm.unit : 's' }
    const res = await request({ url: '/tools/timestamp/convert', method: 'post', data })
    if (dir === 'time_to_ts') ts.tsResult = res.result; else ts.timeResult = res.result
  } catch {} finally { ts.loading = false }
}

// ====== 身份证 ======
const id = reactive({ loading: false, records: [], form: { gender: 1, min_age: 18, max_age: 60, count: 1 } })

watch(
  () => [id.form.gender, id.form.min_age, id.form.max_age, id.form.count],
  () => { id.records = [] },
)

const idGenerate = async () => {
  if (id.form.min_age > id.form.max_age) {
    ElMessage.warning('最小年龄不能大于最大年龄')
    id.records = []
    return
  }
  id.loading = true
  id.records = []
  try { const res = await request({ url: '/tools/id-card/generate', method: 'post', data: id.form }); id.records = res.records || [] }
  catch {} finally { id.loading = false }
}

onMounted(() => { tsLoadCurrent(); timer = setInterval(tsLoadCurrent, 1000) })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.tool-page { }
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 22px; }
.gen-tabs :deep(.el-tabs__header) { display: none; }

/* 时间戳时钟 */
.clock-section { display: flex; align-items: center; gap: 0; padding: 20px 24px; background: linear-gradient(135deg, #f0f5ff, #f6ffed); border-radius: 12px; }
.clock-item { flex: 1; text-align: center; }
.clock-label { font-size: 13px; color: #8c8c8c; margin-bottom: 6px; }
.clock-value { font-size: 22px; font-weight: 700; color: #1a1a1a; }
.clock-value.mono { font-family: SFMono-Regular, Consolas, monospace; font-size: 18px; color: #1677ff; }
.clock-divider { width: 1px; height: 48px; background: #d9d9d9; }

/* 转换面板 */
.convert-panel { background: #fafafa; border-radius: 10px; padding: 20px; }
.convert-title { display: flex; align-items: center; gap: 6px; font-size: 15px; font-weight: 600; color: #1a1a1a; margin-bottom: 14px; }
.convert-result { display: flex; align-items: center; gap: 8px; padding: 10px 14px; background: #f5f7fa; border-radius: 6px; margin-top: 4px; }
.convert-result code { font-size: 18px; font-family: monospace; color: #1677ff; flex: 1; word-break: break-all; }

/* 身份证 */
.id-result-table { width: min(640px, 100%); margin-top: 20px; }
.id-copy-cell { display: flex; align-items: center; gap: 8px; min-width: 0; }
.id-copy-cell > :first-child { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.id-copy-cell :deep(.el-button) { margin-left: auto; flex: 0 0 auto; }
.id-card-value { font-family: SFMono-Regular, Consolas, monospace; letter-spacing: .5px; }
</style>
