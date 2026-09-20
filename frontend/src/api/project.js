import request from '@/utils/request'

// 获取项目列表
export const getProjects = (params) => {
  return request({
    url: '/projects/',
    method: 'get',
    params
  })
}

// 创建项目
export const createProject = (data) => {
  return request({
    url: '/projects/',
    method: 'post',
    data
  })
}

// 获取项目详情
export const getProject = (id) => {
  return request({
    url: `/projects/${id}`,
    method: 'get'
  })
}

// 更新项目
export const updateProject = (id, data) => {
  return request({
    url: `/projects/${id}`,
    method: 'put',
    data
  })
}

// 项目数据看板
export const getProjectDashboard = (projectId) => {
  return request({
    url: `/projects/${projectId}/dashboard`,
    method: 'get'
  })
}

// API 测试项目数据清理
export const getProjectBusinessCleanupSummary = (projectId) => {
  return request({
    url: `/projects/${projectId}/business-cleanup-summary`,
    method: 'get'
  })
}

export const clearProjectBusinessData = (projectId, data) => {
  return request({
    url: `/projects/${projectId}/clear-business-data`,
    method: 'post',
    data,
    skipSuccessToast: true,
  })
}

// 删除项目
export const deleteProject = (id) => {
  return request({
    url: `/projects/${id}`,
    method: 'delete'
  })
}

// 复制项目
export const copyProject = (id) => {
  return request({
    url: `/projects/${id}/copy`,
    method: 'post'
  })
}
