import assert from 'node:assert/strict'

import { copyToClipboard } from '../src/utils/clipboard.js'

const originalNavigator = globalThis.navigator
const originalWindow = globalThis.window
const originalDocument = globalThis.document

function installBrowser({ secure, writeText, execCommand }) {
  const body = {
    appendChild(element) { element.parentNode = body },
    removeChild(element) { element.parentNode = null },
  }
  const document = {
    body,
    createElement() {
      return {
        style: {},
        setAttribute() {},
        select() {},
        setSelectionRange() {},
      }
    },
    execCommand,
  }
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: { clipboard: writeText ? { writeText } : undefined },
  })
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { isSecureContext: secure } })
  Object.defineProperty(globalThis, 'document', { configurable: true, value: document })
}

try {
  const writes = []
  installBrowser({
    secure: true,
    writeText: async text => writes.push(text),
    execCommand: () => false,
  })
  assert.equal(await copyToClipboard('安全上下文'), true)
  assert.deepEqual(writes, ['安全上下文'])

  let fallbackValue = ''
  installBrowser({
    secure: true,
    writeText: async () => { throw new Error('permission denied') },
    execCommand: command => {
      assert.equal(command, 'copy')
      fallbackValue = '降级复制'
      return true
    },
  })
  assert.equal(await copyToClipboard('降级复制'), true)
  assert.equal(fallbackValue, '降级复制')

  installBrowser({ secure: false, execCommand: () => true })
  assert.equal(await copyToClipboard('非安全上下文'), true)
} finally {
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: originalNavigator })
  Object.defineProperty(globalThis, 'window', { configurable: true, value: originalWindow })
  Object.defineProperty(globalThis, 'document', { configurable: true, value: originalDocument })
}

console.log('clipboard helpers passed')
