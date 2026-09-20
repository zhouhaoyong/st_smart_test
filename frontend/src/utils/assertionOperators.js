const OPERATOR_LABELS = Object.freeze({
  eq: '==',
  ne: '!=',
  neq: '!=',
  gt: '>',
  lt: '<',
  gte: '>=',
  lte: '<=',
  contains: '包含',
  not_empty: '非空',
  is_empty: '为空',
})

/** 只看实际值本身、不需要期望值的操作符 */
const OPERATORS_WITHOUT_EXPECTED = Object.freeze(['not_empty', 'is_empty'])

export function getAssertionOperatorLabel(operator) {
  const key = String(operator || '').trim()
  return OPERATOR_LABELS[key] || key || '-'
}

/** 该操作符是否需要填写期望值 */
export function assertionOperatorNeedsExpected(operator) {
  return !OPERATORS_WITHOUT_EXPECTED.includes(String(operator || '').trim())
}
