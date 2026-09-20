import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login, logout as requestLogout, getCurrentUser } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  const savedToken = localStorage.getItem('access_token') || ''
  const savedUser = localStorage.getItem('user_info')
  let initialUser = null
  let initialToken = savedToken
  if (savedUser) {
    try {
      initialUser = JSON.parse(savedUser)
    } catch {
      localStorage.removeItem('user_info')
      localStorage.removeItem('access_token')
      initialToken = ''
    }
  }
  const token = ref(initialToken)
  const userInfo = ref(initialUser)

  // 登录
  const userLogin = async (loginForm) => {
    try {
      const res = await login(loginForm)
      token.value = res.access_token
      localStorage.setItem('access_token', res.access_token)
      
      // 获取用户信息
      await getUserInfo()
      
      return true
    } catch (error) {
      return false
    }
  }

  // 获取用户信息
  const getUserInfo = async () => {
    try {
      const res = await getCurrentUser()
      userInfo.value = res
      localStorage.setItem('user_info', JSON.stringify(res))
      return res
    } catch (error) {
      console.error('获取用户信息失败', error)
      return null
    }
  }

  // 登出
  const logout = async () => {
    try {
      await requestLogout()
    } catch (error) {
      // 退出接口失败时仍清理本地登录态，避免用户被困在当前账号。
      console.warn('退出登录审计记录失败', error)
    }
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
    // 退出提示以后端返回的 message 为准，这里不再重复提示
  }

  return {
    token,
    userInfo,
    userLogin,
    getUserInfo,
    logout
  }
})
