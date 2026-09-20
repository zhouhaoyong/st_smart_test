import request from '@/utils/request'

// 用户登录
export const login = (data) => {
  return request({
    url: '/auth/login',
    method: 'post',
    data: {
      username: data.username,
      password: data.password,
      remember_me: data.remember_me || false,
    }
  })
}

// 用户注册
export const register = (data) => {
  return request({
    url: '/auth/register',
    method: 'post',
    data: data
  })
}

// 获取当前用户信息
export const getCurrentUser = () => {
  return request({
    url: '/auth/me',
    method: 'get'
  })
}

// 记录用户主动退出登录
export const logout = () => {
  return request({
    url: '/auth/logout',
    method: 'post'
  })
}
