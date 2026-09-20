import request from '@/utils/request'

// 解析单条 cURL 命令
export function parseCurl(curl) {
  return request({
    url: '/tools/parse-curl',
    method: 'post',
    data: { curl }
  })
}

// 批量解析多条 cURL 命令
export function parseCurls(curls, options = {}) {
  return request({
    url: '/tools/parse-curls-batch',
    method: 'post',
    data: { curls },
    ...options,
  })
}

// 执行 cURL 命令
export function executeCurl(curl) {
  return request({
    url: '/tools/execute-curl',
    method: 'post',
    data: { curl },
    timeout: 120000,
  })
}

// 断言编辑器：解析响应生成字段树，并按表达式试取值（错误提示由调用方内联展示）
export function inspectJsonResponse(data) {
  return request({
    url: '/tools/inspect',
    method: 'post',
    data,
    skipErrorToast: true,
  })
}

// XMind 转换工具 - 上传并解析
export function uploadXmind(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request({
    url: '/tools/xmind/upload',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
}

// XMind 生成工具 - 上传需求清单生成 XMind
export function generateXmind(file, sourceType = 'excel') {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('source_type', sourceType)
  return request({
    url: '/tools/xmind/generate',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
    responseType: 'blob',
  })
}

// 地址转经纬度
export function geocodeAddress(address) {
  return request({
    url: '/tools/geocode',
    method: 'post',
    data: { address },
  })
}

// 经纬度转地址
export function reverseGeocode(data) {
  return request({
    url: '/tools/regeo',
    method: 'post',
    data,
  })
}
