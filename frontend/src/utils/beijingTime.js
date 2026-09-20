/** Beijing time formatter: YYYY-MM-DD HH:mm:ss */
export function formatBeijingTime(d) {
  if (!d) return ''
  const dt = new Date(d)
  const bj = new Date(dt.toLocaleString('en-US', { timeZone: 'Asia/Shanghai' }))
  const pad = (n) => String(n).padStart(2, '0')
  return `${bj.getFullYear()}-${pad(bj.getMonth() + 1)}-${pad(bj.getDate())} ${pad(bj.getHours())}:${pad(bj.getMinutes())}:${pad(bj.getSeconds())}`
}

export function formatBeijingMinute(d) {
  const value = formatBeijingTime(d)
  return value ? value.slice(0, 16) : ''
}

export function formatBeijingDate(d) {
  const value = formatBeijingTime(d)
  return value ? value.slice(0, 10) : ''
}
