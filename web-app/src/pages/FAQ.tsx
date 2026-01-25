import { useState } from 'react'
import { Link } from 'react-router-dom'
import PublicPageLayout from '../components/PublicPageLayout'

interface FAQItem {
  question: string
  answer: string
}

interface FAQCategory {
  name: string
  icon: string
  faqs: FAQItem[]
}

const faqCategories: FAQCategory[] = [
  {
    name: 'Getting Started',
    icon: '🚀',
    faqs: [
      {
        question: 'What is AutoTrader AI?',
        answer: 'AutoTrader AI is an intelligent trading platform that uses advanced machine learning algorithms to analyze market data, news sentiment, and technical indicators to generate actionable trading recommendations. Our AI processes thousands of data points in real-time to help you make informed trading decisions.',
      },
      {
        question: 'How do I sign up?',
        answer: 'Signing up is easy! Simply click the "Get Started" button on our homepage and sign in with your Google account. You\'ll have immediate access to our free Starter plan, which includes basic AI recommendations and a watchlist. No credit card is required to get started.',
      },
      {
        question: 'Is AutoTrader AI suitable for beginners?',
        answer: 'Absolutely! AutoTrader AI is designed for traders of all experience levels. Our platform provides clear, actionable recommendations (BUY, SELL, HOLD) along with confidence scores and explanations. We also offer educational resources and a supportive community to help beginners learn the ropes.',
      },
      {
        question: 'What do I need to start using AutoTrader AI?',
        answer: 'All you need is a Google account to sign up. To execute trades automatically, you\'ll need to connect a supported brokerage account (available on Pro plan and above). However, you can use our AI recommendations manually with any broker of your choice.',
      },
    ],
  },
  {
    name: 'Trading & AI',
    icon: '🤖',
    faqs: [
      {
        question: 'How does the AI generate recommendations?',
        answer: 'Our AI analyzes multiple data sources including real-time market data, technical indicators (RSI, MACD, moving averages), news sentiment from major financial outlets, SEC filings, and social media trends. The algorithm weighs these factors based on historical performance to generate recommendations with confidence scores.',
      },
      {
        question: 'What is the AI\'s historical win rate?',
        answer: 'Our AI has demonstrated an approximately 94% accuracy rate on recommendations with high confidence scores (above 80%). However, past performance does not guarantee future results. We recommend using our recommendations as one input in your overall trading strategy, not as the sole decision-maker.',
      },
      {
        question: 'How often are recommendations updated?',
        answer: 'Recommendations are updated in real-time during market hours for Pro and Elite subscribers. Our AI continuously monitors market conditions and will alert you to significant changes. Starter plan users receive 3 updated recommendations per day.',
      },
      {
        question: 'Can I customize the AI\'s trading strategy?',
        answer: 'Elite plan subscribers can customize AI parameters including risk tolerance, sector preferences, and technical indicator weights. Enterprise clients can work with our team to develop fully custom AI models tailored to their specific trading strategies.',
      },
      {
        question: 'Does AutoTrader AI trade for me automatically?',
        answer: 'AutoTrader AI provides recommendations, but you maintain full control over your trades. When connected to a supported brokerage, you can choose to execute trades with one click or enable semi-automated trading with your pre-approval for each trade. We never execute trades without your explicit consent.',
      },
    ],
  },
  {
    name: 'Account & Billing',
    icon: '💳',
    faqs: [
      {
        question: 'What plans are available?',
        answer: 'We offer four plans: Starter (Free), Pro ($29/month), Elite ($79/month), and Enterprise (custom pricing). Each plan offers progressively more features, including more recommendations, watchlists, brokerage integrations, and support options. Annual billing saves you approximately 17%.',
      },
      {
        question: 'Can I change my plan anytime?',
        answer: 'Yes! You can upgrade or downgrade your plan at any time from your account settings. Upgrades take effect immediately with prorated billing. Downgrades take effect at the end of your current billing cycle to ensure you get the full value of your payment.',
      },
      {
        question: 'Do you offer refunds?',
        answer: 'We offer a 30-day money-back guarantee for all paid plans. If you\'re not satisfied with AutoTrader AI for any reason within the first 30 days, contact our support team for a full refund. No questions asked.',
      },
      {
        question: 'What payment methods do you accept?',
        answer: 'We accept all major credit cards (Visa, MasterCard, American Express, Discover), PayPal, and Apple Pay. Enterprise customers can also pay via bank transfer or invoice. All payments are processed securely through Stripe.',
      },
      {
        question: 'Is there a free trial for paid plans?',
        answer: 'Yes! Both Pro and Elite plans come with a 14-day free trial. You\'ll have full access to all features during the trial period. No credit card is required to start your trial—we\'ll only ask for payment information when you decide to continue.',
      },
    ],
  },
  {
    name: 'Security & Privacy',
    icon: '🔒',
    faqs: [
      {
        question: 'Is my financial data secure?',
        answer: 'Absolutely. We use bank-grade 256-bit AES encryption for all data at rest and TLS 1.3 for data in transit. Your brokerage credentials are never stored on our servers—we use secure OAuth tokens provided by brokerages. Our infrastructure is hosted on SOC 2 Type II certified cloud providers.',
      },
      {
        question: 'How do you handle my personal information?',
        answer: 'We collect only the minimum information necessary to provide our services. We never sell your personal data to third parties. Your trading data is used solely to improve your recommendations and is never shared. Read our full Privacy Policy for complete details.',
      },
      {
        question: 'Can AutoTrader AI access my brokerage account?',
        answer: 'When you connect a brokerage, you grant limited permissions through the brokerage\'s official OAuth system. We can view your holdings and execute trades you approve, but we cannot withdraw funds, change account settings, or access your banking information. You can revoke access at any time.',
      },
      {
        question: 'Is two-factor authentication available?',
        answer: 'Yes! We strongly recommend enabling two-factor authentication (2FA) on your account. We support authenticator apps (Google Authenticator, Authy) and SMS verification. 2FA is required for all Enterprise accounts.',
      },
    ],
  },
  {
    name: 'Technical',
    icon: '⚙️',
    faqs: [
      {
        question: 'Which brokerages are supported?',
        answer: 'We currently support integration with major US brokerages including Robinhood, Fidelity, Charles Schwab, E*TRADE, TD Ameritrade, and Vanguard. We\'re continuously adding new brokerages—check our integrations page for the latest list or contact us if you\'d like to see a specific broker supported.',
      },
      {
        question: 'Do you offer an API?',
        answer: 'Yes! Elite and Enterprise plans include API access. Our RESTful API allows you to integrate AutoTrader AI recommendations into your own applications, trading systems, or analysis tools. Comprehensive documentation and SDKs for Python and JavaScript are available.',
      },
      {
        question: 'What markets and assets are supported?',
        answer: 'We currently support US equities (stocks and ETFs) traded on NYSE, NASDAQ, and other major exchanges. Support for options, cryptocurrencies, and international markets is on our roadmap. Enterprise clients can request custom asset coverage.',
      },
      {
        question: 'Does AutoTrader AI work on mobile devices?',
        answer: 'Yes! Our web application is fully responsive and works great on smartphones and tablets. We\'re also developing native iOS and Android apps with push notification support for real-time alerts. Join our waitlist to be notified when mobile apps launch.',
      },
      {
        question: 'What happens if the service goes down?',
        answer: 'We maintain 99.9% uptime with redundant systems across multiple data centers. In the rare event of an outage, your connected brokerage accounts remain unaffected—we cannot execute any trades during downtime. Enterprise customers receive SLA guarantees with service credits.',
      },
    ],
  },
  {
    name: 'Support',
    icon: '💬',
    faqs: [
      {
        question: 'How can I contact support?',
        answer: 'Starter and Pro users can reach us via email at support@autotrader.ai. We typically respond within 24 hours. Elite subscribers get priority email support with 4-hour response times. Enterprise clients have access to dedicated account managers and 24/7 phone support.',
      },
      {
        question: 'Do you offer educational resources?',
        answer: 'Yes! We provide extensive educational content including video tutorials, trading strategy guides, webinars, and a knowledge base. Pro and Elite subscribers also get access to exclusive masterclasses and live Q&A sessions with trading experts.',
      },
      {
        question: 'Is there a community forum?',
        answer: 'We have an active Discord community where traders share insights, strategies, and help each other. It\'s free to join and a great way to learn from experienced traders. We also host weekly community calls to discuss market trends.',
      },
      {
        question: 'Can I request new features?',
        answer: 'Absolutely! We love hearing from our users. You can submit feature requests through our feedback portal or community forum. We regularly review and prioritize requests based on user demand. Many of our best features came from user suggestions!',
      },
    ],
  },
]

export default function FAQ() {
  const [activeCategory, setActiveCategory] = useState(faqCategories[0].name)
  const [searchQuery, setSearchQuery] = useState('')

  const filteredFAQs = searchQuery
    ? faqCategories.flatMap(cat => 
        cat.faqs.filter(faq => 
          faq.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
          faq.answer.toLowerCase().includes(searchQuery.toLowerCase())
        ).map(faq => ({ ...faq, category: cat.name }))
      )
    : null

  return (
    <PublicPageLayout>
      {/* Hero Section */}
      <section className="pt-16 pb-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <span className="inline-block px-4 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium mb-4">
            Help Center
          </span>
          <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 mb-4">
            Frequently Asked Questions
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Find answers to common questions about AutoTrader AI
          </p>

          {/* Search Bar */}
          <div className="relative max-w-xl mx-auto">
            <svg
              className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search for answers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-4 rounded-xl border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Search Results or Category View */}
      {filteredFAQs ? (
        /* Search Results */
        <section className="pb-20 px-4 sm:px-6 lg:px-8">
          <div className="max-w-3xl mx-auto">
            <p className="text-gray-600 mb-6">
              {filteredFAQs.length} result{filteredFAQs.length !== 1 ? 's' : ''} for "{searchQuery}"
            </p>
            {filteredFAQs.length > 0 ? (
              <div className="space-y-4">
                {filteredFAQs.map((faq, index) => (
                  <details
                    key={index}
                    className="group bg-white rounded-xl border border-gray-200 overflow-hidden"
                  >
                    <summary className="flex items-center justify-between p-6 cursor-pointer hover:bg-gray-50 transition-colors">
                      <div>
                        <span className="text-xs text-blue-600 font-medium mb-1 block">{faq.category}</span>
                        <span className="font-medium text-gray-900">{faq.question}</span>
                      </div>
                      <svg
                        className="w-5 h-5 text-gray-500 group-open:rotate-180 transition-transform flex-shrink-0 ml-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </summary>
                    <div className="px-6 pb-6 text-gray-600 leading-relaxed">
                      {faq.answer}
                    </div>
                  </details>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
                <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <h3 className="text-lg font-medium text-gray-900 mb-2">No results found</h3>
                <p className="text-gray-600 mb-4">Try a different search term or browse by category</p>
                <button
                  onClick={() => setSearchQuery('')}
                  className="text-blue-600 font-medium hover:underline"
                >
                  Clear search
                </button>
              </div>
            )}
          </div>
        </section>
      ) : (
        /* Category View */
        <section className="pb-20 px-4 sm:px-6 lg:px-8">
          <div className="max-w-6xl mx-auto">
            <div className="grid lg:grid-cols-4 gap-8">
              {/* Category Navigation */}
              <div className="lg:col-span-1">
                <nav className="sticky top-24 space-y-2">
                  {faqCategories.map((category) => (
                    <button
                      key={category.name}
                      onClick={() => setActiveCategory(category.name)}
                      className={`w-full text-left px-4 py-3 rounded-xl font-medium transition-all flex items-center gap-3 ${
                        activeCategory === category.name
                          ? 'bg-blue-600 text-white shadow-md'
                          : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-200'
                      }`}
                    >
                      <span className="text-xl">{category.icon}</span>
                      {category.name}
                    </button>
                  ))}
                </nav>
              </div>

              {/* FAQ Content */}
              <div className="lg:col-span-3">
                {faqCategories.map((category) => (
                  <div
                    key={category.name}
                    className={activeCategory === category.name ? 'block' : 'hidden'}
                  >
                    <div className="flex items-center gap-3 mb-6">
                      <span className="text-3xl">{category.icon}</span>
                      <h2 className="text-2xl font-bold text-gray-900">{category.name}</h2>
                    </div>
                    <div className="space-y-4">
                      {category.faqs.map((faq, index) => (
                        <details
                          key={index}
                          className="group bg-white rounded-xl border border-gray-200 overflow-hidden"
                        >
                          <summary className="flex items-center justify-between p-6 cursor-pointer hover:bg-gray-50 transition-colors">
                            <span className="font-medium text-gray-900 pr-4">{faq.question}</span>
                            <svg
                              className="w-5 h-5 text-gray-500 group-open:rotate-180 transition-transform flex-shrink-0"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </summary>
                          <div className="px-6 pb-6 text-gray-600 leading-relaxed">
                            {faq.answer}
                          </div>
                        </details>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Still Have Questions */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-gray-50">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 md:p-12">
            <div className="grid md:grid-cols-2 gap-8 items-center">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">
                  Still have questions?
                </h2>
                <p className="text-gray-600 mb-6">
                  Can't find the answer you're looking for? Our support team is here to help.
                </p>
                <div className="flex flex-col sm:flex-row gap-4">
                  <a
                    href="mailto:support@autotrader.ai"
                    className="inline-flex items-center justify-center gap-2 bg-blue-600 text-white font-medium px-6 py-3 rounded-xl hover:bg-blue-700 transition-colors"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    Email Support
                  </a>
                  <a
                    href="#"
                    className="inline-flex items-center justify-center gap-2 bg-gray-100 text-gray-700 font-medium px-6 py-3 rounded-xl hover:bg-gray-200 transition-colors"
                  >
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
                    </svg>
                    Join Discord
                  </a>
                </div>
              </div>
              <div className="hidden md:block">
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl p-8 text-center">
                  <div className="text-5xl mb-4">💬</div>
                  <p className="text-gray-600">
                    Average response time: <span className="font-semibold text-gray-900">under 4 hours</span>
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Related Links */}
      <section className="py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-8">Helpful Resources</h2>
          <div className="grid sm:grid-cols-3 gap-6">
            <Link
              to="/pricing"
              className="bg-white p-6 rounded-xl border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all group"
            >
              <div className="text-3xl mb-3">💰</div>
              <h3 className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">Pricing Plans</h3>
              <p className="text-sm text-gray-500 mt-1">Compare features & pricing</p>
            </Link>
            <Link
              to="/terms"
              className="bg-white p-6 rounded-xl border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all group"
            >
              <div className="text-3xl mb-3">📜</div>
              <h3 className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">Terms of Service</h3>
              <p className="text-sm text-gray-500 mt-1">Read our terms & conditions</p>
            </Link>
            <Link
              to="/risk-disclosure"
              className="bg-white p-6 rounded-xl border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all group"
            >
              <div className="text-3xl mb-3">⚠️</div>
              <h3 className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">Risk Disclosure</h3>
              <p className="text-sm text-gray-500 mt-1">Understand the risks involved</p>
            </Link>
          </div>
        </div>
      </section>
    </PublicPageLayout>
  )
}
