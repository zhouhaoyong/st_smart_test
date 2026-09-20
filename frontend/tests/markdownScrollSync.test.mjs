import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  clampScrollTop,
  getEditorScrollTopForHeading,
  getSyncedScrollTopByRatio,
} from '../src/utils/markdownScrollSync.js'

test('markdown scroll sync keeps the same scroll ratio between editor and preview', () => {
  assert.equal(
    getSyncedScrollTopByRatio({
      sourceScrollTop: 900,
      sourceScrollHeight: 2400,
      sourceClientHeight: 600,
      targetScrollHeight: 3600,
      targetClientHeight: 600,
    }),
    1500,
  )

  assert.equal(
    getSyncedScrollTopByRatio({
      sourceScrollTop: 0,
      sourceScrollHeight: 1200,
      sourceClientHeight: 600,
      targetScrollHeight: 1800,
      targetClientHeight: 600,
    }),
    0,
  )
})

test('markdown scroll sync clamps to target scroll range', () => {
  assert.equal(clampScrollTop(9999, 1200, 400), 800)
  assert.equal(clampScrollTop(-10, 1200, 400), 0)
  assert.equal(clampScrollTop(100, 300, 400), 0)
})

test('toc heading click maps editor to the matching heading line', () => {
  assert.equal(getEditorScrollTopForHeading({ headingLine: 18, lineHeight: 22 }), 396)
  assert.equal(getEditorScrollTopForHeading({ headingLine: 0, lineHeight: 22 }), 0)
})
