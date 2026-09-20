import request from '../utils/request'

export function getParameterSets(projectId, page, pageSize, filters = {}) {
  return request({
    url: '/parameter-sets/',
    method: 'get',
    params: {
      project_id: projectId,
      skip: page ? (page - 1) * (pageSize || 10) : 0,
      limit: pageSize || 100,
      ...(filters.name ? { name: filters.name } : {})
    }
  })
}

export function createParameterSet(data, options = {}) {
  return request({
    url: '/parameter-sets/',
    method: 'post',
    data,
    ...options
  })
}

export function getParameterSet(id, options = {}) {
  return request({
    url: `/parameter-sets/${id}`,
    method: 'get',
    params: options.includeItems === false ? { include_items: false } : undefined
  })
}

export function getParameterSetItems(id, page = 1, pageSize = 10, filters = {}) {
  return request({
    url: `/parameter-sets/${id}/items`,
    method: 'get',
    params: {
      skip: Math.max(0, page - 1) * pageSize,
      limit: pageSize,
      ...(filters.name ? { name: filters.name } : {}),
      ...(filters.key ? { key: filters.key } : {}),
      ...(filters.value ? { value: filters.value } : {})
    }
  })
}

export function batchDeleteParameterItems(id, data, options = {}) {
  return request({
    url: `/parameter-sets/${id}/items/batch-delete`,
    method: 'post',
    data,
    ...options
  })
}

export function updateParameterSet(id, data, options = {}) {
  return request({
    url: `/parameter-sets/${id}`,
    method: 'put',
    data,
    ...options
  })
}

export function deleteParameterSet(id) {
  return request({
    url: `/parameter-sets/${id}`,
    method: 'delete'
  })
}

export function copyParameterSet(id) {
  return request({
    url: `/parameter-sets/${id}/copy`,
    method: 'post'
  })
}

export function searchValues(projectId, searchValue, matchKey, paramType, options = {}) {
  return request({
    url: '/parameter-sets/search-values',
    method: 'get',
    params: {
      project_id: projectId,
      search_value: searchValue,
      ...(matchKey ? { match_key: matchKey } : {}),
      ...(paramType ? { param_type: paramType } : {}),
      include_headers: !!options.includeHeaders,
      ...(options.sourceKeyword ? { source_keyword: options.sourceKeyword } : {})
    }
  })
}

export function batchReplace(data, options = {}) {
  return request({
    url: '/parameter-sets/batch-replace',
    method: 'post',
    data,
    ...options
  })
}

export function detectParameterCandidates(projectId, options = {}) {
  return request({
    url: '/parameter-sets/detect-candidates',
    method: 'get',
    params: {
      project_id: projectId,
      ...(Array.isArray(options.locations) ? { locations: options.locations.length ? options.locations : ['none'] } : {}),
      ...(options.keyword ? { keyword: options.keyword } : {})
    },
    paramsSerializer: { indexes: null },
  })
}

export function addItem(psId, data, options = {}) {
  return request({
    url: `/parameter-sets/${psId}/items`,
    method: 'post',
    data,
    ...options
  })
}

export function batchAddParameterItems(psId, data, options = {}) {
  return request({
    url: `/parameter-sets/${psId}/items/batch`,
    method: 'post',
    data,
    ...options
  })
}

export function updateItem(psId, itemId, data) {
  return request({
    url: `/parameter-sets/${psId}/items/${itemId}`,
    method: 'put',
    data
  })
}

export function getItemReferences(psId, itemId) {
  return request({
    url: `/parameter-sets/${psId}/items/${itemId}/references`,
    method: 'get'
  })
}

export function deleteItem(psId, itemId, options = {}) {
  return request({
    url: `/parameter-sets/${psId}/items/${itemId}`,
    method: 'delete',
    params: options.force ? { force: true } : undefined
  })
}
