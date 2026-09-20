import request from '@/utils/request'

// 获取接口集树
export function getCollectionTree(projectId) {
  return request({
    url: `/collections/tree/${projectId}`,
    method: 'get'
  })
}

// 获取接口集列表
export function getCollections(projectId, parentId = null) {
  return request({
    url: '/collections/',
    method: 'get',
    params: { project_id: projectId, parent_id: parentId }
  })
}

// 创建接口集
export function createCollection(data) {
  return request({
    url: '/collections/',
    method: 'post',
    data
  })
}

// 获取接口集详情
export function getCollection(id) {
  return request({
    url: `/collections/${id}`,
    method: 'get'
  })
}

// 更新接口集
export function updateCollection(id, data) {
  return request({
    url: `/collections/${id}`,
    method: 'put',
    data
  })
}

// 删除接口集
export function deleteCollection(id) {
  return request({
    url: `/collections/${id}`,
    method: 'delete'
  })
}

// 拖拽排序
export function reorderCollections(items) {
  return request({
    url: '/collections/reorder',
    method: 'put',
    data: { items }
  })
}

// 批量删除接口集
export function batchDeleteCollections(ids) {
  return request({
    url: '/collections/batch-delete',
    method: 'post',
    data: { ids }
  })
}

// 预览删除接口集影响
export function previewDeleteCollection(id) {
  return request({
    url: `/collections/${id}/delete-preview`,
    method: 'get'
  })
}
