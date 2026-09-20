import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import esbuild from 'esbuild'
import fs from 'fs'

const files = [
  'src/views/test-workbench/components/RefinementAnswerBox.vue',
  'src/views/test-workbench/components/RefinementComposePreview.vue',
  'src/views/test-workbench/components/RefinementMessageCard.vue',
  'src/views/test-workbench/components/AiConversationFrame.vue',
  'src/views/test-workbench/components/AiModelSelectionPanel.vue',
  'src/views/test-workbench/components/AiRetryModelDialog.vue',
  'src/views/test-workbench/components/RefinementStartConfirm.vue',
  'src/views/test-workbench/components/RefinementQuestionGroups.vue',
  'src/views/test-workbench/components/RequirementRefinementDrawer.vue',
  'src/views/test-workbench/components/MergedRequirementCreateDialog.vue',
  'src/views/AuditLogs.vue',
]
let ok = true
for (const f of files) {
  try {
    const src = fs.readFileSync(f, 'utf8')
    const { descriptor, errors } = parse(src, { filename: f })
    if (errors.length) throw new Error(errors.map(e=>e.message).join('; '))
    const id = 'x'
    if (descriptor.script || descriptor.scriptSetup) compileScript(descriptor, { id })
    if (descriptor.template) {
      const r = compileTemplate({ source: descriptor.template.content, filename: f, id })
      if (r.errors.length) throw new Error(r.errors.map(e=>e.message||e).join('; '))
    }
    console.log('OK  ', f)
  } catch (e) {
    ok = false
    console.log('FAIL', f, '->', e.message)
  }
}
// JS files via esbuild
for (const f of ['src/api/testWorkbench.js','src/views/test-workbench/composables/useRequirementRefinement.js','src/views/test-workbench/pages/WorkbenchMergedRequirementPage.vue']) {
  if (f.endsWith('.js')) {
    try { esbuild.transformSync(fs.readFileSync(f,'utf8'), { loader:'js' }); console.log('OK  ', f) }
    catch(e){ ok=false; console.log('FAIL', f, e.message) }
  }
}
process.exit(ok?0:1)
