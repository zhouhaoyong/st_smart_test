import request from '@/utils/request'

// 获取通知配置列表
export function getNotificationConfigs() {
  return request({
    url: '/notifications/',
    method: 'get'
  })
}

// 获取通知配置详情（包含完整秘钥，用于编辑）
export function getNotificationConfig(id) {
  return request({
    url: `/notifications/${id}`,
    method: 'get'
  })
}

// 创建通知配置
export function createNotificationConfig(data) {
  return request({
    url: '/notifications/',
    method: 'post',
    data
  })
}

// 更新通知配置
export function updateNotificationConfig(id, data) {
  return request({
    url: `/notifications/${id}`,
    method: 'put',
    data
  })
}

// 删除通知配置
export function deleteNotificationConfig(id) {
  return request({
    url: `/notifications/${id}`,
    method: 'delete'
  })
}

// 测试通知发送（已保存的配置）
export function testNotification(id) {
  return request({
    url: `/notifications/${id}/test`,
    method: 'post'
  })
}

// 测试通知发送（使用表单数据，无需保存）
export function testNotificationWithData(data) {
  return request({
    url: '/notifications/test',
    method: 'post',
    data
  })
}
