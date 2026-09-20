import request from '@/utils/request'

// 获取执行集列表
export function getExecutionSets(projectId, page, pageSize, extraParams = {}) {
  return request({
    url: '/executions/',
    method: 'get',
    params: { project_id: projectId, skip: page ? (page - 1) * (pageSize || 10) : 0, limit: pageSize || 10, ...extraParams }
  })
}

// 创建执行集（含执行项）
export function createExecutionSet(data) {
  return request({
    url: '/executions/',
    method: 'post',
    data
  })
}

// 获取执行集详情
export function getExecutionSet(id) {
  return request({
    url: `/executions/${id}`,
    method: 'get'
  })
}

// 更新执行集
export function updateExecutionSet(id, data) {
  return request({
    url: `/executions/${id}`,
    method: 'put',
    data
  })
}

// 删除执行集
export function deleteExecutionSet(id) {
  return request({
    url: `/executions/${id}`,
    method: 'delete'
  })
}

// 执行执行集
export function runExecutionSet(id) {
  return request({
    url: `/executions/${id}/run`,
    method: 'post',
    skipSuccessToast: true
  })
}

// 批量删除执行集
export function batchDeleteExecutionSets(ids) {
  return request({
    url: '/executions/batch-delete',
    method: 'post',
    data: { ids }
  })
}
