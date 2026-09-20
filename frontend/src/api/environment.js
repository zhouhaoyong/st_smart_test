import request from '../utils/request'

// 获取环境列表
export function getEnvironments(projectId, page, pageSize) {
  return request({
    url: '/environments/',
    method: 'get',
    params: { project_id: projectId, skip: page ? (page - 1) * (pageSize || 10) : 0, limit: pageSize || 100 }
  })
}

// 创建环境
export function createEnvironment(data, options = {}) {
  return request({
    url: '/environments/',
    method: 'post',
    data,
    ...options
  })
}

// 更新环境
export function updateEnvironment(id, data, options = {}) {
  return request({
    url: `/environments/${id}`,
    method: 'put',
    data,
    ...options
  })
}

// 删除环境
export function deleteEnvironment(id) {
  return request({
    url: `/environments/${id}`,
    method: 'delete'
  })
}

// 复制环境
export function copyEnvironment(id) {
  return request({
    url: `/environments/${id}/copy`,
    method: 'post'
  })
}

// 获取Token（支持内联配置，无需先保存到环境）
export function fetchToken(envId, config, options = {}) {
  return request({
    url: `/environments/${envId}/fetch-token`,
    method: 'post',
    data: config || {},
    ...options
  })
}

export function fetchTokenPreview(config, options = {}) {
  return request({
    url: '/environments/fetch-token',
    method: 'post',
    data: config || {},
    ...options
  })
}

export function getEnvironmentServiceUsage(id) {
  return request({
    url: `/environments/${id}/service-usage`,
    method: 'get'
  })
}
