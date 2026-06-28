/**
 * Token 混合存储工具
 *
 * 策略：sessionStorage（主，每标签页独立）+ localStorage（缓存，同源共享）
 * - 请求时优先读 sessionStorage，实现标签页间隔离
 * - 新标签页 sessionStorage 为空时降级读 localStorage 缓存并提升到 sessionStorage，
 *   实现自动继承上次登录
 * - 登录时双写，登出时仅清当前标签页（避免影响其他标签页）
 */

const ACCESS_KEY = 'accessToken'
const REFRESH_KEY = 'refreshToken'

/**
 * 读取当前标签页的 Access Token
 * sessionStorage 优先，为空则从 localStorage 缓存提升
 * @returns {string | null}
 */
export function getAccessToken() {
  let token = sessionStorage.getItem(ACCESS_KEY)
  if (!token) {
    // 新标签页：从 localStorage 缓存继承
    token = localStorage.getItem(ACCESS_KEY)
    if (token) {
      // 提升到 sessionStorage，实现本标签页后续隔离
      sessionStorage.setItem(ACCESS_KEY, token)
      sessionStorage.setItem(REFRESH_KEY, localStorage.getItem(REFRESH_KEY))
    }
  }
  return token
}

/**
 * 读取当前标签页的 Refresh Token
 * @returns {string | null}
 */
export function getRefreshToken() {
  let token = sessionStorage.getItem(REFRESH_KEY)
  if (!token) {
    token = localStorage.getItem(REFRESH_KEY)
    if (token) {
      sessionStorage.setItem(REFRESH_KEY, token)
      sessionStorage.setItem(ACCESS_KEY, localStorage.getItem(ACCESS_KEY))
    }
  }
  return token
}

/**
 * 保存 Token（同时写入 sessionStorage + localStorage 缓存）
 * @param {string} accessToken
 * @param {string} refreshToken
 */
export function setTokens(accessToken, refreshToken) {
  sessionStorage.setItem(ACCESS_KEY, accessToken)
  sessionStorage.setItem(REFRESH_KEY, refreshToken)
  localStorage.setItem(ACCESS_KEY, accessToken)
  localStorage.setItem(REFRESH_KEY, refreshToken)
}

/**
 * 清除当前标签页 Token（登出时调用）
 * 仅当 localStorage 缓存与当前 Token 一致时才清除缓存，避免影响其他标签页
 */
export function clearTokens() {
  const sessionAccess = sessionStorage.getItem(ACCESS_KEY)
  const cachedAccess = localStorage.getItem(ACCESS_KEY)

  sessionStorage.removeItem(ACCESS_KEY)
  sessionStorage.removeItem(REFRESH_KEY)

  // 仅当 localStorage 缓存的是同一账号时才清除
  if (sessionAccess === cachedAccess) {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  }
}
