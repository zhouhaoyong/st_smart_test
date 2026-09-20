<template>
  <div class="cron-tool">
    <el-card>
      <template #header>
        <div class="tool-card-header">
          <h3>Cron 表达式</h3>
          <el-radio-group v-model="cronFormat" class="format-switch" aria-label="Cron 表达式格式">
            <el-radio-button label="standard">标准 Cron（5 位）</el-radio-button>
            <el-radio-button label="quartz">Quartz（6/7 位）</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <el-tabs v-model="activeTab" class="cron-tabs">
        <el-tab-pane label="生成表达式" name="generate">
          <el-form class="cron-form" label-width="112px">
            <el-form-item label="执行频率">
              <el-radio-group v-model="generation.frequency" class="frequency-switch">
                <el-radio-button v-for="option in frequencyOptions" :key="option.value" :label="option.value">
                  {{ option.label }}
                </el-radio-button>
              </el-radio-group>
            </el-form-item>

            <el-form-item v-if="generation.frequency === 'minutes'" label="执行间隔">
              <div class="number-field">
                <el-input-number v-model="generation.interval" :min="1" :max="59" controls-position="right" />
                <span>分钟</span>
              </div>
            </el-form-item>

            <el-form-item v-else-if="generation.frequency === 'hours'" label="执行时间">
              <div class="time-fields">
                <div class="number-field">
                  <el-input-number v-model="generation.interval" :min="1" :max="23" controls-position="right" />
                  <span>小时一次</span>
                </div>
                <div class="number-field">
                  <el-input-number v-model="generation.minute" :min="0" :max="59" controls-position="right" />
                  <span>分执行</span>
                </div>
              </div>
            </el-form-item>

            <el-form-item v-else-if="generation.frequency === 'daily'" label="执行时间">
              <div class="time-fields">
                <div class="number-field">
                  <el-input-number v-model="generation.hour" :min="0" :max="23" controls-position="right" />
                  <span>时</span>
                </div>
                <div class="number-field">
                  <el-input-number v-model="generation.minute" :min="0" :max="59" controls-position="right" />
                  <span>分</span>
                </div>
              </div>
            </el-form-item>

            <template v-else-if="generation.frequency === 'weekly'">
              <el-form-item label="执行日期" required>
                <div>
                  <el-checkbox-group v-model="generation.weekdays" class="weekday-switch">
                    <el-checkbox-button v-for="weekday in weekdayOptions" :key="weekday.value" :label="weekday.value">
                      {{ weekday.label }}
                    </el-checkbox-button>
                  </el-checkbox-group>
                  <div v-if="!generation.weekdays.length" class="form-tip">请至少选择一个执行日</div>
                </div>
              </el-form-item>
              <el-form-item label="执行时间">
                <div class="time-fields">
                  <div class="number-field">
                    <el-input-number v-model="generation.hour" :min="0" :max="23" controls-position="right" />
                    <span>时</span>
                  </div>
                  <div class="number-field">
                    <el-input-number v-model="generation.minute" :min="0" :max="59" controls-position="right" />
                    <span>分</span>
                  </div>
                </div>
              </el-form-item>
            </template>

            <template v-else>
              <el-form-item label="执行日期">
                <div class="number-field">
                  <el-input-number v-model="generation.dayOfMonth" :min="1" :max="31" controls-position="right" />
                  <span>日</span>
                </div>
              </el-form-item>
              <el-form-item label="执行时间">
                <div class="time-fields">
                  <div class="number-field">
                    <el-input-number v-model="generation.hour" :min="0" :max="23" controls-position="right" />
                    <span>时</span>
                  </div>
                  <div class="number-field">
                    <el-input-number v-model="generation.minute" :min="0" :max="59" controls-position="right" />
                    <span>分</span>
                  </div>
                </div>
              </el-form-item>
            </template>

            <el-form-item>
              <el-button type="primary" :loading="generating" :disabled="!canGenerate" @click="generateExpression">
                生成表达式
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="解析表达式" name="analyze">
          <el-form class="cron-form" label-width="112px">
            <el-form-item label="Cron 表达式">
              <el-input
                v-model="expression"
                class="expression-input"
                type="textarea"
                :rows="5"
                placeholder="例如：0 9 * * 1-5"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="analyzing" :disabled="!canAnalyze" @click="analyzeExpression">
                解析表达式
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <section v-if="result" class="result-section">
        <el-divider content-position="left">结果</el-divider>
        <el-alert
          v-if="result.notice"
          class="result-notice"
          :title="result.notice"
          type="warning"
          show-icon
          :closable="false"
        />
        <el-descriptions :column="1" border class="result-descriptions">
          <el-descriptions-item label="表达式格式">{{ resultFormatLabel }}</el-descriptions-item>
          <el-descriptions-item label="Cron 表达式">
            <div class="expression-result">
              <code>{{ result.expression || '-' }}</code>
              <CopyButton :value="result.expression" label="复制" tooltip="复制 Cron 表达式" />
            </div>
          </el-descriptions-item>
          <el-descriptions-item label="执行说明">{{ result.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="下次执行时间">
            <div class="next-times-header">
              <span class="timezone-label">北京时间</span>
              <CopyButton :value="nextTimesText" label="复制全部" tooltip="复制下次执行时间" :disabled="!nextTimesText" />
            </div>
            <ol v-if="nextTimes.length" class="next-times">
              <li v-for="(time, index) in nextTimes" :key="`${time}-${index}`">{{ time }}</li>
            </ol>
            <span v-else class="empty-times">暂无可用执行时间</span>
          </el-descriptions-item>
        </el-descriptions>
      </section>
    </el-card>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import request from '@/utils/request'
import CopyButton from '@/components/CopyButton.vue'

const activeTab = ref('generate')
const cronFormat = ref('standard')
const expression = ref('')
const generating = ref(false)
const analyzing = ref(false)
const result = ref(null)

const generation = reactive({
  frequency: 'minutes',
  interval: 5,
  minute: 0,
  hour: 9,
  weekdays: [1],
  dayOfMonth: 1,
})

const frequencyOptions = [
  { label: '每 N 分钟', value: 'minutes' },
  { label: '每 N 小时的第 N 分钟', value: 'hours' },
  { label: '每天固定时间', value: 'daily' },
  { label: '每周指定日期', value: 'weekly' },
  { label: '每月指定日期', value: 'monthly' },
]

const weekdayOptions = [
  { label: '周一', value: 1 },
  { label: '周二', value: 2 },
  { label: '周三', value: 3 },
  { label: '周四', value: 4 },
  { label: '周五', value: 5 },
  { label: '周六', value: 6 },
  { label: '周日', value: 7 },
]

const canGenerate = computed(() => generation.frequency !== 'weekly' || generation.weekdays.length > 0)
const canAnalyze = computed(() => expression.value.trim().length > 0)
const nextTimes = computed(() => Array.isArray(result.value?.next_times) ? result.value.next_times : [])
const nextTimesText = computed(() => nextTimes.value.join('\n'))
const resultFormatLabel = computed(() => result.value?.format === 'quartz' ? 'Quartz（6/7 位）' : '标准 Cron（5 位）')

const normalizeResult = (data) => ({
  format: typeof data?.format === 'string' ? data.format : '',
  expression: typeof data?.expression === 'string' ? data.expression : '',
  description: typeof data?.description === 'string' ? data.description : '',
  next_times: Array.isArray(data?.next_times) ? data.next_times.filter(time => typeof time === 'string') : [],
  notice: typeof data?.notice === 'string' ? data.notice : '',
})

const generateExpression = async () => {
  generating.value = true
  result.value = null
  try {
    const data = await request({
      url: '/tools/cron/generate',
      method: 'post',
      data: {
        cron_format: cronFormat.value,
        frequency: generation.frequency,
        interval: generation.interval,
        minute: generation.minute,
        hour: generation.hour,
        weekdays: generation.weekdays,
        day_of_month: generation.dayOfMonth,
      },
    })
    result.value = normalizeResult(data)
  } catch {} finally {
    generating.value = false
  }
}

const analyzeExpression = async () => {
  analyzing.value = true
  result.value = null
  try {
    const data = await request({
      url: '/tools/cron/analyze',
      method: 'post',
      data: {
        cron_format: cronFormat.value,
        expression: expression.value.trim(),
      },
    })
    result.value = normalizeResult(data)
  } catch {} finally {
    analyzing.value = false
  }
}
</script>

<style scoped>
.tool-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.tool-card-header h3 {
  margin: 0;
  color: var(--el-text-color-primary);
  font-size: 18px;
  font-weight: 600;
}
.format-switch,
.frequency-switch,
.weekday-switch {
  display: flex;
  flex-wrap: wrap;
}
.cron-tabs :deep(.el-tabs__header) { margin-bottom: 20px; }
.cron-form { max-width: 760px; padding-top: 4px; }
.time-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}
.number-field {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-regular);
}
.number-field :deep(.el-input-number) { width: 128px; }
.form-tip {
  margin-top: 6px;
  color: var(--el-color-danger);
  font-size: 12px;
  line-height: 1.4;
}
.expression-input { max-width: 620px; }
.expression-input :deep(.el-textarea__inner),
.expression-result code {
  font-family: SFMono-Regular, Consolas, Monaco, monospace;
}
.result-section { margin-top: 8px; }
.result-section :deep(.el-divider__text) {
  padding: 0 10px 0 0;
  color: var(--el-text-color-primary);
  font-weight: 600;
}
.result-notice { margin-bottom: 14px; }
.result-descriptions { width: 100%; }
.expression-result,
.next-times-header {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.expression-result code {
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--el-color-primary);
  font-size: 15px;
}
.timezone-label {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.next-times { margin: 8px 0 0; padding-left: 20px; }
.next-times li { line-height: 1.8; }
.empty-times { color: var(--el-text-color-secondary); }
@media (max-width: 640px) {
  .tool-card-header { align-items: flex-start; flex-direction: column; }
  .format-switch { width: 100%; }
  .cron-form { max-width: none; }
  .cron-form :deep(.el-form-item__label) { width: auto !important; }
  .cron-form :deep(.el-form-item__content) { margin-left: 0 !important; }
  .cron-form :deep(.el-form-item) { display: block; }
  .cron-form :deep(.el-form-item__label) { display: block; text-align: left; }
  .expression-input { max-width: none; }
  .result-descriptions :deep(.el-descriptions__label) { width: 96px; }
}
</style>
