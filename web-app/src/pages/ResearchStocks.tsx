/**
 * Research Stocks Page
 * 
 * Allows users to:
 * 1. Select search criteria via checkboxes
 * 2. Scrape stock data from Yahoo Finance (most-active, gainers, losers)
 * 3. Use LLM to generate SQL query from selected criteria
 * 4. Display matching stocks in a results table
 */

import { useState, useEffect } from 'react'
import Header from '../components/Header'

interface SearchCriteria {
  id: number
  name: string
  description: string
  sql_hint: string
  is_active: boolean
}

interface CriteriaValues {
  [key: number]: string  // criteriaId -> user-entered value
}

interface Stock {
  symbol: string
  name: string
  price: number | null
  change: number | null
  change_percent: number | null
  volume: number | null
  avg_volume_3m: number | null
  market_cap: number | null
  pe_ratio: number | null
  source: string
  scraped_at: string
}

interface ScrapeStatus {
  lastRun: {
    id: number
    started_at: string
    completed_at: string
    status: string
    stocks_count: number
    sources_scraped: string[]
  } | null
  lastScrape: string | null
  uniqueStocks: number
  cacheValid: boolean
}

export default function ResearchStocks() {
  const [criteria, setCriteria] = useState<SearchCriteria[]>([])
  const [selectedCriteria, setSelectedCriteria] = useState<Set<number>>(new Set())
  const [criteriaValues, setCriteriaValues] = useState<CriteriaValues>({
    1: '2',    // Default: $2B market cap
    2: '15',   // Default: 15% price drop
    3: '50'    // Default: 50% volume deviation
  })
  const [stocks, setStocks] = useState<Stock[]>([])
  const [status, setStatus] = useState<ScrapeStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [scraping, setScraping] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [generatedQuery, setGeneratedQuery] = useState<string | null>(null)
  const [criteriaUsed, setCriteriaUsed] = useState<string[]>([])
  const [pageError, setPageError] = useState<string | null>(null)
  const [sortColumn, setSortColumn] = useState<string | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')

  // Fetch available criteria on mount
  useEffect(() => {
    try {
      fetchCriteria()
      fetchStatus()
    } catch (err) {
      setPageError(err instanceof Error ? err.message : 'Failed to initialize page')
    }
  }, [])

  const fetchCriteria = async () => {
    try {
      const response = await fetch('/api/v1/research-stocks/criteria')
      if (response.ok) {
        const data = await response.json()
        setCriteria(data.criteria)
      }
    } catch (err) {
      console.error('Failed to fetch criteria:', err)
    }
  }

  const fetchStatus = async () => {
    try {
      const response = await fetch('/api/v1/research-stocks/status')
      if (response.ok) {
        const data = await response.json()
        setStatus(data)
      }
    } catch (err) {
      console.error('Failed to fetch status:', err)
    }
  }

  const toggleCriteria = (id: number) => {
    setSelectedCriteria(prev => {
      const newSet = new Set(prev)
      if (newSet.has(id)) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      return newSet
    })
  }

  const updateCriteriaValue = (id: number, value: string) => {
    setCriteriaValues(prev => ({
      ...prev,
      [id]: value
    }))
  }

  const handleSubmit = async () => {
    if (selectedCriteria.size === 0) {
      setError('Please select at least one search criterion')
      return
    }

    setLoading(true)
    setError(null)
    setStocks([])
    setGeneratedQuery(null)
    setCriteriaUsed([])

    try {
      // Step 1: Scrape data (will use cache if fresh)
      setScraping(true)
      const scrapeResponse = await fetch('/api/v1/research-stocks/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })

      if (!scrapeResponse.ok) {
        throw new Error('Failed to fetch stock data from Yahoo Finance')
      }

      const scrapeData = await scrapeResponse.json()
      console.log('Scrape result:', scrapeData)
      setScraping(false)

      // Step 2: Search with selected criteria and their values
      const criteriaWithValues = Array.from(selectedCriteria).map(id => ({
        id,
        value: criteriaValues[id] || ''
      }))
      
      const searchResponse = await fetch('/api/v1/research-stocks/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          criteriaIds: Array.from(selectedCriteria),
          criteriaValues: criteriaWithValues
        })
      })

      if (!searchResponse.ok) {
        const errorData = await searchResponse.json()
        throw new Error(errorData.error || 'Failed to search stocks')
      }

      const searchData = await searchResponse.json()
      setStocks(searchData.stocks)
      setGeneratedQuery(searchData.query)
      setCriteriaUsed(searchData.criteriaUsed)

      // Refresh status
      fetchStatus()

    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
      setScraping(false)
    }
  }

  const formatNumber = (num: number | string | null, decimals = 2): string => {
    if (num === null || num === undefined) return '-'
    const n = typeof num === 'string' ? parseFloat(num) : num
    if (isNaN(n)) return '-'
    return n.toLocaleString(undefined, { 
      minimumFractionDigits: decimals, 
      maximumFractionDigits: decimals 
    })
  }

  const formatLargeNumber = (num: number | string | null): string => {
    if (num === null || num === undefined) return '-'
    const n = typeof num === 'string' ? parseFloat(num) : num
    if (isNaN(n)) return '-'
    if (n >= 1_000_000_000_000) return `${(n / 1_000_000_000_000).toFixed(2)}T`
    if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
    if (n >= 1_000) return `${(n / 1_000).toFixed(2)}K`
    return n.toLocaleString()
  }

  const formatPercent = (num: number | string | null): string => {
    if (num === null || num === undefined) return '-'
    const n = typeof num === 'string' ? parseFloat(num) : num
    if (isNaN(n)) return '-'
    const sign = n >= 0 ? '+' : ''
    return `${sign}${n.toFixed(2)}%`
  }

  const getChangeColor = (change: number | null): string => {
    if (change === null) return 'text-gray-500'
    if (change > 0) return 'text-green-600'
    if (change < 0) return 'text-red-600'
    return 'text-gray-500'
  }

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortColumn(column)
      setSortDirection('asc')
    }
  }

  const getSortedStocks = (): Stock[] => {
    if (!sortColumn) return stocks
    
    return [...stocks].sort((a, b) => {
      let aVal = a[sortColumn as keyof Stock]
      let bVal = b[sortColumn as keyof Stock]
      
      // Handle null values
      if (aVal === null || aVal === undefined) return sortDirection === 'asc' ? 1 : -1
      if (bVal === null || bVal === undefined) return sortDirection === 'asc' ? -1 : 1
      
      // Convert strings to numbers if needed
      if (typeof aVal === 'string' && !isNaN(parseFloat(aVal))) aVal = parseFloat(aVal)
      if (typeof bVal === 'string' && !isNaN(parseFloat(bVal))) bVal = parseFloat(bVal)
      
      // Compare
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc' 
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal)
      }
      
      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1
      return 0
    })
  }

  const SortIcon = ({ column }: { column: string }) => (
    <span className="ml-1 inline-block">
      {sortColumn === column ? (
        sortDirection === 'asc' ? '↑' : '↓'
      ) : (
        <span className="text-gray-300">↕</span>
      )}
    </span>
  )

  // Wrap entire render in try-catch for debugging
  try {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        
        <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
          {/* Page Error */}
          {pageError && (
            <div className="mb-6 bg-red-100 border border-red-400 rounded-lg p-4">
              <p className="text-red-700">Page Error: {pageError}</p>
            </div>
          )}

          {/* Page Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">Research Stocks</h1>
            <p className="mt-2 text-gray-600">
              Select criteria to filter stocks from Yahoo Finance (Most Active, Gainers, Losers)
            </p>
          </div>

        {/* Status Card */}
        {status && (
          <div className="mb-6 bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm text-gray-500">Data Status: </span>
                {status.cacheValid ? (
                  <span className="text-sm text-green-600 font-medium">
                    ✓ Fresh data available ({status.uniqueStocks} unique stocks)
                  </span>
                ) : (
                  <span className="text-sm text-yellow-600 font-medium">
                    ⚠ Data will be refreshed on search
                  </span>
                )}
              </div>
              {status.lastScrape && (
                <span className="text-xs text-gray-400">
                  Last updated: {new Date(status.lastScrape).toLocaleString()}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Yahoo Screeners Section */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Yahoo Screeners</h2>
            <p className="text-sm text-gray-500 mt-1">
              External Yahoo Finance screeners for additional research.
            </p>
          </div>
          <div className="p-6 flex flex-wrap gap-4">
            <a
              href="https://finance.yahoo.com/research-hub/screener/831957d7-4555-4d66-b231-f3e693df9d6f/?start=0&count=100"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              Daily Losers Screener
            </a>
            <a
              href="https://finance.yahoo.com/research-hub/screener/9ed7221d-a38f-4228-b8c0-fe40b4320363/?start=0&count=100"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              Daily Gainers Screener
            </a>
          </div>
        </div>

        {/* Criteria Selection */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Search Criteria</h2>
            <p className="text-sm text-gray-500 mt-1">
              Select the criteria to filter stocks. All selected criteria must match (AND logic).
            </p>
          </div>
          
          <div className="p-6 space-y-4">
            {criteria.length === 0 ? (
              <p className="text-gray-500">Loading criteria...</p>
            ) : (
              <>
                {/* Criteria 1: Market Cap */}
                <div
                  className={`flex items-start p-4 rounded-lg border-2 transition-all ${
                    selectedCriteria.has(1)
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedCriteria.has(1)}
                    onChange={() => toggleCriteria(1)}
                    className="mt-1 h-5 w-5 text-blue-600 rounded border-gray-300 focus:ring-blue-500 cursor-pointer"
                  />
                  <div className="ml-4 flex-1">
                    <p className="font-medium text-gray-900">
                      Show me stocks with market cap greater than{' '}
                      <span className="inline-flex items-center">
                        $
                        <input
                          type="number"
                          min="0"
                          value={criteriaValues[1]}
                          onChange={(e) => updateCriteriaValue(1, e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          className="mx-1 w-20 px-2 py-1 border border-gray-300 rounded text-center focus:ring-blue-500 focus:border-blue-500"
                        />
                        B
                      </span>
                    </p>
                  </div>
                </div>

                {/* Criteria 2: Price Drop */}
                <div
                  className={`flex items-start p-4 rounded-lg border-2 transition-all ${
                    selectedCriteria.has(2)
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedCriteria.has(2)}
                    onChange={() => toggleCriteria(2)}
                    className="mt-1 h-5 w-5 text-blue-600 rounded border-gray-300 focus:ring-blue-500 cursor-pointer"
                  />
                  <div className="ml-4 flex-1">
                    <p className="font-medium text-gray-900">
                      Show me stocks with daily price drop of more than{' '}
                      <span className="inline-flex items-center">
                        <input
                          type="number"
                          min="0"
                          value={criteriaValues[2]}
                          onChange={(e) => updateCriteriaValue(2, e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          className="mx-1 w-20 px-2 py-1 border border-gray-300 rounded text-center focus:ring-blue-500 focus:border-blue-500"
                        />
                        %
                      </span>
                    </p>
                  </div>
                </div>

                {/* Criteria 3: Volume Deviation */}
                <div
                  className={`flex items-start p-4 rounded-lg border-2 transition-all ${
                    selectedCriteria.has(3)
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedCriteria.has(3)}
                    onChange={() => toggleCriteria(3)}
                    className="mt-1 h-5 w-5 text-blue-600 rounded border-gray-300 focus:ring-blue-500 cursor-pointer"
                  />
                  <div className="ml-4 flex-1">
                    <p className="font-medium text-gray-900">
                      Show me stocks where today's volume deviates from average vol (3M) by more than{' '}
                      <span className="inline-flex items-center">
                        <input
                          type="number"
                          min="0"
                          value={criteriaValues[3]}
                          onChange={(e) => updateCriteriaValue(3, e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          className="mx-1 w-20 px-2 py-1 border border-gray-300 rounded text-center focus:ring-blue-500 focus:border-blue-500"
                        />
                        %
                      </span>
                    </p>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Submit Button */}
          <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
            <button
              onClick={handleSubmit}
              disabled={loading || selectedCriteria.size === 0}
              className={`w-full sm:w-auto px-6 py-3 rounded-lg font-medium transition-colors ${
                loading || selectedCriteria.size === 0
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  {scraping ? 'Fetching from Yahoo Finance...' : 'Searching stocks...'}
                </span>
              ) : (
                `Search Stocks (${selectedCriteria.size} criteria selected)`
              )}
            </button>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Generated Query Display */}
        {generatedQuery && (
          <div className="mb-6 bg-gray-800 rounded-lg p-4">
            <p className="text-xs text-gray-400 mb-2">LLM Generated SQL WHERE Clause:</p>
            <code className="text-sm text-green-400 font-mono">{generatedQuery}</code>
            <div className="mt-3 pt-3 border-t border-gray-700">
              <p className="text-xs text-gray-400">Criteria applied:</p>
              <ul className="mt-1">
                {criteriaUsed.map((c, i) => (
                  <li key={i} className="text-xs text-gray-300">• {c}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Results Table */}
        {stocks.length > 0 && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">
                Results ({stocks.length} stocks found)
              </h2>
            </div>
            
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th onClick={() => handleSort('symbol')} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                      Symbol<SortIcon column="symbol" />
                    </th>
                    <th onClick={() => handleSort('name')} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                      Name<SortIcon column="name" />
                    </th>
                    <th onClick={() => handleSort('price')} className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                      Price<SortIcon column="price" />
                    </th>
                    <th onClick={() => handleSort('change')} className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                      Change<SortIcon column="change" />
                    </th>
                    <th onClick={() => handleSort('change_percent')} className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                      Change %<SortIcon column="change_percent" />
                    </th>
                    <th onClick={() => handleSort('volume')} className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                      Volume<SortIcon column="volume" />
                    </th>
                    <th onClick={() => handleSort('avg_volume_3m')} className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                      Avg Vol (3M)<SortIcon column="avg_volume_3m" />
                    </th>
                    <th onClick={() => handleSort('market_cap')} className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                      Market Cap<SortIcon column="market_cap" />
                    </th>
                    <th onClick={() => handleSort('pe_ratio')} className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                      P/E<SortIcon column="pe_ratio" />
                    </th>
                    <th onClick={() => handleSort('source')} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100">
                      Source<SortIcon column="source" />
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {getSortedStocks().map((stock, index) => (
                    <tr key={`${stock.symbol}-${index}`} className="hover:bg-gray-50">
                      <td className="px-4 py-3 whitespace-nowrap">
                        <a 
                          href={`https://finance.yahoo.com/quote/${stock.symbol}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-blue-600 hover:text-blue-800"
                        >
                          {stock.symbol}
                        </a>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 max-w-xs truncate">
                        {stock.name || '-'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-900">
                        ${formatNumber(stock.price)}
                      </td>
                      <td className={`px-4 py-3 whitespace-nowrap text-sm text-right ${getChangeColor(stock.change)}`}>
                        {stock.change !== null ? (stock.change >= 0 ? '+' : '') : ''}
                        {formatNumber(stock.change)}
                      </td>
                      <td className={`px-4 py-3 whitespace-nowrap text-sm text-right font-medium ${getChangeColor(stock.change_percent)}`}>
                        {formatPercent(stock.change_percent)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-900">
                        {formatLargeNumber(stock.volume)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-500">
                        {formatLargeNumber(stock.avg_volume_3m)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-900">
                        ${formatLargeNumber(stock.market_cap)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-500">
                        {formatNumber(stock.pe_ratio)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        <span className={`px-2 py-1 rounded-full text-xs ${
                          stock.source === 'gainers' ? 'bg-green-100 text-green-800' :
                          stock.source === 'losers' ? 'bg-red-100 text-red-800' :
                          'bg-blue-100 text-blue-800'
                        }`}>
                          {stock.source}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* No Results Message */}
        {!loading && stocks.length === 0 && generatedQuery && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
            <p className="text-yellow-700">No stocks found matching all selected criteria.</p>
            <p className="text-sm text-yellow-600 mt-2">Try selecting fewer criteria or different combinations.</p>
          </div>
        )}
        </main>
      </div>
    )
  } catch (err) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <h1 className="text-2xl font-bold text-red-600">Error rendering page</h1>
        <p className="mt-2 text-gray-700">{err instanceof Error ? err.message : 'Unknown error'}</p>
      </div>
    )
  }
}
