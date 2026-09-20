import { ElMessageBox } from 'element-plus'

/**
 * 二次确认删除弹窗
 * @param {string} name 要删除的内容名称
 * @param {string} label 类型标签，如"项目""环境""接口"
 * @returns {Promise<boolean>} true=确认删除, false=取消
 */
export function confirmDelete(name, label = '') {
  const subject = label ? `${label}「${name}」` : `「${name}」`
  return ElMessageBox.confirm(
    `确认删除${subject}？`,
    '确认删除',
    {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(() => true).catch(() => false)
}

/**
 * 二次确认终止 AI 任务
 * @returns {Promise<boolean>} true=确认终止, false=取消
 */
export function confirmCancelAiTask() {
  return ElMessageBox.confirm(
    '任务终止后将不会输出任何内容，是否确认终止？',
    '确认终止',
    {
      confirmButtonText: '确认终止',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(() => true).catch(() => false)
}
