import request from '@/utils/request'

export function uploadFeedbackImage(file, config = {}) {
  const form = new FormData()
  form.append('file', file)
  return request.post('/feedbacks/upload-image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    ...config,
  })
}

export function createFeedback(data, options = {}) {
  return request({ url: '/feedbacks', method: 'post', data, ...options })
}

export function getFeedbacks(params) {
  return request({ url: '/feedbacks', method: 'get', params })
}

export function getFeedback(id) {
  return request({ url: `/feedbacks/${id}`, method: 'get' })
}

export function getFeedbackReminders() {
  return request({ url: '/feedbacks/reminders', method: 'get', skipSuccessToast: true })
}

export function replyFeedback(id, data, options = {}) {
  return request({ url: `/feedbacks/${id}/reply`, method: 'put', data, ...options })
}

export function resolveFeedback(id, data, options = {}) {
  return request({ url: `/feedbacks/${id}/resolve`, method: 'put', data, ...options })
}

export function confirmCloseFeedback(id, options = {}) {
  return request({ url: `/feedbacks/${id}/confirm-close`, method: 'put', ...options })
}

export function reopenFeedback(id, data = {}, options = {}) {
  return request({ url: `/feedbacks/${id}/reopen`, method: 'put', data, ...options })
}

export function deleteFeedback(id, options = {}) {
  return request({ url: `/feedbacks/${id}`, method: 'delete', ...options })
}
