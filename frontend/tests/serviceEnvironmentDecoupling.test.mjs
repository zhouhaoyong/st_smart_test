import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  normalizeServiceKey,
  getEnvironmentServices,
  resolveServiceSelection,
  formatServiceOptionLabel,
  matchServiceFromUrl,
} from '../src/utils/serviceEnvironment.js'

const environmentSource = readFileSync(new URL('../src/views/Environments.vue', import.meta.url), 'utf8')
const environmentText = environmentSource.replace(/<[^>]+>/g, '')
const interfaceSource = readFileSync(new URL('../src/views/Interfaces.vue', import.meta.url), 'utf8')

test('服务标识应保留空白之外的稳定值', () => {
  assert.equal(normalizeServiceKey('  user-center  '), 'user-center')
  assert.equal(normalizeServiceKey(''), null)
  assert.equal(normalizeServiceKey(null), null)
})

test('环境没有该服务时仍保留服务标识，不把它当成无服务', () => {
  const environment = {
    service_config: {
      items: [],
    },
  }

  assert.deepEqual(resolveServiceSelection('user-center', environment), {
    key: 'user-center',
    status: 'missing',
    service: null,
  })
})

test('服务选项应包含当前环境中的标识，即使服务停用或尚未填写路径', () => {
  const environment = {
    service_config: {
      items: [
        { key: 'user-center', name: '用户中心', enabled: false, path_prefix: '' },
        { key: 'order-service', name: '订单服务', enabled: true, path_prefix: '/order' },
      ],
    },
  }

  assert.deepEqual(getEnvironmentServices(environment).map(item => item.key), [
    'user-center',
    'order-service',
  ])
})

test('停用服务只影响当前环境解析状态，不清空服务标识', () => {
  const environment = {
    service_config: {
      items: [
        { key: 'user-center', name: '用户中心', enabled: false, path_prefix: '/user' },
      ],
    },
  }

  assert.deepEqual(resolveServiceSelection('user-center', environment), {
    key: 'user-center',
    status: 'disabled',
    service: environment.service_config.items[0],
  })
})

test('环境服务编辑不再把接口和用例引用当成当前环境关联', () => {
  assert.doesNotMatch(environmentSource, /getEnvironmentServiceUsage/)
  assert.doesNotMatch(environmentSource, /本次修改会影响接口/)
  assert.match(environmentSource, /接口和用例中的服务标识不会被删除/)
})

test('服务配置使用说明只保留环境解析核心规则', () => {
  assert.match(environmentText, /服务配置用于为当前环境设置服务的路径前缀和认证方式。接口和用例只保存服务标识，不绑定具体环境。/)
  assert.match(environmentText, /请求地址 = 当前环境基础 URL \+ 服务路径前缀 \+ 接口路径。/)
  assert.match(environmentText, /当前环境没有该服务或服务未启用时，不拦截请求，直接按“基础 URL \+ 接口路径”执行。/)
  assert.match(environmentText, /服务未绑定认证时使用环境默认认证。服务配置只影响当前环境，不会修改接口和用例中的服务标识。/)
  assert.doesNotMatch(environmentText, /导入接口时，当前环境的服务配置只用于辅助匹配/)
  assert.doesNotMatch(environmentText, /删除服务配置只影响当前环境，不会删除接口和用例中的服务标识/)
})

test('服务标识输入在当前环境缺少配置时仍可编辑', () => {
  assert.match(interfaceSource, /allow-create filterable/)
  assert.doesNotMatch(interfaceSource, /:disabled="!environmentServices\.length"/)
})

test('服务展示和 URL 匹配应使用统一规则', () => {
  assert.equal(formatServiceOptionLabel({ key: 'user-center', name: '用户中心', path_prefix: '' }), '用户中心（当前环境未配置路径）')

  const services = [
    { key: 'api', name: 'API', enabled: true, path_prefix: '/api' },
    { key: 'order', name: '订单', enabled: true, path_prefix: '/api/order' },
    { key: 'disabled', name: '停用服务', enabled: false, path_prefix: '/disabled' },
  ]

  assert.deepEqual(matchServiceFromUrl('https://example.com/base/api/order/list?id=1', services, 'https://example.com/base'), {
    service_key: 'order',
    url: '/list?id=1',
  })
  assert.deepEqual(matchServiceFromUrl('/api/unknown', services), {
    service_key: 'api',
    url: '/unknown',
  })
  assert.deepEqual(matchServiceFromUrl('/disabled/list', services), {
    service_key: null,
    url: '/disabled/list',
  })
})
