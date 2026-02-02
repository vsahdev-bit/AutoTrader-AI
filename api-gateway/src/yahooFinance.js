// Yahoo Finance helpers for scraping data not present in the chart meta.
//
// NOTE: We prefer official Yahoo endpoints where possible, but marketCap is
// occasionally missing from the v8/finance/chart meta. In those cases we
// fall back to scraping the public quote page.

const DEFAULT_TTL_MS = 6 * 60 * 60 * 1000; // 6 hours

// In-memory cache (per process)
const marketCapCache = new Map(); // symbol -> { value: number|null, expiresAt: number }

// Deduplicate concurrent requests per symbol
const inFlight = new Map(); // symbol -> Promise<number|null>

function parseAbbrevNumber(value) {
  if (value == null) return null;
  if (typeof value === 'number' && Number.isFinite(value)) return value;

  const s = String(value).trim();
  if (!s) return null;

  // Remove commas
  const cleaned = s.replace(/,/g, '');

  // Match e.g. 2.34T, 510.2B, 900M, 12.3K
  const m = cleaned.match(/^(-?\d+(?:\.\d+)?)([TMBK])?$/i);
  if (!m) return null;

  const num = Number(m[1]);
  if (!Number.isFinite(num)) return null;

  const unit = (m[2] || '').toUpperCase();
  const mult = unit === 'T' ? 1e12 : unit === 'B' ? 1e9 : unit === 'M' ? 1e6 : unit === 'K' ? 1e3 : 1;
  return num * mult;
}

export function parseMarketCapFromYahooQuoteHtml(html) {
  if (!html || typeof html !== 'string') return null;

  // 1) Best case: JSON blob contains a raw market cap.
  //    Example: "marketCap":{"raw":123456789,"fmt":"123.46B"}
  const rawMatch = html.match(/"marketCap"\s*:\s*\{[^}]*?"raw"\s*:\s*(\d+(?:\.\d+)?)/);
  if (rawMatch) {
    const n = Number(rawMatch[1]);
    return Number.isFinite(n) ? n : null;
  }

  // 2) Next: JSON blob has only fmt.
  const fmtMatch = html.match(/"marketCap"\s*:\s*\{[^}]*?"fmt"\s*:\s*"([^"]+)"/);
  if (fmtMatch) {
    return parseAbbrevNumber(fmtMatch[1]);
  }

  // 3) Last resort: try to read the Summary table string value.
  //    Yahoo markup changes frequently; keep this intentionally loose.
  const tableMatch = html.match(/Market\s*Cap\s*\(intraday\)[\s\S]{0,500}?>\s*([0-9.,]+\s*[TMBK]?)/i);
  if (tableMatch) {
    return parseAbbrevNumber(tableMatch[1].replace(/\s+/g, ''));
  }

  return null;
}

async function fetchYahooMarketCapFromV7Quote(sym) {
  // Common backing endpoint used by the quote page for quick quote fields.
  // Returns marketCap for most equities.
  const url = `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${encodeURIComponent(sym)}`;
  const response = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'application/json',
    },
  });

  if (!response.ok) return null;

  const data = await response.json();
  const quote = data?.quoteResponse?.result?.[0];
  const mc = quote?.marketCap;
  return mc != null && Number.isFinite(Number(mc)) ? Number(mc) : null;
}

async function fetchYahooMarketCapFromQuoteSummary(sym) {
  // This endpoint is what the quote page uses under the hood.
  // We keep it as a "quote page" source, but JSON is far more stable than scraping HTML.
  const url = `https://query1.finance.yahoo.com/v10/finance/quoteSummary/${encodeURIComponent(sym)}?modules=price`;
  const response = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'application/json',
    },
  });

  if (!response.ok) return null;

  const data = await response.json();
  const marketCap = data?.quoteSummary?.result?.[0]?.price?.marketCap;
  // marketCap can be: { raw, fmt, longFmt }
  if (marketCap?.raw != null && Number.isFinite(Number(marketCap.raw))) return Number(marketCap.raw);
  if (marketCap?.fmt) return parseAbbrevNumber(marketCap.fmt);
  return null;
}

export async function fetchYahooMarketCap(symbol, { ttlMs = DEFAULT_TTL_MS } = {}) {
  if (!symbol) return null;
  const sym = String(symbol).trim().toUpperCase();
  if (!sym) return null;

  const now = Date.now();
  const cached = marketCapCache.get(sym);
  if (cached && cached.expiresAt > now) {
    // Never treat cached null as authoritative.
    if (cached.value != null) return cached.value;
  }

  if (inFlight.has(sym)) {
    return inFlight.get(sym);
  }

  const promise = (async () => {
    try {
      // 1) Prefer stable JSON endpoints (these are what the quote page uses under the hood)
      const v7MarketCap = await fetchYahooMarketCapFromV7Quote(sym).catch(() => null);
      if (v7MarketCap != null) {
        marketCapCache.set(sym, {
          value: v7MarketCap,
          expiresAt: Date.now() + ttlMs,
        });
        return v7MarketCap;
      }

      const summaryMarketCap = await fetchYahooMarketCapFromQuoteSummary(sym).catch(() => null);
      if (summaryMarketCap != null) {
        marketCapCache.set(sym, {
          value: summaryMarketCap,
          expiresAt: Date.now() + ttlMs,
        });
        return summaryMarketCap;
      }

      // 2) Fallback to the public HTML quote page
      const url = `https://finance.yahoo.com/quote/${encodeURIComponent(sym)}/`;
      const response = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
          'Accept-Language': 'en-US,en;q=0.9',
        },
        redirect: 'follow',
      });

      if (!response.ok) {
        return null;
      }

      const html = await response.text();
      const marketCap = parseMarketCapFromYahooQuoteHtml(html);

      // Do not cache null results; Yahoo occasionally blocks/changes markup temporarily.
      if (marketCap != null) {
        marketCapCache.set(sym, {
          value: marketCap,
          expiresAt: Date.now() + ttlMs,
        });
      }

      return marketCap;
    } catch {
      return null;
    } finally {
      inFlight.delete(sym);
    }
  })();

  inFlight.set(sym, promise);
  return promise;
}
