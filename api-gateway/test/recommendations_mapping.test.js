import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function loadMapper() {
  // api-gateway/src/index.js doesn't export mapStockRecommendationRow.
  // For testing, we eval the file in a sandbox and extract the function.
  // This keeps the test lightweight and avoids restructuring production code.
  const code = readFileSync(new URL('../src/index.js', import.meta.url), 'utf8')

  // strip ESM imports to avoid module resolution in vm
  const stripped = code
    .split('\n')
    .filter((line) => !line.startsWith('import '))
    .join('\n')

  const sandbox = {
    console,
    process: { env: {} },
    // minimal stubs for symbols referenced during file evaluation
    express: () => ({ get() {}, post() {}, use() {}, listen() {} }),
  }

  vm.createContext(sandbox)

  // Only execute the portion defining mapStockRecommendationRow.
  const start = stripped.indexOf('function mapStockRecommendationRow')
  assert.ok(start >= 0, 'mapStockRecommendationRow not found')
  const end = stripped.indexOf('app.get(\'/api/v1/recommendations\'')
  assert.ok(end > start, 'Could not find end of mapper section')

  vm.runInContext(stripped.slice(start, end), sandbox)
  assert.equal(typeof sandbox.mapStockRecommendationRow, 'function')
  return sandbox.mapStockRecommendationRow
}

test('mapStockRecommendationRow derives normalizedScore when legacy fields are null but split/component fields exist', () => {
  const mapStockRecommendationRow = loadMapper()

  const row = {
    id: '00000000-0000-0000-0000-000000000000',
    symbol: 'AAPL',

    // legacy combined missing
    action: null,
    score: null,
    normalized_score: null,
    confidence: null,

    // split scores present
    news_normalized_score: 0.9,
    technical_normalized_score: 0.7,

    // component raw scores present (preferred)
    news_sentiment_score: 0.8, // (-1..1)
    news_momentum_score: 0.2,
    technical_trend_score: -0.1,
    technical_momentum_score: 0.3,

    explanation: {
      // could include signal weights; omit to use defaults
    },
  }

  const mapped = mapStockRecommendationRow(row)

  assert.equal(mapped.symbol, 'AAPL')
  assert.equal(mapped.action, 'HOLD')

  // Derived from component weighted average:
  // weights: 0.3,0.2,0.25,0.25 => raw = 0.3*0.8 + 0.2*0.2 + 0.25*(-0.1) + 0.25*0.3 = 0.33
  // normalized = (0.33+1)/2 = 0.665
  assert.ok(mapped.normalizedScore !== null)
  assert.ok(Math.abs(mapped.normalizedScore - 0.665) < 1e-6)

  // Also ensure score (raw) is set when derived
  assert.ok(mapped.score !== null)
  assert.ok(Math.abs(mapped.score - 0.33) < 1e-6)
})
