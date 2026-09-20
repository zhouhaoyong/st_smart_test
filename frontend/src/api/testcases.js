import request from '@/utils/request'

// 获取接口下的用例列表
export function getTestCases(interfaceId) {
  return request({ url: '/testcases', method: 'get', params: { interface_id: interfaceId } })
}

// 按接口分组（执行集选择器用）
export function getCasesByInterface(projectId, options = {}) {
  const params = { project_id: projectId }
  if (options.refresh) params._t = Date.now()
  return request({ url: '/testcases/by-interface', method: 'get', params })
}

// 获取用例详情
export function getTestCase(id) {
  return request({ url: `/testcases/${id}`, method: 'get' })
}

export function createTestCase(data, options = {}) {
  return request({ url: '/testcases', method: 'post', data, ...options })
}

export function updateTestCase(id, data) {
  return request({ url: `/testcases/${id}`, method: 'put', data })
}

export function copyTestCase(id) {
  return request({ url: `/testcases/${id}/copy`, method: 'post' })
}

export function deleteTestCase(id) {
  return request({ url: `/testcases/${id}`, method: 'delete' })
}

export function batchDeleteTestCases(ids) {
  return request({ url: '/testcases/batch-delete', method: 'post', data: { ids } })
}

// 批量删除当前项目、当前接口下仍未软删除的全部用例
export function batchDeleteTestCasesByInterface(projectId, interfaceId) {
  return request({
    url: '/testcases/batch-delete',
    method: 'post',
    data: { project_id: projectId, interface_id: interfaceId },
  })
}

export function batchConfirmTestCases(interfaceId) {
  return request({ url: '/testcases/batch-confirm', method: 'post', data: { interface_id: interfaceId } })
}
