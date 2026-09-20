<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="min(680px, calc(100vw - 40px))"
    top="8vh"
    append-to-body
    class="quota-stats-dialog"
  >
    <div class="qs-filter">
      <el-radio-group v-model="filterType" size="small" @change="onFilterTypeChange">
        <el-radio-button value="today">今日</el-radio-button>
        <el-radio-button value="day">按天</el-radio-button>
        <el-radio-button value="range">按时间段</el-radio-button>
      </el-radio-group>
      <el-date-picker
        v-if="filterType === 'day'"
        v-model="dayValue"
        type="date"
        size="small"
        placeholder="选择日期"
        :clearable="false"
        :disabled-date="disabledFutureDate"
        class="qs-picker"
        @change="loadStats"
      />
      <el-date-picker
        v-else-if="filterType === 'range'"
        v-model="rangeValue"
        type="daterange"
        size="small"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        :clearable="false"
        :disabled-date="disabledFutureDate"
        class="qs-picker-range"
        @change="loadStats"
      />
      <span class="qs-mode-hint">{{ modeHint }}</span>
    </div>

    <div v-loading="loading" class="qs-body">
      <div v-if="errorMessage" class="qs-error-state">
        <el-alert :title="errorMessage" type="error" :closable="false" show-icon />
        <el-button type="primary" size="small" @click="loadStats">重新查询</el-button>
      </div>
      <el-tabs v-else v-model="activeTab">
        <el-tab-pane label="平台模型" name="platform">
          <div class="qs-block">
            <div class="qs-block-title">平台模型</div>
            <div class="qs-metrics">
              <template v-if="isTodayMode">
                <div class="qs-metric"><span class="qs-metric-label">已用</span><strong>{{ platform.used ?? 0 }} 次</strong></div>
                <div class="qs-metric"><span class="qs-metric-label">上限</span><strong>{{ limitText(platform.limit) }}</strong></div>
                <div class="qs-metric"><span class="qs-metric-label">剩余</span><strong>{{ remainingText(platform) }}</strong></div>
              </template>
              <template v-else>
                <div class="qs-metric"><span class="qs-metric-label">成功</span><strong>{{ platform.succeeded ?? 0 }} 次</strong></div>
                <div class="qs-metric"><span class="qs-metric-label">失败</span><strong>{{ platform.failed ?? 0 }} 次</strong></div>
                <div class="qs-metric"><span class="qs-metric-label">扣费</span><strong>{{ platform.consumed ?? 0 }} 次</strong></div>
              </template>
            </div>
            <div v-if="isTodayMode" class="qs-sub">成功 {{ platform.succeeded ?? 0 }} · 失败 {{ platform.failed ?? 0 }} · 扣费 {{ platform.consumed ?? 0 }}</div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="我的模型" name="personal">
          <div v-if="personal.length" class="qs-personal-list">
            <div v-for="item in personal" :key="item.model_id ?? item.model_name" class="qs-block">
              <div class="qs-block-title">{{ item.model_name || '未命名模型' }}</div>
              <div class="qs-metrics">
                <template v-if="isTodayMode">
                  <div class="qs-metric"><span class="qs-metric-label">已用</span><strong>{{ item.used ?? 0 }} 次</strong></div>
                  <div class="qs-metric"><span class="qs-metric-label">上限</span><strong>{{ limitText(item.limit) }}</strong></div>
                  <div class="qs-metric"><span class="qs-metric-label">剩余</span><strong>{{ remainingText(item) }}</strong></div>
                </template>
                <template v-else>
                  <div class="qs-metric"><span class="qs-metric-label">成功</span><strong>{{ item.succeeded ?? 0 }} 次</strong></div>
                  <div class="qs-metric"><span class="qs-metric-label">失败</span><strong>{{ item.failed ?? 0 }} 次</strong></div>
                  <div class="qs-metric"><span class="qs-metric-label">扣费</span><strong>{{ item.consumed ?? 0 }} 次</strong></div>
                </template>
              </div>
              <div v-if="isTodayMode" class="qs-sub">成功 {{ item.succeeded ?? 0 }} · 失败 {{ item.failed ?? 0 }} · 扣费 {{ item.consumed ?? 0 }}</div>
            </div>
          </div>
          <el-empty v-else :description="isTodayMode ? '该用户暂无已配置额度的我的模型' : '该时段暂无我的模型用量'" :image-size="64" />
        </el-tab-pane>
      </el-tabs>
    </div>

    <template #footer>
      <el-button type="primary" @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { getUserQuotaStats } from '@/api/ai'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  userId: { type: [Number, String], default: null },
  userName: { type: String, default: '' },
  modelScope: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const filterType = ref('today')
const dayValue = ref(new Date())
const rangeValue = ref([new Date(), new Date()])
const activeTab = ref('platform')
const loading = ref(false)
const errorMessage = ref('')
const platform = ref({ used: 0, limit: null, remaining: null, succeeded: 0, failed: 0, consumed: 0 })
const personal = ref([])
const isTodayMode = ref(true)

const dialogTitle = computed(() => (props.userName ? `用量统计 · ${props.userName}` : '用量统计'))
const modeHint = computed(() => (
  currentMode() === 'today'
    ? '额度视角：显示已用 / 上限 / 剩余'
    : '仅显示所选时段的调用次数，不含上限'
))

function ymd(d) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date(d))
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]))
  return `${values.year}-${values.month}-${values.day}`
}
function isToday(d) { return ymd(d) === ymd(new Date()) }
function disabledFutureDate(date) { return date.getTime() > Date.now() }
function dateFromYmd(value) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}
function todayDate() {
  return dateFromYmd(ymd(new Date()))
}
function yesterdayDate() {
  const date = todayDate()
  date.setDate(date.getDate() - 1)
  return date
}
function currentMonthRange() {
  const today = todayDate()
  return [new Date(today.getFullYear(), today.getMonth(), 1), today]
}

function currentMode() {
  if (filterType.value === 'today') return 'today'
  if (filterType.value === 'day') return isToday(dayValue.value) ? 'today' : 'range'
  return 'range'
}

function currentRange() {
  if (filterType.value === 'today') {
    const day = ymd(new Date())
    return [`${day} 00:00:00`, `${day} 23:59:59`]
  }
  if (filterType.value === 'day') {
    const day = ymd(dayValue.value)
    return [`${day} 00:00:00`, `${day} 23:59:59`]
  }
  const [start, end] = rangeValue.value || []
  if (!start || !end) return null
  return [`${ymd(start)} 00:00:00`, `${ymd(end)} 23:59:59`]
}

function limitText(limit) {
  if (limit === -1) return '不限'
  if (limit == null) return '未配置'
  return `${limit} 次`
}
function remainingText(block) {
  if (block?.limit === -1) return '不限'
  if (block?.remaining == null) return '—'
  return `${block.remaining} 次`
}

async function loadStats() {
  if (!props.userId) return
  const range = currentRange()
  if (!range) return
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await getUserQuotaStats({
      user_id: props.userId,
      mode: currentMode(),
      start_time: range[0],
      end_time: range[1],
    })
    isTodayMode.value = !!res?.today_mode
    platform.value = res?.platform || { used: 0, limit: null, remaining: null, succeeded: 0, failed: 0, consumed: 0 }
    personal.value = Array.isArray(res?.personal) ? res.personal : []
  } catch (error) {
    const message = String(error?.message || '')
    errorMessage.value = message && message !== 'Network Error' ? message : '用量统计查询失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function onFilterTypeChange() {
  if (filterType.value === 'day') dayValue.value = yesterdayDate()
  if (filterType.value === 'range') rangeValue.value = currentMonthRange()
  loadStats()
}

watch(visible, (val) => {
  if (val) {
    filterType.value = 'today'
    dayValue.value = yesterdayDate()
    rangeValue.value = currentMonthRange()
    activeTab.value = props.modelScope === 'personal' ? 'personal' : 'platform'
    loadStats()
  }
})

watch(() => props.modelScope, (scope) => {
  if (visible.value) activeTab.value = scope === 'personal' ? 'personal' : 'platform'
})
</script>

<style scoped>
.qs-filter { display: flex; align-items: center; flex-wrap: wrap; gap: 10px 12px; margin-bottom: 12px; }
.qs-picker { width: 160px; }
.qs-picker-range { width: 260px; }
.qs-mode-hint { font-size: 12px; color: #909399; }
.qs-body { min-height: 200px; }
.qs-error-state { display: flex; flex-direction: column; align-items: center; gap: 14px; padding: 36px 20px; }
.qs-personal-list { display: flex; flex-direction: column; gap: 12px; }
.qs-block { border: 1px solid #edf1f7; border-radius: 8px; padding: 14px 16px; background: #fff; }
.qs-block-title { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.qs-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; }
.qs-metric { display: flex; flex-direction: column; gap: 6px; padding: 10px 12px; border-radius: 8px; background: #f8fafc; }
.qs-metric-label { font-size: 12px; color: #8c8c8c; }
.qs-metric strong { font-size: 20px; font-weight: 700; color: #1a1a1a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.qs-sub { margin-top: 10px; font-size: 12px; color: #909399; }
</style>
