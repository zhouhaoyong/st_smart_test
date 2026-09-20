import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const modelPageSource = readFileSync(new URL('../src/views/admin/AiModels.vue', import.meta.url), 'utf8')
const schemaSource = readFileSync(new URL('../../backend/schemas/ai_schemas.py', import.meta.url), 'utf8')
const serviceSource = readFileSync(new URL('../../backend/services/ai_model_service.py', import.meta.url), 'utf8')
const providerSource = readFileSync(new URL('../../backend/llm/providers/openai_compat.py', import.meta.url), 'utf8')
const apiSource = readFileSync(new URL('../../backend/api/v1/endpoints/ai.py', import.meta.url), 'utf8')

assert.match(modelPageSource, /label="接口协议"/)
assert.match(modelPageSource, /value="openai-compat"/)
assert.match(modelPageSource, /value="responses"/)
assert.match(modelPageSource, /provider: 'openai-compat'/)
assert.match(modelPageSource, /form\.value\.provider/)
assert.match(schemaSource, /provider: str = "openai-compat"/)
assert.match(schemaSource, /provider: str \| None = None/)
assert.match(serviceSource, /wire_api=getattr\(model, "provider", "openai-compat"\)/)
assert.match(providerSource, /wire_api: str = "openai-compat"/)
assert.match(providerSource, /self\.endpoint_path = "\/responses" if self\.wire_api == "responses" else "\/chat\/completions"/)
assert.match(providerSource, /"instructions": system_prompt/)
assert.match(providerSource, /"input": user_text/)
assert.match(providerSource, /response\.output_text\.delta/)
assert.match(providerSource, /response\.reasoning_summary_text\.delta/)
assert.match(apiSource, /OpenAICompatProvider\(/)
assert.match(apiSource, /wire_api=provider_type/)

console.log('ai model protocol test ok')
