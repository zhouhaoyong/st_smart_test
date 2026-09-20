import request from '@/utils/request'

export function getSchedulePolicies(params = {}) {
  return request({
    url: '/schedule-policies/',
    method: 'get',
    params,
  })
}

export function createSchedulePolicy(data) {
  return request({
    url: '/schedule-policies/',
    method: 'post',
    data,
  })
}

export function updateSchedulePolicy(id, data) {
  return request({
    url: `/schedule-policies/${id}`,
    method: 'put',
    data,
  })
}

export function deleteSchedulePolicy(id) {
  return request({
    url: `/schedule-policies/${id}`,
    method: 'delete',
  })
}

export function getSchedulePolicyReferences(id) {
  return request({
    url: `/schedule-policies/${id}/references`,
    method: 'get',
  })
}

export function getSchedulePolicyLogs(id, params = {}) {
  return request({
    url: `/schedule-policies/${id}/logs`,
    method: 'get',
    params,
  })
}
