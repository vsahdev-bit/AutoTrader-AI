import { Link } from 'react-router-dom'
import PublicPageLayout from '../../components/PublicPageLayout'

export default function RiskDisclosure() {
  const lastUpdated = 'January 15, 2026'

  return (
    <PublicPageLayout>
      {/* Hero Section */}
      <section className="pt-16 pb-8 px-4 sm:px-6 lg:px-8 bg-red-50">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-3 mb-4">
            <svg className="w-10 h-10 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <h1 className="text-4xl font-bold text-gray-900">Risk Disclosure</h1>
          </div>
          <p className="text-gray-600">
            Last updated: {lastUpdated}
          </p>
        </div>
      </section>

      {/* Important Warning Banner */}
      <section className="py-6 px-4 sm:px-6 lg:px-8 bg-red-600">
        <div className="max-w-4xl mx-auto">
          <p className="text-white text-center font-medium">
            ⚠️ Trading involves substantial risk of loss. Please read this entire disclosure before using our Services.
          </p>
        </div>
      </section>

      {/* Content */}
      <section className="py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 md:p-12">
            <div className="prose prose-gray max-w-none">

              {/* General Risk Warning */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">1. General Risk Warning</h2>
                <div className="bg-red-50 border-l-4 border-red-500 p-6 mb-6">
                  <p className="text-red-900 leading-relaxed font-medium">
                    Trading stocks, options, ETFs, and other securities involves substantial risk of loss and is not suitable for all investors. You should carefully consider your investment objectives, level of experience, and risk appetite before using AutoTrader AI or making any investment decisions.
                  </p>
                </div>
                <p className="text-gray-600 leading-relaxed mb-4">
                  The value of investments can go down as well as up, and you may lose some or all of your invested capital. There is no guarantee that any investment strategy, including those suggested by our AI, will be successful.
                </p>
                <p className="text-gray-600 leading-relaxed">
                  <strong>Only invest money you can afford to lose.</strong> If you are unsure whether trading is appropriate for you, please consult with a qualified financial advisor before using our Services.
                </p>
              </div>

              {/* Past Performance */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">2. Past Performance Disclaimer</h2>
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 mb-4">
                  <p className="text-yellow-900 leading-relaxed font-medium">
                    PAST PERFORMANCE IS NOT INDICATIVE OF FUTURE RESULTS.
                  </p>
                </div>
                <p className="text-gray-600 leading-relaxed mb-4">
                  Any historical returns, expected returns, or probability projections displayed on our website or in our marketing materials:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2">
                  <li>Are based on historical data and backtesting, which may not reflect actual trading conditions</li>
                  <li>Do not account for all market conditions, fees, slippage, or other real-world factors</li>
                  <li>Should not be relied upon as a prediction or guarantee of future performance</li>
                  <li>May not be achievable by all users due to individual circumstances</li>
                </ul>
              </div>

              {/* Market Risks */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">3. Market Risks</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  Securities markets are subject to various risks that can significantly impact your investments:
                </p>
                
                <h3 className="text-lg font-semibold text-gray-900 mb-3">3.1 Volatility Risk</h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  Markets can experience extreme price movements in short periods. High volatility can lead to significant losses, especially for leveraged positions or short-term trades.
                </p>

                <h3 className="text-lg font-semibold text-gray-900 mb-3">3.2 Liquidity Risk</h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  Some securities may have limited trading volume, making it difficult to buy or sell at desired prices. This can result in wider spreads and potentially larger losses.
                </p>

                <h3 className="text-lg font-semibold text-gray-900 mb-3">3.3 Systematic Risk</h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  Broad market events—such as economic recessions, geopolitical events, pandemics, or financial crises—can cause widespread losses across all securities and sectors.
                </p>

                <h3 className="text-lg font-semibold text-gray-900 mb-3">3.4 Company-Specific Risk</h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  Individual stocks can be affected by company-specific events such as earnings reports, management changes, lawsuits, regulatory actions, or bankruptcy.
                </p>

                <h3 className="text-lg font-semibold text-gray-900 mb-3">3.5 Gap Risk</h3>
                <p className="text-gray-600 leading-relaxed">
                  Prices can "gap" significantly between market close and open due to after-hours news or events. Stop-loss orders may not protect against gap losses.
                </p>
              </div>

              {/* AI and Algorithm Limitations */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">4. AI and Algorithm Limitations</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  AutoTrader AI uses artificial intelligence and machine learning algorithms to generate trading recommendations. You should understand the following limitations:
                </p>

                <div className="space-y-4">
                  <div className="bg-gray-50 rounded-lg p-4">
                    <h4 className="font-semibold text-gray-900 mb-2">Model Uncertainty</h4>
                    <p className="text-gray-600 text-sm">
                      AI models are trained on historical data and may not accurately predict future market behavior, especially during unprecedented events or market conditions not present in training data.
                    </p>
                  </div>

                  <div className="bg-gray-50 rounded-lg p-4">
                    <h4 className="font-semibold text-gray-900 mb-2">Data Quality</h4>
                    <p className="text-gray-600 text-sm">
                      Our recommendations depend on data from third-party sources. Errors, delays, or inaccuracies in this data can affect the quality of recommendations.
                    </p>
                  </div>

                  <div className="bg-gray-50 rounded-lg p-4">
                    <h4 className="font-semibold text-gray-900 mb-2">Technical Failures</h4>
                    <p className="text-gray-600 text-sm">
                      Software bugs, system outages, or connectivity issues may prevent timely generation or delivery of recommendations.
                    </p>
                  </div>

                  <div className="bg-gray-50 rounded-lg p-4">
                    <h4 className="font-semibold text-gray-900 mb-2">Black Swan Events</h4>
                    <p className="text-gray-600 text-sm">
                      AI models cannot predict rare, extreme events that have not occurred in historical data. Such events can cause significant losses.
                    </p>
                  </div>

                  <div className="bg-gray-50 rounded-lg p-4">
                    <h4 className="font-semibold text-gray-900 mb-2">Confidence Scores</h4>
                    <p className="text-gray-600 text-sm">
                      Confidence scores represent the model's certainty, not the probability of profit. A high confidence score does not guarantee a successful trade.
                    </p>
                  </div>
                </div>
              </div>

              {/* Not Investment Advice */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">5. Not Investment Advice</h2>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-4">
                  <p className="text-blue-900 leading-relaxed">
                    <strong>AutoTrader AI does not provide personalized investment advice.</strong> Our Services provide general information and AI-generated recommendations based on technical and sentiment analysis. These recommendations are not tailored to your individual financial situation, investment objectives, or risk tolerance.
                  </p>
                </div>
                <p className="text-gray-600 leading-relaxed mb-4">
                  We are not a registered investment advisor, broker-dealer, or financial planner. Our recommendations should not be construed as:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2">
                  <li>A recommendation to buy, sell, or hold any specific security</li>
                  <li>An offer or solicitation to buy or sell securities</li>
                  <li>Personalized investment advice</li>
                  <li>Tax, legal, or accounting advice</li>
                </ul>
              </div>

              {/* Brokerage Risks */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">6. Brokerage Account Risks</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  When you connect a brokerage account to AutoTrader AI:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-4">
                  <li><strong>Execution Risk:</strong> Trades may not execute at expected prices due to market conditions, delays, or brokerage limitations</li>
                  <li><strong>Brokerage Failure:</strong> Your brokerage may experience technical issues, security breaches, or financial difficulties</li>
                  <li><strong>Connection Issues:</strong> API connections may fail, preventing execution of intended trades</li>
                  <li><strong>Third-Party Risk:</strong> We rely on brokerages to execute trades; we are not responsible for their actions or failures</li>
                </ul>
                <p className="text-gray-600 leading-relaxed">
                  Ensure your brokerage account is protected by SIPC (Securities Investor Protection Corporation) and understand your brokerage's own risk disclosures.
                </p>
              </div>

              {/* Regulatory Considerations */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">7. Regulatory Considerations</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  Trading activities are subject to various laws and regulations:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2">
                  <li><strong>Pattern Day Trading:</strong> Accounts with less than $25,000 may be restricted from day trading under FINRA rules</li>
                  <li><strong>Wash Sale Rules:</strong> IRS rules may affect the tax treatment of losses on securities sold and repurchased within 30 days</li>
                  <li><strong>Short-Term Capital Gains:</strong> Profits from securities held less than one year are taxed as ordinary income</li>
                  <li><strong>International Regulations:</strong> If you reside outside the US, additional regulations may apply</li>
                </ul>
                <p className="text-gray-600 leading-relaxed mt-4">
                  You are responsible for understanding and complying with all applicable laws and regulations. Consult with a tax professional regarding the tax implications of your trading activities.
                </p>
              </div>

              {/* Psychological Risks */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">8. Psychological and Behavioral Risks</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  Trading can have psychological impacts that affect decision-making:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2">
                  <li><strong>Emotional Trading:</strong> Fear and greed can lead to poor decisions that deviate from sound strategy</li>
                  <li><strong>Overconfidence:</strong> Past successes may lead to excessive risk-taking</li>
                  <li><strong>Loss Aversion:</strong> The tendency to hold losing positions too long hoping for recovery</li>
                  <li><strong>Addiction:</strong> Trading can become addictive; seek help if trading negatively impacts your life</li>
                </ul>
                <p className="text-gray-600 leading-relaxed mt-4">
                  We encourage responsible trading. If you feel trading is negatively affecting your mental health or financial well-being, please seek professional help.
                </p>
              </div>

              {/* Recommendation */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">9. Seek Professional Advice</h2>
                <div className="bg-green-50 border border-green-200 rounded-lg p-6">
                  <p className="text-green-900 leading-relaxed">
                    <strong>We strongly recommend consulting with qualified professionals before making investment decisions:</strong>
                  </p>
                  <ul className="list-disc pl-6 text-green-800 space-y-2 mt-4">
                    <li><strong>Financial Advisor:</strong> To assess whether trading aligns with your financial goals</li>
                    <li><strong>Tax Professional:</strong> To understand tax implications of trading activities</li>
                    <li><strong>Legal Advisor:</strong> To ensure compliance with applicable laws and regulations</li>
                  </ul>
                </div>
              </div>

              {/* Acknowledgment */}
              <div className="mb-6">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">10. Acknowledgment</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  By using AutoTrader AI Services, you acknowledge that you have read, understood, and agree to this Risk Disclosure. You confirm that:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-6">
                  <li>You understand the risks associated with trading securities</li>
                  <li>You are solely responsible for your trading decisions</li>
                  <li>You will not hold AutoTrader AI liable for any trading losses</li>
                  <li>You have the financial resources to bear potential losses</li>
                  <li>You will seek professional advice if needed</li>
                </ul>

                <div className="bg-gray-900 text-white rounded-lg p-6 text-center">
                  <p className="font-medium mb-2">
                    Questions about risks or our Services?
                  </p>
                  <p className="text-gray-300 text-sm">
                    Contact us at <a href="mailto:support@autotrader.ai" className="text-blue-400 hover:underline">support@autotrader.ai</a>
                  </p>
                </div>
              </div>

            </div>
          </div>

          {/* Related Links */}
          <div className="mt-8 flex flex-wrap gap-4 justify-center">
            <Link
              to="/terms"
              className="text-blue-600 hover:underline font-medium"
            >
              Terms of Service →
            </Link>
            <Link
              to="/privacy"
              className="text-blue-600 hover:underline font-medium"
            >
              Privacy Policy →
            </Link>
            <Link
              to="/faq"
              className="text-blue-600 hover:underline font-medium"
            >
              FAQ →
            </Link>
          </div>
        </div>
      </section>
    </PublicPageLayout>
  )
}
