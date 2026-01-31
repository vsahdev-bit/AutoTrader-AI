import { useEffect, useMemo, useRef, useState } from 'react'
import Header from '../components/Header'
import { useAuth } from '../context/AuthContext'
import { searchStocks, addToOptionsWatchlist, getOptionsWatchlist, removeFromOptionsWatchlist, OptionsWatchlistItem } from '../services/onboardingApi'
import { stockQuotesApi, StockQuote } from '../services/api'

interface StockSearchResult {
  symbol: string
  name: string
  exchange: string
  type: string
}

function formatMarketCap(value: number | null): string {
  if (value === null || value === undefined) return '-'
  const abs = Math.abs(value)
  if (abs >= 1e12) return `${(value / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${(value / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `${(value / 1e6).toFixed(2)}M`
  return value.toLocaleString()
}

function formatPrice(value: number | null): string {
  if (value === null || value === undefined) return '-'
  return `$${value.toFixed(2)}`
}

export default function Options() {
  const { user } = useAuth()
  const userId = user?.dbId

  // Watchlist + quotes
  const [items, setItems] = useState<OptionsWatchlistItem[]>([])
  const [quotes, setQuotes] = useState<Record<string, StockQuote>>({})

  // Page state
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [quotesLoading, setQuotesLoading] = useState(false)

  // Search state (copied pattern from GetRecommendation)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<StockSearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const symbols = useMemo(() => items.map(i => i.symbol.toUpperCase()), [items])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const refreshQuotes = async (symbolsToFetch: string[]) => {
    if (symbolsToFetch.length === 0) return
    setQuotesLoading(true)
    try {
      const { data } = await stockQuotesApi.getQuotes(symbolsToFetch)
      setQuotes(data.quotes)
    } catch (e) {
      console.error('Failed to load quotes:', e)
    } finally {
      setQuotesLoading(false)
    }
  }

  const load = async () => {
    if (!userId) {
      setError('Please log in to view Options')
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)

    try {
      const data = await getOptionsWatchlist(userId)
      setItems(data)
      await refreshQuotes(data.map(d => d.symbol))
    } catch (e: any) {
      setError(e?.message || 'Failed to load options watchlist')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId])

  const handleSearch = async (query: string) => {
    setSearchQuery(query)

    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
    }

    if (query.length < 1) {
      setSearchResults([])
      setShowDropdown(false)
      return
    }

    searchTimeoutRef.current = setTimeout(async () => {
      setIsSearching(true)
      try {
        const results = await searchStocks(query)
        setSearchResults((results || []) as any)
        setShowDropdown(true)
      } catch (err) {
        console.error('Search error:', err)
        setSearchResults([])
      } finally {
        setIsSearching(false)
      }
    }, 250)
  }

  const handleAdd = async (stock: StockSearchResult) => {
    if (!userId) return

    const sym = stock.symbol.toUpperCase()

    try {
      const added = await addToOptionsWatchlist(userId, {
        symbol: sym,
        companyName: stock.name,
        exchange: stock.exchange,
      })

      setItems(prev => {
        const exists = prev.some(x => x.symbol.toUpperCase() === sym)
        const next = exists ? prev : [...prev, added]
        next.sort((a, b) => a.symbol.localeCompare(b.symbol))
        return next
      })

      setSearchQuery('')
      setSearchResults([])
      setShowDropdown(false)

      await refreshQuotes([sym, ...symbols])
    } catch (e: any) {
      alert(e?.message || 'Failed to add symbol')
    }
  }

  const handleRemove = async (symbol: string) => {
    if (!userId) return
    const sym = symbol.toUpperCase()

    try {
      await removeFromOptionsWatchlist(userId, sym)
      setItems(prev => prev.filter(x => x.symbol.toUpperCase() !== sym))
      setQuotes(prev => {
        const next = { ...prev }
        delete next[sym]
        return next
      })
    } catch (e: any) {
      alert(e?.message || 'Failed to remove symbol')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Options</h1>
          <p className="mt-2 text-gray-600">Track an options watchlist with key stock metrics.</p>
        </div>

        {/* Add symbols */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Add stock</h2>

          <div className="flex gap-4">
            <div className="flex-1 relative" ref={dropdownRef}>
              <div className="relative">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => handleSearch(e.target.value)}
                  onFocus={() => searchResults.length > 0 && setShowDropdown(true)}
                  placeholder="Search by symbol or company name (e.g., AAPL, Apple)"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors"
                />
                {isSearching && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                  </div>
                )}
              </div>

              {showDropdown && searchResults.length > 0 && (
                <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                  {searchResults.map((stock) => (
                    <button
                      key={stock.symbol}
                      onClick={() => handleAdd(stock)}
                      className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-center justify-between border-b border-gray-100 last:border-0"
                    >
                      <div>
                        <span className="font-semibold text-gray-900">{stock.symbol}</span>
                        <span className="text-gray-500 ml-2 text-sm">{stock.name}</span>
                      </div>
                      <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded">{stock.exchange}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <button
              onClick={() => handleSearch(searchQuery)}
              disabled={true}
              className="px-6 py-3 font-medium rounded-lg bg-gray-100 text-gray-400 cursor-not-allowed"
              title="Select a stock from the dropdown to add"
            >
              Add
            </button>
          </div>

          <p className="text-xs text-gray-500 mt-2">Tip: pick a result from the dropdown to add it.</p>
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Options Watchlist</h2>
              <p className="text-sm text-gray-500">{items.length} symbol{items.length === 1 ? '' : 's'}</p>
            </div>
            <button
              onClick={() => refreshQuotes(symbols)}
              disabled={quotesLoading || symbols.length === 0}
              className={`px-4 py-2 text-sm font-medium rounded-lg border ${
                quotesLoading || symbols.length === 0
                  ? 'bg-gray-50 text-gray-400 border-gray-200 cursor-not-allowed'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              {quotesLoading ? 'Refreshing…' : 'Refresh quotes'}
            </button>
          </div>

          {loading ? (
            <div className="p-8 text-center text-gray-500">Loading…</div>
          ) : error ? (
            <div className="p-8 text-center text-red-600">{error}</div>
          ) : items.length === 0 ? (
            <div className="p-8 text-center text-gray-500">No symbols yet. Add one above.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Symbol</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Company</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Price</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Change</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Market Cap</th>
                    <th className="px-6 py-3"></th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {items.map((item) => {
                    const sym = item.symbol.toUpperCase()
                    const q = quotes[sym]
                    const change = q?.change
                    const changePct = q?.changePercent
                    const changeText =
                      change === null || change === undefined
                        ? '-'
                        : `${change >= 0 ? '+' : ''}${change.toFixed(2)}${
                            changePct !== null && changePct !== undefined ? ` (${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}%)` : ''
                          }`
                    const changeClass = change === null || change === undefined
                      ? 'text-gray-500'
                      : change >= 0
                        ? 'text-green-600'
                        : 'text-red-600'

                    return (
                      <tr key={item.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap font-semibold text-gray-900">{sym}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                          {item.company_name || '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                          {formatPrice(q?.price ?? null)}
                        </td>
                        <td className={`px-6 py-4 whitespace-nowrap text-right text-sm ${changeClass}`}>
                          {changeText}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                          {formatMarketCap(q?.marketCap ?? null)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right">
                          <button
                            onClick={() => handleRemove(sym)}
                            className="text-sm text-red-600 hover:text-red-800 hover:underline"
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
