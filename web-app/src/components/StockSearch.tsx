import { useState, useEffect, useRef } from 'react'
import { searchStocks, addToWatchlist, removeFromWatchlist, StockSearchResult, WatchlistStock } from '../services/onboardingApi'

interface StockSearchProps {
  userId: string
  watchlist: WatchlistStock[]
  onWatchlistUpdate: (stocks: WatchlistStock[]) => void
}

export default function StockSearch({ userId, watchlist, onWatchlistUpdate }: StockSearchProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StockSearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)
  const [isAdding, setIsAdding] = useState<string | null>(null)
  const searchRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Debounced search
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }

    if (query.length < 1) {
      setResults([])
      setShowDropdown(false)
      return
    }

    setIsSearching(true)
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await searchStocks(query)
        setResults(data)
        setShowDropdown(true)
      } catch (error) {
        console.error('Search error:', error)
      } finally {
        setIsSearching(false)
      }
    }, 300)

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [query])

  const handleAddStock = async (stock: StockSearchResult) => {
    setIsAdding(stock.symbol)
    try {
      const added = await addToWatchlist(userId, {
        symbol: stock.symbol,
        companyName: stock.name,
        exchange: stock.exchange,
      })
      
      if (added && !watchlist.find(s => s.symbol === stock.symbol)) {
        onWatchlistUpdate([...watchlist, {
          id: added.id || crypto.randomUUID(),
          symbol: stock.symbol,
          company_name: stock.name,
          exchange: stock.exchange,
        }])
      }
    } catch (error) {
      console.error('Error adding stock:', error)
    } finally {
      setIsAdding(null)
      setQuery('')
      setShowDropdown(false)
    }
  }

  const handleRemoveStock = async (symbol: string) => {
    try {
      await removeFromWatchlist(userId, symbol)
      onWatchlistUpdate(watchlist.filter(s => s.symbol !== symbol))
    } catch (error) {
      console.error('Error removing stock:', error)
    }
  }

  const isInWatchlist = (symbol: string) => watchlist.some(s => s.symbol === symbol)

  return (
    <div className="space-y-6">
      {/* Search Box */}
      <div ref={searchRef} className="relative">
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
            {isSearching ? (
              <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            )}
          </div>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => results.length > 0 && setShowDropdown(true)}
            className="w-full pl-12 pr-4 py-4 text-lg border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-sm"
            placeholder="Search stocks by symbol or company name (e.g., AAPL, Tesla)"
          />
        </div>

        {/* Search Results Dropdown */}
        {showDropdown && results.length > 0 && (
          <div className="absolute z-50 w-full mt-2 bg-white border border-gray-200 rounded-xl shadow-lg max-h-96 overflow-y-auto">
            {results.map((stock) => (
              <div
                key={stock.symbol}
                className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-0"
              >
                <div className="flex-1" onClick={() => !isInWatchlist(stock.symbol) && handleAddStock(stock)}>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center font-bold text-gray-700 text-sm">
                      {stock.symbol.slice(0, 2)}
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900">{stock.symbol}</div>
                      <div className="text-sm text-gray-500 truncate max-w-xs">{stock.name}</div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded">{stock.exchange}</span>
                  {isInWatchlist(stock.symbol) ? (
                    <span className="text-green-600 text-sm font-medium flex items-center gap-1">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      Added
                    </span>
                  ) : (
                    <button
                      onClick={() => handleAddStock(stock)}
                      disabled={isAdding === stock.symbol}
                      className="px-3 py-1 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                    >
                      {isAdding === stock.symbol ? (
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      ) : (
                        '+ Add'
                      )}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* No Results */}
        {showDropdown && query.length > 0 && results.length === 0 && !isSearching && (
          <div className="absolute z-50 w-full mt-2 bg-white border border-gray-200 rounded-xl shadow-lg p-6 text-center">
            <svg className="w-12 h-12 text-gray-300 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-gray-500">No stocks found for "{query}"</p>
            <p className="text-sm text-gray-400 mt-1">Try searching with a different symbol or name</p>
          </div>
        )}
      </div>

      {/* Watchlist */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-900">Your Watchlist</h3>
          <span className="text-sm text-gray-500">{watchlist.length} stocks</span>
        </div>

        {watchlist.length === 0 ? (
          <div className="text-center py-12 bg-gray-50 rounded-xl border-2 border-dashed border-gray-200">
            <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            <p className="text-gray-500 font-medium">No stocks in your watchlist yet</p>
            <p className="text-sm text-gray-400 mt-1">Search above to add stocks you want to track</p>
          </div>
        ) : (
          <div className="max-h-[400px] overflow-y-auto border border-gray-200 rounded-xl">
            <div className="grid gap-3 p-3">
              {watchlist.map((stock) => (
                <div
                  key={stock.symbol}
                  className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-xl hover:shadow-sm transition-shadow"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center text-white font-bold">
                      {stock.symbol.slice(0, 2)}
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900">{stock.symbol}</div>
                      <div className="text-sm text-gray-500">{stock.company_name}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded">{stock.exchange}</span>
                    <button
                      onClick={() => handleRemoveStock(stock.symbol)}
                      className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                      title="Remove from watchlist"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Popular Stocks Suggestion */}
        {watchlist.length < 3 && (
          <div className="mt-6 p-4 bg-blue-50 rounded-xl">
            <p className="text-sm font-medium text-blue-900 mb-3">💡 Popular stocks to get started:</p>
            <div className="flex flex-wrap gap-2">
              {['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'NVDA', 'META'].map((symbol) => (
                !isInWatchlist(symbol) && (
                  <button
                    key={symbol}
                    onClick={() => handleAddStock({ symbol, name: symbol, exchange: 'NASDAQ', type: 'EQUITY' })}
                    className="px-3 py-1 bg-white border border-blue-200 rounded-full text-sm font-medium text-blue-700 hover:bg-blue-100 transition-colors"
                  >
                    + {symbol}
                  </button>
                )
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
