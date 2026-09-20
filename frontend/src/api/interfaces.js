import request from '@/utils/request'

export function getInterfaces(collectionId, projectId, page, pageSize, extraParams = {}) {
  const params = collectionId != null ? { collection_id: collectionId } : { project_id: projectId }
  if (page != null) {
    params.skip = (page - 1) * (pageSize || 10)
    params.limit = pageSize || 10
  }
  Object.assign(params, extraParams)
  return request({
    url: '/interfaces/',
    method: 'get',
    params,
    paramsSerializer: { indexes: null },
  })
}

export function getInterfaceMethods(projectId) {
  return request({
    url: '/interfaces/methods',
    method: 'get',
    params: { project_id: projectId },
    skipSuccessToast: true,
    skipErrorToast: true,
  })
}

export function getInterfaceSelectionIds(projectId, params = {}) {
  return request({
    url: '/interfaces/selection-ids',
    method: 'get',
    params: { project_id: projectId, ...params },
    paramsSerializer: { indexes: null },
    skipSuccessToast: true,
    skipErrorToast: true,
  })
}

export function batchUpdateInterfaceWorkflowStatus(ids, workflowStatus) {
  return request({
    url: '/interfaces/batch-workflow-status',
    method: 'post',
    data: { ids, workflow_status: workflowStatus },
  })
}

export function createInterface(data, options = {}) {
  return request({
    url: '/interfaces/',
    method: 'post',
    data,
    ...options,
  })
}

export function getInterface(id) {
  return request({
    url: `/interfaces/${id}`,
    method: 'get',
  })
}

export function updateInterface(id, data) {
  return request({
    url: `/interfaces/${id}`,
    method: 'put',
    data,
  })
}

export function moveInterface(id, collectionId, options = {}) {
  return request({
    url: `/interfaces/${id}/move`,
    method: 'post',
    data: { collection_id: collectionId },
    ...options,
  })
}

export function batchMoveInterfaces(ids, collectionId, options = {}) {
  return request({
    url: '/interfaces/batch-move',
    method: 'post',
    data: { interface_ids: ids, collection_id: collectionId },
    ...options,
  })
}

export function deleteInterface(id) {
  return request({
    url: `/interfaces/${id}`,
    method: 'delete',
  })
}

export function copyInterface(id) {
  return request({
    url: `/interfaces/${id}/copy`,
    method: 'post',
  })
}

export function batchDeleteInterfaces(ids) {
  return request({
    url: '/interfaces/batch-delete',
    method: 'post',
    data: { ids },
  })
}

export function batchUpdateInterfaceService(ids, serviceKey) {
  return request({
    url: '/interfaces/batch-service',
    method: 'post',
    data: { ids, service_key: serviceKey || null },
  })
}

export function batchImportCurl(data, options = {}) {
  return request({
    url: '/import/curl-batch',
    method: 'post',
    data,
    ...options,
  })
}

export function getInterfaceImportLogs(projectId, page = 1, pageSize = 20, filters = {}) {
  return request({
    url: '/interfaces/import-logs',
    method: 'get',
    params: {
      project_id: projectId,
      skip: (page - 1) * pageSize,
      limit: pageSize,
      ...filters,
    },
    skipSuccessToast: true,
    skipErrorToast: true,
  })
}

export function getInterfaceImportLogOperators(projectId) {
  return request({
    url: '/interfaces/import-logs/operators',
    method: 'get',
    params: { project_id: projectId },
    skipSuccessToast: true,
    skipErrorToast: true,
  })
}

export function getInterfaceImportLogItems(
  projectId,
  logId,
  itemType,
  page = 1,
  pageSize = 10,
  keyword = '',
) {
  return request({
    url: `/interfaces/import-logs/${logId}/items`,
    method: 'get',
    params: {
      project_id: projectId,
      item_type: itemType,
      keyword,
      skip: (page - 1) * pageSize,
      limit: pageSize,
    },
    skipSuccessToast: true,
    skipErrorToast: true,
  })
}

export function createInterfaceImportLog(data) {
  return request({
    url: '/interfaces/import-logs',
    method: 'post',
    data,
    skipSuccessToast: true,
    skipErrorToast: true,
  })
}
