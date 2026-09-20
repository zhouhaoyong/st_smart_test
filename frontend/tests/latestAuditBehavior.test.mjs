import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')

const requestTabs = read('../src/components/RequestConfigTabs.vue')
const executor = read('../../backend/api/v1/endpoints/executor.py')
const requestExecutor = read('../../backend/services/request_executor.py')
const assertions = read('../../backend/services/execution_engine/assertions.py')
const importApi = read('../../backend/api/v1/endpoints/import_api.py')
const schedulePolicies = read('../../backend/api/v1/endpoints/schedule_policies.py')
const parameterSets = read('../../backend/api/v1/endpoints/parameter_sets_routers/sets.py')
const backendExecutions = read('../../backend/api/v1/endpoints/executions.py')
const executions = read('../src/views/Executions.vue')

assert.match(requestTabs, /value="neq"/)
assert.doesNotMatch(requestTabs, /value="ne"/)
assert.match(requestTabs, /assertion\.enabled !== false/)
assert.doesNotMatch(executor, /ensure_business_code_assertion\(/)
assert.match(requestExecutor, /execution_engine\.assertions/)
assert.doesNotMatch(requestExecutor, /def run_assertions\(/)
// 别名归一的实现已收敛到统一映射表，护栏断言随之改为校验映射表，保持「ne / != 归一为 neq」的原意
assert.match(assertions, /_OPERATOR_ALIASES = \{"ne": "neq", "!=": "neq"/)
assert.match(importApi, /"enabled": True/)
assert.match(schedulePolicies, /"enabled_total"/)
assert.match(schedulePolicies, /if is_manager\(current_user\):\s+response_data\["default_max_references"\]/)
assert.match(backendExecutions, /"cron_expression": es\.cron_expression if is_manager\(current_user\) else None/)
assert.match(backendExecutions, /retry_count: int = Field\(default=0, ge=0, le=3\)/)
assert.match(backendExecutions, /retry_count: int \| None = Field\(default=None, ge=0, le=3\)/)
assert.match(executions, /schedulePolicyEnabledTotal/)
assert.match(parameterSets, /ensure_project_detail_access/)

console.log('latest audit behavior contract test ok')
