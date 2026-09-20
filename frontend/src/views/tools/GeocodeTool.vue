<template>
  <div class="tool-page geocode-page">
    <div class="page-header">
      <h2>{{ activeTab === 'geocode' ? '地址转经纬度' : '经纬度转地址' }}</h2>
      <p>{{ activeTab === 'geocode' ? '输入中文地址，查询高德地图匹配的经度和纬度。' : '输入经度和纬度，查询高德地图匹配的中文地址。' }}</p>
    </div>

    <el-card class="geocode-card">
      <el-tabs v-model="activeTab" class="geocode-tabs">
        <el-tab-pane label="地址转经纬度" name="geocode">
          <el-form label-position="top" @submit.prevent="handleQuery">
            <el-form-item label="中文地址" required>
              <el-input
                v-model="address"
                type="textarea"
                :rows="3"
                maxlength="128"
                show-word-limit
                clearable
                placeholder="例如：北京市朝阳区阜通东大街6号"
                @keydown.ctrl.enter.prevent="handleQuery"
              />
            </el-form-item>
            <div class="form-actions">
              <el-button type="primary" :loading="loading" @click="handleQuery">查询经纬度</el-button>
              <el-button :disabled="loading" @click="handleClear">清空</el-button>
            </div>
          </el-form>

          <el-alert
            class="coordinate-tip"
            title="结果为高德地图坐标（GCJ-02），经度在前、纬度在后。"
            type="info"
            :closable="false"
            show-icon
          />

          <div v-if="result" class="result-panel">
            <div class="result-title">查询结果</div>
            <div class="result-grid">
              <div class="result-item">
                <span class="result-label">经度</span>
                <code>{{ result.longitude }}</code>
                <CopyButton :value="result.longitude" label="复制" tooltip="复制经度" />
              </div>
              <div class="result-item">
                <span class="result-label">纬度</span>
                <code>{{ result.latitude }}</code>
                <CopyButton :value="result.latitude" label="复制" tooltip="复制纬度" />
              </div>
              <div class="result-item result-item-wide">
                <span class="result-label">坐标</span>
                <code>{{ result.location }}</code>
                <CopyButton :value="result.location" label="复制" tooltip="复制坐标" />
              </div>
            </div>

            <el-descriptions class="address-details" :column="2" border>
              <el-descriptions-item label="匹配地址" :span="2">
                <div class="description-value">
                  <span>{{ result.formatted_address || '—' }}</span>
                  <CopyButton :value="result.formatted_address" label="复制" tooltip="复制匹配地址" />
                </div>
              </el-descriptions-item>
              <el-descriptions-item label="匹配级别">
                <div class="description-value">
                  <span>{{ result.level || '—' }}</span>
                  <CopyButton :value="result.level" label="复制" tooltip="复制匹配级别" />
                </div>
              </el-descriptions-item>
              <el-descriptions-item label="行政区划代码">
                <div class="description-value">
                  <span>{{ result.adcode || '—' }}</span>
                  <CopyButton :value="result.adcode" label="复制" tooltip="复制行政区划代码" />
                </div>
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-tab-pane>

        <el-tab-pane label="经纬度转地址" name="regeo">
          <el-form label-position="top" @submit.prevent="handleReverseQuery">
            <div class="coordinate-fields">
              <el-form-item label="经度" required>
                <el-input v-model="reverseForm.longitude" clearable placeholder="请输入经度" />
              </el-form-item>
              <el-form-item label="纬度" required>
                <el-input v-model="reverseForm.latitude" clearable placeholder="请输入纬度" />
              </el-form-item>
            </div>
            <div class="form-actions">
              <el-button type="primary" :loading="reverseLoading" @click="handleReverseQuery">查询中文地址</el-button>
              <el-button :disabled="reverseLoading" @click="handleReverseClear">清空</el-button>
            </div>
          </el-form>

          <el-alert
            class="coordinate-tip"
            title="请输入高德 GCJ-02 坐标，经度在前、纬度在后。"
            type="info"
            :closable="false"
            show-icon
          />

          <div v-if="reverseResult" class="result-panel">
            <div class="result-title">查询结果</div>
            <div class="result-grid">
              <div class="result-item result-item-wide">
                <span class="result-label">中文地址</span>
                <span class="address-value">{{ reverseResult.formatted_address }}</span>
                <CopyButton :value="reverseResult.formatted_address" label="复制" tooltip="复制中文地址" />
              </div>
              <div class="result-item result-item-wide">
                <span class="result-label">坐标</span>
                <code>{{ reverseResult.location }}</code>
                <CopyButton :value="reverseResult.location" label="复制" tooltip="复制坐标" />
              </div>
            </div>

            <el-descriptions class="address-details" :column="2" border>
              <el-descriptions-item label="省份">
                <div class="description-value">
                  <span>{{ reverseResult.province || '—' }}</span>
                  <CopyButton :value="reverseResult.province" label="复制" tooltip="复制省份" />
                </div>
              </el-descriptions-item>
              <el-descriptions-item label="城市">
                <div class="description-value">
                  <span>{{ reverseResult.city || '—' }}</span>
                  <CopyButton :value="reverseResult.city" label="复制" tooltip="复制城市" />
                </div>
              </el-descriptions-item>
              <el-descriptions-item label="区县">
                <div class="description-value">
                  <span>{{ reverseResult.district || '—' }}</span>
                  <CopyButton :value="reverseResult.district" label="复制" tooltip="复制区县" />
                </div>
              </el-descriptions-item>
              <el-descriptions-item label="街道">
                <div class="description-value">
                  <span>{{ reverseResult.street || '—' }}</span>
                  <CopyButton :value="reverseResult.street" label="复制" tooltip="复制街道" />
                </div>
              </el-descriptions-item>
              <el-descriptions-item label="行政区划代码" :span="2">
                <div class="description-value">
                  <span>{{ reverseResult.adcode || '—' }}</span>
                  <CopyButton :value="reverseResult.adcode" label="复制" tooltip="复制行政区划代码" />
                </div>
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import CopyButton from '@/components/CopyButton.vue'
import { geocodeAddress, reverseGeocode } from '@/api/tools'

const activeTab = ref('geocode')
const address = ref('')
const loading = ref(false)
const result = ref(null)
const reverseForm = reactive({ longitude: '', latitude: '' })
const reverseLoading = ref(false)
const reverseResult = ref(null)

const handleQuery = async () => {
  const value = address.value.trim()
  if (!value) {
    ElMessage.warning('请输入地址')
    return
  }

  loading.value = true
  result.value = null
  try {
    result.value = await geocodeAddress(value)
  } catch {
    // 请求工具已统一提示后端返回的错误信息，这里只负责清理当前结果。
  } finally {
    loading.value = false
  }
}

const handleClear = () => {
  address.value = ''
  result.value = null
}

const handleReverseQuery = async () => {
  const longitude = reverseForm.longitude.trim()
  const latitude = reverseForm.latitude.trim()
  if (!longitude || !latitude) {
    ElMessage.warning('请输入经度和纬度')
    return
  }

  const longitudeValue = Number(longitude)
  const latitudeValue = Number(latitude)
  if (!Number.isFinite(longitudeValue) || !Number.isFinite(latitudeValue)) {
    ElMessage.warning('请输入有效的经度和纬度')
    return
  }
  if (longitudeValue < -180 || longitudeValue > 180) {
    ElMessage.warning('经度范围应为 -180 至 180')
    return
  }
  if (latitudeValue < -90 || latitudeValue > 90) {
    ElMessage.warning('纬度范围应为 -90 至 90')
    return
  }

  reverseLoading.value = true
  reverseResult.value = null
  try {
    reverseResult.value = await reverseGeocode({ longitude, latitude })
  } catch {
    // 请求工具已统一提示后端返回的错误信息，这里只负责清理当前结果。
  } finally {
    reverseLoading.value = false
  }
}

const handleReverseClear = () => {
  reverseForm.longitude = ''
  reverseForm.latitude = ''
  reverseResult.value = null
}
</script>

<style scoped>
.geocode-page { width: 100%; margin: 0; }
.page-header { margin-bottom: 0; }
.page-header h2 { margin: 0; font-size: 22px; color: #1f2937; }
.page-header p { margin: 8px 0 0; color: #6b7280; font-size: 14px; }
.geocode-card { width: min(100%, 1200px); margin: 28px 0 0; }
.geocode-card :deep(.el-card__body) { padding-bottom: 28px; }
.geocode-tabs :deep(.el-tabs__header) { margin-bottom: 22px; }
.geocode-card :deep(.el-form-item__label) { font-weight: 600; }
.form-actions { display: flex; gap: 10px; }
.coordinate-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.coordinate-tip { margin-top: 12px; }
.result-panel { margin-top: 24px; }
.result-title { margin-bottom: 12px; font-size: 16px; font-weight: 600; color: #1f2937; }
.result-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.result-item {
  display: flex; align-items: center; gap: 10px; min-width: 0;
  padding: 14px 16px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fafafa;
}
.result-item-wide { grid-column: 1 / -1; }
.result-label { flex: 0 0 auto; color: #6b7280; font-size: 14px; }
.result-item code { min-width: 0; flex: 1; color: #1677ff; font-size: 17px; font-family: SFMono-Regular, Consolas, monospace; word-break: break-all; }
.result-item :deep(.el-button) { flex: 0 0 auto; }
.address-value { min-width: 0; flex: 1; color: #1677ff; font-size: 16px; line-height: 1.5; word-break: break-all; }
.description-value { display: flex; align-items: center; gap: 8px; min-width: 0; }
.description-value > :first-child { min-width: 0; flex: 1; word-break: break-all; }
.description-value :deep(.el-button) { flex: 0 0 auto; }
.address-details { margin-top: 16px; }
@media (max-width: 680px) {
  .coordinate-fields { grid-template-columns: 1fr; gap: 0; }
  .result-grid { grid-template-columns: 1fr; }
  .result-item-wide { grid-column: auto; }
  .address-details :deep(.el-descriptions__body) { overflow-x: auto; }
}
</style>
