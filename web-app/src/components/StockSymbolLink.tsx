import React from 'react'
import { Link } from 'react-router-dom'

/**
 * StockSymbolLink
 * 
 * Small utility component used across recommendation UIs to render a stock symbol
 * as a navigable link. By default it links to the Stock Recommendations page with
 * an in-page anchor to the symbol section.
 */
export default function StockSymbolLink({
  symbol,
  className,
  href,
}: {
  symbol: string
  className?: string
  /** Optional override for the link target */
  href?: string
}) {
  const sym = (symbol || '').trim().toUpperCase()
  const target = href ?? `/recommendations#${encodeURIComponent(sym)}`

  return (
    <Link
      to={target}
      className={className ?? 'text-blue-600 hover:text-blue-800 hover:underline'}
      title={`View ${sym}`}
    >
      {sym}
    </Link>
  )
}
