import request from '@/utils/request'

export function getNavigationApps(params = {}) {
  return request({ url: '/tools/navigation/apps', method: 'get', params })
}

export function getNavigationSystems(params = {}) {
  return request({ url: '/tools/navigation/systems', method: 'get', params })
}

export function getNavigationCreators() {
  return request({ url: '/tools/navigation/apps/creators', method: 'get' })
}

export function createNavigationApp(data) {
  return request({ url: '/tools/navigation/apps', method: 'post', data })
}

export function updateNavigationApp(id, data) {
  return request({ url: `/tools/navigation/apps/${id}`, method: 'put', data })
}

export function batchMoveNavigationApps(data) {
  return request({ url: '/tools/navigation/apps/batch/system', method: 'put', data })
}

export function batchDeleteNavigationApps(data) {
  return request({ url: '/tools/navigation/apps/batch', method: 'delete', data })
}

export function deleteNavigationApp(id) {
  return request({ url: `/tools/navigation/apps/${id}`, method: 'delete' })
}

export function createNavigationSystem(data) {
  return request({ url: '/tools/navigation/systems', method: 'post', data })
}

export function updateNavigationSystem(id, data) {
  return request({ url: `/tools/navigation/systems/${id}`, method: 'put', data })
}

export function deleteNavigationSystem(id) {
  return request({ url: `/tools/navigation/systems/${id}`, method: 'delete' })
}
