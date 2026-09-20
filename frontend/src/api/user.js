import request from '@/utils/request'

export function getProfile() {
  return request({ url: '/auth/me', method: 'get' })
}

export function updateProfile(data) {
  return request({ url: '/auth/profile', method: 'put', data })
}

export function changePassword(data) {
  return request({ url: '/auth/password', method: 'put', data })
}

export function getTokens() {
  return request({ url: '/auth/tokens/', method: 'get' })
}

export function createToken(data) {
  return request({ url: '/auth/tokens/', method: 'post', data })
}

export function revokeToken(id) {
  return request({ url: `/auth/tokens/${id}`, method: 'delete' })
}

export function getUsers(params = {}) {
  return request({ url: '/users/', method: 'get', params })
}

export function getUser(id) {
  return request({ url: `/users/${id}`, method: 'get' })
}

export function createUser(data) {
  return request({ url: '/users/', method: 'post', data })
}

export function updateUser(id, data) {
  return request({ url: `/users/${id}`, method: 'put', data })
}

export function resetUserPassword(id) {
  return request({ url: `/users/${id}/reset-password`, method: 'post', skipSuccessToast: true })
}

export function deleteUser(id) {
  return request({ url: `/users/${id}`, method: 'delete', skipSuccessToast: true })
}
