import request from '@/utils/request'

/** 上传文件解析导入文档 */
export function parseImportFile(file) {
  const form = new FormData()
  form.append('file', file)
  return request.post('/import/parse-file', form, { headers: { 'Content-Type': 'multipart/form-data' } })
}

/** 解析完成后先判重：只读比对，返回这次真的会落库的接口 */
export function checkImportDuplicates(data) {
  return request.post('/import/check-duplicates', data)
}

/** 执行导入 */
export function executeImport(data) {
  return request.post('/import/execute', data)
}

export function downloadImportExcelTemplate() {
  return request.get('/import/excel-template', { responseType: 'blob' })
}
