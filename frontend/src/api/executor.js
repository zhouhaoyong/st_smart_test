import request from '@/utils/request'

// 上传临时文件（用于 form-data 文件上传）
export function uploadTempFile(file, config = {}) {
  const form = new FormData()
  form.append('file', file)
  return request.post('/executor/upload-file', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    ...config,
  })
}

// 调试：发送单次接口请求
export function debugRequest(data) {
  return request({
    url: '/executor/debug',
    method: 'post',
    data,
  })
}

// 运行用例
export function runTestCase(data, options = {}) {
  return request({
    url: '/executor/run-case',
    method: 'post',
    data,
    ...options,
  })
}
