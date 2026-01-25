import { useState } from 'react'
import { Link } from 'react-router-dom'
import PublicPageLayout from '../components/PublicPageLayout'

type BillingPeriod = 'monthly' | 'yearly'

interface PlanFeature {
  text: string
  included: boolean
  highlight?: boolean
}

interface PricingPlan {
  name: string
  description: string
  monthlyPrice: number | null
  yearlyPrice: number | null
  features: PlanFeature[]
  cta: string
  popular?: boolean
  enterprise?: boolean
}

const plans: PricingPlan[] = [
  {
    name: 'Starter',
    description: 'Perfect for beginners exploring AI-powered trading',
    monthlyPrice: 0,
    yearlyPrice: 0,
    features: [
      { text: '3 AI recommendations per day', included: true },
      { text: '1 stock watchlist (up to 5 stocks)', included: true },
      { text: 'Basic technical indicators', included: true },
      { text: 'Email support', included: true },
      { text: 'Real-time market data', included: false },
      { text: 'Advanced AI signals', included: false },
      { text: 'Brokerage integration', included: false },
      { text: 'Priority support', included: false },
    ],
    cta: 'Get Started Free',
  },
  {
    name: 'Pro',
    description: 'For active traders who want the full AI advantage',
    monthlyPrice: 29,
    yearlyPrice: 290,
    popular: true,
    features: [
      { text: 'Unlimited AI recommendations', included: true, highlight: true },
      { text: '5 watchlists (up to 50 stocks each)', included: true },
      { text: 'Advanced technical indicators', included: true },
      { text: 'Real-time market data', included: true, highlight: true },
      { text: 'Advanced AI signals & alerts', included: true, highlight: true },
      { text: '1 brokerage integration', included: true },
      { text: 'Priority email support', included: true },
      { text: 'API access', included: false },
    ],
    cta: 'Start 14-Day Free Trial',
  },
  {
    name: 'Elite',
    description: 'Maximum power for professional traders',
    monthlyPrice: 79,
    yearlyPrice: 790,
    features: [
      { text: 'Everything in Pro, plus:', included: true, highlight: true },
      { text: 'Unlimited watchlists & stocks', included: true },
      { text: 'Multi-brokerage integration', included: true, highlight: true },
      { text: 'Advanced portfolio analytics', included: true },
      { text: 'Custom AI model tuning', included: true, highlight: true },
      { text: 'Full API access', included: true },
      { text: 'Dedicated account manager', included: true },
      { text: 'Phone & video support', included: true },
    ],
    cta: 'Start 14-Day Free Trial',
  },
  {
    name: 'Enterprise',
    description: 'Custom solutions for institutions & hedge funds',
    monthlyPrice: null,
    yearlyPrice: null,
    enterprise: true,
    features: [
      { text: 'Everything in Elite, plus:', included: true, highlight: true },
      { text: 'Custom AI model development', included: true },
      { text: 'Dedicated infrastructure', included: true },
      { text: 'White-label options', included: true },
      { text: 'SLA guarantees (99.9% uptime)', included: true },
      { text: 'Compliance & audit support', included: true },
      { text: 'On-premise deployment option', included: true },
      { text: '24/7 dedicated support team', included: true },
    ],
    cta: 'Contact Sales',
  },
]

const faqs = [
  {
    question: 'Can I change my plan later?',
    answer: 'Yes! You can upgrade or downgrade your plan at any time. When upgrading, you\'ll get immediate access to new features. When downgrading, changes take effect at the end of your billing cycle.',
  },
  {
    question: 'What payment methods do you accept?',
    answer: 'We accept all major credit cards (Visa, MasterCard, American Express), PayPal, and bank transfers for Enterprise plans.',
  },
  {
    question: 'Is there a free trial?',
    answer: 'Yes! Pro and Elite plans come with a 14-day free trial. No credit card required to start. The Starter plan is always free.',
  },
  {
    question: 'What happens when my trial ends?',
    answer: 'You\'ll be notified before your trial ends. If you don\'t upgrade, your account will automatically switch to the free Starter plan—you won\'t lose any data.',
  },
  {
    question: 'Do you offer refunds?',
    answer: 'We offer a 30-day money-back guarantee for all paid plans. If you\'re not satisfied, contact us for a full refund.',
  },
]

export default function Pricing() {
  const [billingPeriod, setBillingPeriod] = useState<BillingPeriod>('monthly')

  const getPrice = (plan: PricingPlan) => {
    if (plan.enterprise) return 'Custom'
    const price = billingPeriod === 'monthly' ? plan.monthlyPrice : plan.yearlyPrice
    if (price === 0) return 'Free'
    return `$${price}`
  }

  const getPeriodLabel = (plan: PricingPlan) => {
    if (plan.enterprise || plan.monthlyPrice === 0) return ''
    return billingPeriod === 'monthly' ? '/month' : '/year'
  }

  const getSavings = (plan: PricingPlan) => {
    if (!plan.monthlyPrice || !plan.yearlyPrice || plan.monthlyPrice === 0) return null
    const yearlySavings = (plan.monthlyPrice * 12) - plan.yearlyPrice
    return yearlySavings
  }

  return (
    <PublicPageLayout>
      {/* Hero Section */}
      <section className="pt-16 pb-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto text-center">
          <span className="inline-block px-4 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium mb-4">
            Simple, Transparent Pricing
          </span>
          <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 mb-4">
            Choose Your Trading Edge
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-8">
            Start free and scale as you grow. All plans include our core AI technology.
          </p>

          {/* Billing Toggle */}
          <div className="inline-flex items-center bg-gray-100 rounded-full p-1 mb-12">
            <button
              onClick={() => setBillingPeriod('monthly')}
              className={`px-6 py-2 rounded-full text-sm font-medium transition-all ${
                billingPeriod === 'monthly'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingPeriod('yearly')}
              className={`px-6 py-2 rounded-full text-sm font-medium transition-all ${
                billingPeriod === 'yearly'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Yearly
              <span className="ml-2 text-green-600 text-xs font-semibold">Save 17%</span>
            </button>
          </div>
        </div>
      </section>

      {/* Pricing Cards */}
      <section className="pb-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`relative bg-white rounded-2xl border-2 p-8 flex flex-col ${
                  plan.popular
                    ? 'border-blue-600 shadow-xl scale-105'
                    : 'border-gray-200 shadow-sm hover:shadow-md'
                } transition-all`}
              >
                {/* Popular Badge */}
                {plan.popular && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                    <span className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-semibold px-4 py-1 rounded-full">
                      Most Popular
                    </span>
                  </div>
                )}

                {/* Plan Header */}
                <div className="mb-6">
                  <h3 className="text-xl font-bold text-gray-900 mb-2">{plan.name}</h3>
                  <p className="text-gray-500 text-sm">{plan.description}</p>
                </div>

                {/* Price */}
                <div className="mb-6">
                  <div className="flex items-baseline gap-1">
                    <span className="text-4xl font-bold text-gray-900">{getPrice(plan)}</span>
                    <span className="text-gray-500">{getPeriodLabel(plan)}</span>
                  </div>
                  {billingPeriod === 'yearly' && getSavings(plan) && (
                    <p className="text-green-600 text-sm mt-1">
                      Save ${getSavings(plan)} per year
                    </p>
                  )}
                </div>

                {/* Features */}
                <ul className="space-y-3 mb-8 flex-1">
                  {plan.features.map((feature, index) => (
                    <li key={index} className="flex items-start gap-3">
                      {feature.included ? (
                        <svg className={`w-5 h-5 flex-shrink-0 ${feature.highlight ? 'text-blue-600' : 'text-green-500'}`} fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                      ) : (
                        <svg className="w-5 h-5 flex-shrink-0 text-gray-300" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                      )}
                      <span className={`text-sm ${feature.included ? (feature.highlight ? 'text-gray-900 font-medium' : 'text-gray-700') : 'text-gray-400'}`}>
                        {feature.text}
                      </span>
                    </li>
                  ))}
                </ul>

                {/* CTA Button */}
                <Link
                  to={plan.enterprise ? '/contact' : '/#login'}
                  className={`w-full py-3 px-4 rounded-xl font-medium text-center transition-colors ${
                    plan.popular
                      ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-700 hover:to-indigo-700'
                      : plan.enterprise
                      ? 'bg-gray-900 text-white hover:bg-gray-800'
                      : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
                  }`}
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature Comparison Table */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-gray-50">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-gray-900 text-center mb-12">
            Compare All Features
          </h2>
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-4 px-6 text-gray-500 font-medium">Feature</th>
                  <th className="text-center py-4 px-4 text-gray-900 font-semibold">Starter</th>
                  <th className="text-center py-4 px-4 text-blue-600 font-semibold bg-blue-50">Pro</th>
                  <th className="text-center py-4 px-4 text-gray-900 font-semibold">Elite</th>
                  <th className="text-center py-4 px-4 text-gray-900 font-semibold">Enterprise</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {[
                  { feature: 'AI Recommendations', starter: '3/day', pro: 'Unlimited', elite: 'Unlimited', enterprise: 'Unlimited' },
                  { feature: 'Watchlists', starter: '1', pro: '5', elite: 'Unlimited', enterprise: 'Unlimited' },
                  { feature: 'Stocks per Watchlist', starter: '5', pro: '50', elite: 'Unlimited', enterprise: 'Unlimited' },
                  { feature: 'Real-time Data', starter: false, pro: true, elite: true, enterprise: true },
                  { feature: 'Advanced AI Signals', starter: false, pro: true, elite: true, enterprise: true },
                  { feature: 'Brokerage Integration', starter: false, pro: '1', elite: 'Multi', enterprise: 'Unlimited' },
                  { feature: 'API Access', starter: false, pro: false, elite: true, enterprise: true },
                  { feature: 'Custom AI Tuning', starter: false, pro: false, elite: true, enterprise: true },
                  { feature: 'Dedicated Support', starter: false, pro: false, elite: true, enterprise: '24/7' },
                  { feature: 'SLA Guarantee', starter: false, pro: false, elite: false, enterprise: '99.9%' },
                ].map((row, index) => (
                  <tr key={index}>
                    <td className="py-4 px-6 text-gray-700">{row.feature}</td>
                    <td className="text-center py-4 px-4">
                      {typeof row.starter === 'boolean' ? (
                        row.starter ? (
                          <svg className="w-5 h-5 text-green-500 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        ) : (
                          <svg className="w-5 h-5 text-gray-300 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                          </svg>
                        )
                      ) : (
                        <span className="text-sm text-gray-600">{row.starter}</span>
                      )}
                    </td>
                    <td className="text-center py-4 px-4 bg-blue-50">
                      {typeof row.pro === 'boolean' ? (
                        row.pro ? (
                          <svg className="w-5 h-5 text-blue-600 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        ) : (
                          <svg className="w-5 h-5 text-gray-300 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                          </svg>
                        )
                      ) : (
                        <span className="text-sm font-medium text-blue-600">{row.pro}</span>
                      )}
                    </td>
                    <td className="text-center py-4 px-4">
                      {typeof row.elite === 'boolean' ? (
                        row.elite ? (
                          <svg className="w-5 h-5 text-green-500 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        ) : (
                          <svg className="w-5 h-5 text-gray-300 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                          </svg>
                        )
                      ) : (
                        <span className="text-sm text-gray-600">{row.elite}</span>
                      )}
                    </td>
                    <td className="text-center py-4 px-4">
                      {typeof row.enterprise === 'boolean' ? (
                        row.enterprise ? (
                          <svg className="w-5 h-5 text-green-500 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        ) : (
                          <svg className="w-5 h-5 text-gray-300 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                          </svg>
                        )
                      ) : (
                        <span className="text-sm text-gray-600">{row.enterprise}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Pricing FAQ */}
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-3xl font-bold text-gray-900 text-center mb-12">
            Frequently Asked Questions
          </h2>
          <div className="space-y-4">
            {faqs.map((faq, index) => (
              <details
                key={index}
                className="group bg-white rounded-xl border border-gray-200 overflow-hidden"
              >
                <summary className="flex items-center justify-between p-6 cursor-pointer hover:bg-gray-50 transition-colors">
                  <span className="font-medium text-gray-900">{faq.question}</span>
                  <svg
                    className="w-5 h-5 text-gray-500 group-open:rotate-180 transition-transform"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </summary>
                <div className="px-6 pb-6 text-gray-600">
                  {faq.answer}
                </div>
              </details>
            ))}
          </div>
          <div className="text-center mt-8">
            <p className="text-gray-600">
              Have more questions?{' '}
              <Link to="/faq" className="text-blue-600 hover:underline font-medium">
                Visit our full FAQ
              </Link>{' '}
              or{' '}
              <a href="mailto:support@autotrader.ai" className="text-blue-600 hover:underline font-medium">
                contact us
              </a>
            </p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-r from-blue-600 to-indigo-600">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Ready to Trade Smarter?
          </h2>
          <p className="text-xl text-blue-100 mb-8">
            Join thousands of traders using AI to maximize their returns.
          </p>
          <Link
            to="/#login"
            className="inline-flex items-center gap-2 bg-white text-blue-600 font-semibold px-8 py-4 rounded-xl hover:bg-blue-50 transition-colors"
          >
            Start Free Today
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </Link>
          <p className="text-blue-200 text-sm mt-4">
            No credit card required • Free plan available forever
          </p>
        </div>
      </section>
    </PublicPageLayout>
  )
}
