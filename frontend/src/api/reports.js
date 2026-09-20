import request from '@/utils/request'

// 获取报告列表
export function getReports(projectId, executionSetId, page = 1, pageSize = 10, status = null, extraParams = {}) {
  return request({
    url: '/reports/',
    method: 'get',
    params: { project_id: projectId, execution_set_id: executionSetId || undefined, status: status || undefined, skip: (page - 1) * pageSize, limit: pageSize, ...extraParams }
  })
}

// 获取报告详情
export function getReport(id) {
  return request({
    url: `/reports/${id}`,
    method: 'get'
  })
}

// 获取报告步骤详情
export function getReportDetails(reportId) {
  return request({
    url: `/reports/${reportId}/details`,
    method: 'get'
  })
}

// 获取按用例分组的报告详情
export function getReportGroupedDetails(reportId, page = 1, pageSize = 10, params = {}) {
  return request({
    url: `/reports/${reportId}/grouped-details`,
    method: 'get',
    params: { skip: (page - 1) * pageSize, limit: pageSize, ...params }
  })
}

// 发送报告
export function sendReport(reportId) {
  return request({
    url: `/reports/${reportId}/send`,
    method: 'post',
    skipSuccessToast: true
  })
}

// 获取报告发送日志
export function getReportSendLogs(reportId) {
  return request({
    url: `/reports/${reportId}/send-logs`,
    method: 'get'
  })
}

// 删除报告
export function deleteReport(id) {
  return request({
    url: `/reports/${id}`,
    method: 'delete'
  })
}

// 批量删除报告
export function batchDeleteReports(ids) {
  return request({
    url: '/reports/batch-delete',
    method: 'post',
    data: { ids }
  })
}
