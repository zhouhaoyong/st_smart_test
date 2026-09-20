import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = relativePath => fs.readFileSync(new URL(relativePath, import.meta.url), 'utf8')

test('用例卡片展示创建人和创建修改时间，不展示执行信息', () => {
  const source = read('../src/views/InterfaceCases.vue')
  const cardStart = source.indexOf('<el-card v-for="tc in cases"')
  const cardEnd = source.indexOf('</el-card>', cardStart)
  const card = source.slice(cardStart, cardEnd)

  assert.match(card, /class="card-creator"/)
  assert.match(card, /created_by_name/)
  assert.match(card, /created_by_avatar/)
  assert.match(card, /创建时间：\{\{\s*formatCaseTime\(tc\.created_at\)\s*\}\}/)
  assert.match(card, /修改时间：\{\{\s*formatCaseTime\(tc\.updated_at\)\s*\}\}/)
  assert.doesNotMatch(card, /last_run_at|last_run_status/)
})

test('接口编辑详情保留只读信息页签并将状态移到配置区', () => {
  const interfaceSource = read('../src/components/InterfaceEditDialog.vue')
  const caseSource = read('../src/components/TestCaseEditDialog.vue')
  const metadataSource = read('../src/components/RecordMetadataTable.vue')
  const infoTab = interfaceSource.match(/<el-tab-pane v-if="props\.showInfo && props\.model\.id" label="信息" name="info">([\s\S]*?)<\/el-tab-pane>/)?.[1] || ''

  assert.match(interfaceSource, /RecordMetadataTable/)
  assert.match(interfaceSource, /label="信息"/)
  assert.match(interfaceSource, /<template #status>[\s\S]*label="接口状态"[\s\S]*workflow_status/)
  assert.match(infoTab, /RecordMetadataTable/)
  assert.doesNotMatch(infoTab, /接口状态|workflow_status/)
  assert.match(caseSource, /RecordMetadataTable/)
  assert.match(caseSource, /label="信息"/)
  for (const label of ['ID', '创建人', '创建时间', '修改人', '修改时间']) {
    assert.match(metadataSource, new RegExp(label))
  }
})

test('用例编辑详情应按三行排列基础字段并将确认状态移到配置区', () => {
  const source = read('../src/components/TestCaseEditDialog.vue')
  const configTab = source.match(/<el-tab-pane label="配置" name="config">([\s\S]*?)<\/el-tab-pane>/)?.[1] || ''
  const infoTab = source.match(/<el-tab-pane v-if="props\.showInfo && hasPersistedMetadata" label="信息" name="info">([\s\S]*?)<\/el-tab-pane>/)?.[1] || ''
  const rows = configTab.match(/<el-row[\s\S]*?<\/el-row>/g) || []

  assert.equal(rows.length, 3, '用例详情基础字段应分为三行')
  assert.match(rows[0], /用例名称[\s\S]*?请求方法/)
  assert.match(rows[1], /URL[\s\S]*?优先级/)
  assert.match(rows[2], /描述[\s\S]*?model\.description[\s\S]*?:rows="1"[\s\S]*?确认状态[\s\S]*?model\.confirm_status/)
  assert.match(configTab, /<el-option label="待确认" value="pending" \/>[\s\S]*?<el-option label="已确认" value="confirmed" \/>/)
  assert.match(infoTab, /RecordMetadataTable/)
  assert.doesNotMatch(infoTab, /确认状态|confirm_status|confirm_reason/)
})

test('用例左侧接口列表按用例总数和待确认数量展示数字标签', () => {
  const source = read('../src/views/InterfaceCases.vue')
  const badgeSource = read('../src/components/CaseCountStatusBadge.vue')

  assert.match(source, /pending_test_case_count/, '接口列表应使用后端返回的待确认用例数量')
  assert.match(source, /<CaseCountStatusBadge[\s\S]*:count="iface\.test_case_count"[\s\S]*:pending-count="iface\.pending_test_case_count"/, '左侧应复用用例数量状态标签组件')
  assert.match(badgeSource, /v-if="normalizedCount > 0"/, '有用例时应展示总数量')
  assert.match(badgeSource, /normalizedPendingCount > 0 \? 'warning' : 'success'/, '待确认用例应使用警示颜色')
  assert.match(badgeSource, /v-else[^>]*case-count-status--empty/, '没有用例时应保持显示 0')
})

test('详情信息页使用接口返回的时间，并在缺少修改时间时回退到创建时间', () => {
  const interfacePage = read('../src/views/Interfaces.vue')
  const casesPage = read('../src/views/InterfaceCases.vue')
  const metadataSource = read('../src/components/RecordMetadataTable.vue')

  assert.match(interfacePage, /created_at:\s*source\.created_at[\s\S]*updated_at:\s*source\.updated_at/)
  assert.match(casesPage, /created_at:\s*res\.created_at[\s\S]*updated_at:\s*res\.updated_at/)
  assert.match(casesPage, /created_at:\s*detail\.created_at[\s\S]*updated_at:\s*detail\.updated_at/)
  assert.match(metadataSource, /formatTime\(record\.updated_at\s*\|\|\s*record\.created_at\)/)
})

test('AI 保存接口和用例时使用实际保存人作为创建人', () => {
  const persistSource = read('../../backend/services/ai_import/persist.py')

  assert.match(persistSource, /def _new_test_case\([\s\S]*created_by: int\)/)
  assert.match(persistSource, /created_by=created_by,\s*\n\s*updated_by=created_by/)
  assert.match(persistSource, /db\.add\(_new_test_case\([\s\S]*current_user\.real_name,\s*\n\s*current_user\.id/)
  assert.doesNotMatch(persistSource, /def _new_interface\(/, '当前 AI 保存流程只向既有接口追加用例，不应重新创建接口')
})

test('接口列表支持六种用例数比较条件并传递筛选参数', () => {
  const viewSource = read('../src/views/Interfaces.vue')
  const endpointSource = read('../../backend/api/v1/endpoints/interfaces.py')

  assert.match(viewSource, /searchCaseCountOperator/)
  assert.match(viewSource, /searchCaseCount/)
  const optionsStart = viewSource.indexOf('const caseCountOperators = [')
  const optionsEnd = viewSource.indexOf(']', optionsStart)
  const optionsSource = viewSource.slice(optionsStart, optionsEnd)
  const labels = ["'='", "'>'", "'≧'", "'<'", "'≦'", "'≠'"]
  for (let index = 0; index < labels.length; index += 1) {
    assert.match(optionsSource, new RegExp(`label:\\s*${labels[index]}`))
    if (index > 0) {
      assert.ok(
        optionsSource.indexOf(`label: ${labels[index - 1]}`) < optionsSource.indexOf(`label: ${labels[index]}`),
        `${labels[index]} 应排在 ${labels[index - 1]} 后面`,
      )
    }
  }
  assert.match(viewSource, /test_case_count_operator/)
  assert.match(viewSource, /test_case_count/)
  for (const operator of ['gt', 'gte', 'eq', 'lt', 'lte', 'ne']) {
    assert.match(endpointSource, new RegExp(`['"]${operator}['"]`))
  }
  assert.equal(
    (endpointSource.match(/"ne": case_count != test_case_count/g) || []).length,
    2,
    '普通列表查询和跨页全选查询都必须支持不等于条件',
  )
  assert.match(endpointSource, /TestCase\.is_deleted\s*==\s*False/)
})
