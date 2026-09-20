import request from '@/utils/request'

const serializeAuditParams = (params = {}) => {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.filter(item => item !== null && item !== undefined && item !== '').forEach(item => searchParams.append(key, item))
    } else if (value !== null && value !== undefined && value !== '') {
      searchParams.append(key, value)
    }
  })
  return searchParams.toString()
}

export function getAuditLogs(params) {
  return request({ url: '/audit/', method: 'get', params, paramsSerializer: serializeAuditParams })
}

export function deleteAuditLogsBatch(ids, config = {}) {
  return request({
    url: '/audit/delete-batch',
    method: 'post',
    data: { ids },
    skipSuccessToast: true,
    ...config,
  })
}

export function deleteAuditLogsAll(params = {}, config = {}) {
  return request({
    url: '/audit/delete-all',
    method: 'post',
    data: params,
    skipSuccessToast: true,
    ...config,
  })
}
