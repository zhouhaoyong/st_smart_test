function splitLines(text) {
  return String(text ?? '').split('\n')
}

function lineAt(lines, index) {
  if (index < 0 || index >= lines.length) return null
  return { number: index + 1, content: lines[index] }
}

export function buildLineDiffRows(diffs = [], leftText = '', rightText = '') {
  const leftLines = splitLines(leftText)
  const rightLines = splitLines(rightText)
  const rows = []

  diffs.forEach((diff, diffIndex) => {
    const leftCount = Math.max(0, diff.left_end - diff.left_start)
    const rightCount = Math.max(0, diff.right_end - diff.right_start)
    const rowCount = Math.max(leftCount, rightCount)

    for (let offset = 0; offset < rowCount; offset += 1) {
      const left = offset < leftCount ? lineAt(leftLines, diff.left_start + offset) : null
      const right = offset < rightCount ? lineAt(rightLines, diff.right_start + offset) : null
      rows.push({
        diffIndex,
        type: left && right ? 'replace' : left ? 'delete' : 'insert',
        left,
        right,
      })
    }
  })

  return rows
}

export function getLineDiffSummary(rows = []) {
  return rows.reduce((summary, row) => {
    if (row.type === 'insert') summary.insert += 1
    else if (row.type === 'delete') summary.delete += 1
    else summary.replace += 1
    return summary
  }, { insert: 0, delete: 0, replace: 0 })
}

export function getCharacterRangeLabel(text, start, end) {
  const source = String(text ?? '')
  const safeStart = Math.min(Math.max(Number(start) || 0, 0), source.length)
  const safeEnd = Math.min(Math.max(Number(end) || safeStart, safeStart), source.length)
  const before = source.slice(0, safeStart)
  const line = (before.match(/\n/g) || []).length + 1
  const column = safeStart - before.lastIndexOf('\n')

  if (safeStart === safeEnd) return `第 ${line} 行第 ${column} 个字符后`

  const selected = source.slice(safeStart, safeEnd)
  const endLine = line + (selected.match(/\n/g) || []).length
  return endLine === line ? `第 ${line} 行第 ${column} 个字符起` : `第 ${line}-${endLine} 行`
}
