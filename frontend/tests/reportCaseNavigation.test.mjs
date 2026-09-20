import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const reports = read('../src/views/Reports.vue')
const interfaceCases = read('../src/views/InterfaceCases.vue')
const router = read('../src/router/index.js')

assert.match(reports, /<div class="case-card-header" @click="toggleCaseGroup\(group, gi\)">/)
assert.match(reports, /<span class="case-name">/)
assert.match(reports, /class="case-link-button"[\s\S]*@click\.stop="jumpToTestCase\(group\)"[\s\S]*查看用例/)
const caseTitleAreaStart = reports.indexOf('<div class="case-title-area">')
const caseHeaderEnd = reports.indexOf('</template>', caseTitleAreaStart)
const caseTitleArea = reports.slice(caseTitleAreaStart, caseHeaderEnd)
assert.ok(caseTitleArea.indexOf('class="case-name"') < caseTitleArea.indexOf('class="case-link-button"'))
assert.ok(caseTitleArea.indexOf('class="case-link-button"') < caseTitleArea.indexOf('case-status-pill'))
assert.match(reports, /v-if="canJumpToTestCase\(group\)"/)
assert.match(reports, /v-else class="case-link-button case-link-button--disabled"/)
assert.match(reports, /用例已删除/)
assert.doesNotMatch(reports, /<span class="case-name clickable-title"[^>]*@click\.stop="jumpToTestCase\(group\)"/)
assert.match(reports, /const jumpToTestCase = \(group\) => \{[\s\S]*group\?\.test_case_id[\s\S]*group\?\.interface_id[\s\S]*name: 'InterfaceCases'/)
assert.match(reports, /const canJumpToTestCase = \(group\) =>[\s\S]*test_case_deleted[\s\S]*interface_deleted/)
assert.doesNotMatch(reports, /router\.push\(`\/project\/\$\{projectId\.value\}\/testcases\?tc=/)
const caseNameRule = reports.match(/\.case-name\s*\{[^}]+\}/)?.[0] || ''
assert.match(caseNameRule, /flex:\s*0\s+1\s+auto/)
assert.doesNotMatch(caseNameRule, /flex:\s*1\s*[;}]/)

const statsBlockStart = reports.indexOf('/* 统计卡片 */')
const statsBlockEnd = reports.indexOf('/* 用例卡片 */', statsBlockStart)
const statsBlock = reports.slice(statsBlockStart, statsBlockEnd)
assert.match(statsBlock, /\.stat-card\s*\{[\s\S]*padding:\s*16px 20px/)
assert.match(statsBlock, /\.stat-card--total\s*\{[\s\S]*background:\s*linear-gradient/)
assert.match(statsBlock, /\.stat-card--passed\s*\{[\s\S]*background:\s*linear-gradient/)
assert.match(statsBlock, /\.stat-card--failed\s*\{[\s\S]*background:\s*linear-gradient/)
assert.match(statsBlock, /\.stat-card--rate\s*\{[\s\S]*background:\s*linear-gradient/)

const detailQueryBar = reports.match(/\.detail-query-bar\s*\{[^}]+\}/)?.[0] || ''
assert.match(detailQueryBar, /background:\s*#f5f7fa/)
assert.match(detailQueryBar, /border:\s*1px solid/)
assert.match(detailQueryBar, /border-radius:\s*8px/)
assert.match(detailQueryBar, /padding:\s*10px 12px/)
assert.match(detailQueryBar, /flex-wrap:\s*wrap/)

assert.match(router, /path: 'project\/:[^']+\/interfaces\/:iid\/cases'[\s\S]*name: 'InterfaceCases'/)
assert.match(interfaceCases, /const routeCaseId = Number\(route\.query\.tc\)/)
assert.match(interfaceCases, /const target = cases\.value\.find\(tc => tc\.id === routeCaseId\)/)
assert.match(interfaceCases, /openEdit\(target\)/)
assert.match(interfaceCases, /openEdit\(target\)[\s\S]*router\.replace\(\{ query: \{\} \}\)/)

assert.match(reports, /section === 'request' \? 'auto' : 'body'/)
assert.match(reports, /const requestBodyText = \(body\) =>[\s\S]*formatBody\(body\)/)
assert.match(reports, /:body-text="requestBodyText\(step\.request_data\?\.body\)"/)

console.log('report case navigation test ok')
