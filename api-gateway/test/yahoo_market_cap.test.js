import test from 'node:test';
import assert from 'node:assert/strict';

import { parseMarketCapFromYahooQuoteHtml } from '../src/yahooFinance.js';

// Note: fetchYahooMarketCap() uses live network (quoteSummary + HTML). We keep tests unit-level only.

test('parseMarketCapFromYahooQuoteHtml - raw value', () => {
  const html = '<script>var x={"marketCap":{"raw":1234567890,"fmt":"1.23B"}}</script>';
  assert.equal(parseMarketCapFromYahooQuoteHtml(html), 1234567890);
});

test('parseMarketCapFromYahooQuoteHtml - fmt value', () => {
  const html = '<script>var x={"marketCap":{"fmt":"2.50T"}}</script>';
  assert.equal(parseMarketCapFromYahooQuoteHtml(html), 2.5e12);
});

test('parseMarketCapFromYahooQuoteHtml - unknown returns null', () => {
  const html = '<html><body>No market cap here</body></html>';
  assert.equal(parseMarketCapFromYahooQuoteHtml(html), null);
});
