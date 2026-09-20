import request from '@/utils/request'

const BASE = '/message-config'

export function getMessageChannels(params = {}) {
  return request.get(`${BASE}/channels`, { params })
}

export function getMessageChannelOptions(params = {}) {
  return request.get(`${BASE}/channels/options`, { params, paramsSerializer: { indexes: null } })
}

export function getMessageChannel(id) {
  return request.get(`${BASE}/channels/${id}`)
}

export function getMessageChannelReferences(id) {
  return request.get(`${BASE}/channels/${id}/references`)
}

export function createMessageChannel(data) {
  return request.post(`${BASE}/channels`, data)
}

export function updateMessageChannel(id, data) {
  return request.put(`${BASE}/channels/${id}`, data)
}

export function deleteMessageChannel(id, config = {}) {
  return request.delete(`${BASE}/channels/${id}`, config)
}

export function testMessageChannel(id) {
  return request.post(`${BASE}/channels/${id}/test`)
}

export function testTempMessageChannel(data) {
  return request.post(`${BASE}/channels/test`, data)
}

export function getMessageTemplates(params = {}) {
  return request.get(`${BASE}/templates`, { params })
}

export function getMessageTemplateOptions(params = {}) {
  return request.get(`${BASE}/templates/options`, { params, paramsSerializer: { indexes: null } })
}

export function getMessageTemplate(id) {
  return request.get(`${BASE}/templates/${id}`)
}

export function createMessageTemplate(data) {
  return request.post(`${BASE}/templates`, data)
}

export function updateMessageTemplate(id, data) {
  return request.put(`${BASE}/templates/${id}`, data)
}

export function deleteMessageTemplate(id) {
  return request.delete(`${BASE}/templates/${id}`)
}

export function getDefaultMessageTemplates() {
  return request.get(`${BASE}/templates/defaults`)
}

export function getMessageBindings(params = {}) {
  return request.get(`${BASE}/bindings`, { params })
}

export function saveMessageBinding(data) {
  return request.post(`${BASE}/bindings`, data)
}
