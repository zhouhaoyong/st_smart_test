import request from '@/utils/request'

// 预览可清理的表
export function previewCleanup(mode = 'datetime', cutoff = null, days = 7, searchTable = '', searchChinese = '') {
  const params = { mode }
  if (mode === 'datetime' && cutoff) {
    params.cutoff = cutoff
  } else if (mode === 'days') {
    params.days = days
  }
  if (searchTable) {
    params.search_table = searchTable
  }
  if (searchChinese) {
    params.search_chinese = searchChinese
  }
  return request({ 
    url: '/cleanup/preview', 
    method: 'get',
    params,
    skipSuccessToast: true  // 跳过拦截器的 Toast，预览不需要提示
  })
}

// 查看指定表的待清理数据
export function previewTableData(tableName, mode = 'datetime', cutoff = null, days = 7) {
  const params = { mode }
  if (mode === 'datetime' && cutoff) {
    params.cutoff = cutoff
  } else if (mode === 'days') {
    params.days = days
  }
  return request({ 
    url: `/cleanup/preview/${tableName}`, 
    method: 'get',
    params,
    skipSuccessToast: true
  })
}

// 清理所有表的数据
export function cleanupData(mode = 'datetime', cutoff = null, days = 7, tableNames = []) {
  const params = { mode }
  if (mode === 'datetime' && cutoff) {
    params.cutoff = cutoff
  } else if (mode === 'days') {
    params.days = days
  }
  if (tableNames.length) {
    params.table_names = tableNames.join(',')
  }
  return request({ 
    url: '/cleanup/cleanup', 
    method: 'post',
    params,
    skipSuccessToast: true,  // 跳过拦截器的 Toast，由组件自己处理弹窗
    skipErrorToast: true
  })
}

// 清理单个表的数据
export function cleanupSingleTable(tableName, mode = 'datetime', cutoff = null, days = 7) {
  const params = { mode }
  if (mode === 'datetime' && cutoff) {
    params.cutoff = cutoff
  } else if (mode === 'days') {
    params.days = days
  }
  return request({ 
    url: `/cleanup/cleanup/${tableName}`, 
    method: 'post',
    params,
    skipSuccessToast: true,  // 跳过拦截器的 Toast，由组件自己处理弹窗
    skipErrorToast: true
  })
}
