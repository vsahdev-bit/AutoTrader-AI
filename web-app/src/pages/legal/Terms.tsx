import { Link } from 'react-router-dom'
import PublicPageLayout from '../../components/PublicPageLayout'

export default function Terms() {
  const lastUpdated = 'January 15, 2026'

  return (
    <PublicPageLayout>
      {/* Hero Section */}
      <section className="pt-16 pb-8 px-4 sm:px-6 lg:px-8 bg-gray-50">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">Terms of Service</h1>
          <p className="text-gray-600">
            Last updated: {lastUpdated}
          </p>
        </div>
      </section>

      {/* Content */}
      <section className="py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 md:p-12">
            <div className="prose prose-gray max-w-none">
              
              {/* Introduction */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">1. Introduction and Acceptance</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  Welcome to AutoTrader AI ("Company," "we," "us," or "our"). These Terms of Service ("Terms") govern your access to and use of our website, applications, and services (collectively, the "Services").
                </p>
                <p className="text-gray-600 leading-relaxed mb-4">
                  By accessing or using our Services, you agree to be bound by these Terms and our Privacy Policy. If you do not agree to these Terms, you may not access or use the Services.
                </p>
                <p className="text-gray-600 leading-relaxed">
                  We reserve the right to modify these Terms at any time. We will notify you of material changes by posting the updated Terms on our website and updating the "Last updated" date. Your continued use of the Services after such changes constitutes acceptance of the modified Terms.
                </p>
              </div>

              {/* Eligibility */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">2. Eligibility</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  To use our Services, you must:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-4">
                  <li>Be at least 18 years of age</li>
                  <li>Have the legal capacity to enter into a binding agreement</li>
                  <li>Not be prohibited from using the Services under applicable law</li>
                  <li>Reside in a jurisdiction where our Services are available</li>
                </ul>
                <p className="text-gray-600 leading-relaxed">
                  By using the Services, you represent and warrant that you meet all eligibility requirements.
                </p>
              </div>

              {/* Account Registration */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">3. Account Registration</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  To access certain features of our Services, you must create an account. When registering, you agree to:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-4">
                  <li>Provide accurate, current, and complete information</li>
                  <li>Maintain and promptly update your account information</li>
                  <li>Keep your login credentials secure and confidential</li>
                  <li>Notify us immediately of any unauthorized access to your account</li>
                  <li>Accept responsibility for all activities under your account</li>
                </ul>
                <p className="text-gray-600 leading-relaxed">
                  We reserve the right to suspend or terminate accounts that violate these Terms or engage in suspicious activity.
                </p>
              </div>

              {/* Services Description */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">4. Description of Services</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  AutoTrader AI provides AI-powered trading recommendations and analysis tools. Our Services include:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-4">
                  <li>AI-generated trading recommendations (buy, sell, hold signals)</li>
                  <li>Technical and sentiment analysis</li>
                  <li>Portfolio tracking and watchlist management</li>
                  <li>Integration with supported brokerage accounts</li>
                  <li>Educational content and market insights</li>
                </ul>
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 my-6">
                  <p className="text-yellow-800 font-medium">
                    ⚠️ Important: Our Services provide information and recommendations only. We do not provide personalized investment advice, and our recommendations should not be considered as such. You are solely responsible for your trading decisions.
                  </p>
                </div>
              </div>

              {/* Subscription and Payments */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">5. Subscription and Payments</h2>
                <h3 className="text-lg font-semibold text-gray-900 mb-3">5.1 Subscription Plans</h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  We offer various subscription plans with different features and pricing. Details of current plans are available on our Pricing page. We reserve the right to modify pricing with 30 days' notice.
                </p>
                
                <h3 className="text-lg font-semibold text-gray-900 mb-3">5.2 Billing</h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  Paid subscriptions are billed in advance on a monthly or annual basis. By subscribing, you authorize us to charge your payment method for recurring fees until you cancel.
                </p>
                
                <h3 className="text-lg font-semibold text-gray-900 mb-3">5.3 Free Trials</h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  We may offer free trials for certain plans. At the end of a trial, your subscription will automatically convert to a paid subscription unless you cancel before the trial ends.
                </p>
                
                <h3 className="text-lg font-semibold text-gray-900 mb-3">5.4 Refunds</h3>
                <p className="text-gray-600 leading-relaxed">
                  We offer a 30-day money-back guarantee for new subscribers. After this period, subscription fees are non-refundable except as required by law. Contact support@autotrader.ai for refund requests.
                </p>
              </div>

              {/* Brokerage Integration */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">6. Brokerage Integration</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  Our Services may allow you to connect third-party brokerage accounts. By connecting a brokerage account, you:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-4">
                  <li>Authorize us to access account information as permitted by the brokerage</li>
                  <li>Acknowledge that we are not affiliated with any brokerage</li>
                  <li>Understand that trades are executed by your brokerage, not by us</li>
                  <li>Accept that connection issues may occur due to third-party systems</li>
                </ul>
                <p className="text-gray-600 leading-relaxed">
                  We do not have access to your brokerage login credentials. Authentication is handled securely through the brokerage's official OAuth system.
                </p>
              </div>

              {/* User Responsibilities */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">7. User Responsibilities</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  You agree not to:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-4">
                  <li>Use the Services for any unlawful purpose</li>
                  <li>Attempt to gain unauthorized access to our systems</li>
                  <li>Interfere with or disrupt the Services</li>
                  <li>Reverse engineer or attempt to extract source code</li>
                  <li>Share your account credentials with others</li>
                  <li>Use automated systems to access the Services without permission</li>
                  <li>Resell or redistribute our Services without authorization</li>
                  <li>Violate any applicable laws or regulations</li>
                </ul>
              </div>

              {/* Intellectual Property */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">8. Intellectual Property</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  All content, features, and functionality of the Services—including but not limited to text, graphics, logos, algorithms, and software—are owned by AutoTrader AI and protected by intellectual property laws.
                </p>
                <p className="text-gray-600 leading-relaxed">
                  We grant you a limited, non-exclusive, non-transferable license to access and use the Services for personal, non-commercial purposes in accordance with these Terms.
                </p>
              </div>

              {/* Disclaimers */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">9. Disclaimers</h2>
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 my-4">
                  <p className="text-red-800 leading-relaxed mb-4">
                    <strong>THE SERVICES ARE PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED.</strong>
                  </p>
                  <p className="text-red-800 leading-relaxed mb-4">
                    We do not warrant that:
                  </p>
                  <ul className="list-disc pl-6 text-red-800 space-y-2">
                    <li>The Services will be uninterrupted or error-free</li>
                    <li>Any recommendations will result in profitable trades</li>
                    <li>The information provided is accurate or complete</li>
                    <li>The Services will meet your specific requirements</li>
                  </ul>
                </div>
                <p className="text-gray-600 leading-relaxed">
                  Trading involves substantial risk of loss. Past performance does not guarantee future results. Please read our <Link to="/risk-disclosure" className="text-blue-600 hover:underline">Risk Disclosure</Link> for complete information.
                </p>
              </div>

              {/* Limitation of Liability */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">10. Limitation of Liability</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  TO THE MAXIMUM EXTENT PERMITTED BY LAW, AUTOTRADER AI SHALL NOT BE LIABLE FOR:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-4">
                  <li>Any indirect, incidental, special, consequential, or punitive damages</li>
                  <li>Loss of profits, revenue, data, or business opportunities</li>
                  <li>Trading losses or investment losses of any kind</li>
                  <li>Damages arising from your reliance on our recommendations</li>
                </ul>
                <p className="text-gray-600 leading-relaxed">
                  Our total liability for any claims arising from these Terms or your use of the Services shall not exceed the amount you paid us in the 12 months preceding the claim.
                </p>
              </div>

              {/* Indemnification */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">11. Indemnification</h2>
                <p className="text-gray-600 leading-relaxed">
                  You agree to indemnify and hold harmless AutoTrader AI, its officers, directors, employees, and agents from any claims, damages, losses, or expenses (including reasonable attorneys' fees) arising from your use of the Services, violation of these Terms, or infringement of any third-party rights.
                </p>
              </div>

              {/* Termination */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">12. Termination</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  You may terminate your account at any time through your account settings or by contacting support. We may suspend or terminate your access to the Services at our discretion, including for:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-4">
                  <li>Violation of these Terms</li>
                  <li>Fraudulent or illegal activity</li>
                  <li>Non-payment of fees</li>
                  <li>Extended periods of inactivity</li>
                </ul>
                <p className="text-gray-600 leading-relaxed">
                  Upon termination, your right to use the Services will immediately cease. Provisions that by their nature should survive termination will remain in effect.
                </p>
              </div>

              {/* Governing Law */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">13. Governing Law and Disputes</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  These Terms shall be governed by and construed in accordance with the laws of the State of Delaware, United States, without regard to conflict of law principles.
                </p>
                <p className="text-gray-600 leading-relaxed">
                  Any disputes arising from these Terms or the Services shall be resolved through binding arbitration in accordance with the American Arbitration Association's rules, except that either party may seek injunctive relief in any court of competent jurisdiction.
                </p>
              </div>

              {/* Miscellaneous */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">14. Miscellaneous</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  <strong>Entire Agreement:</strong> These Terms, together with our Privacy Policy and any other agreements referenced herein, constitute the entire agreement between you and AutoTrader AI.
                </p>
                <p className="text-gray-600 leading-relaxed mb-4">
                  <strong>Severability:</strong> If any provision of these Terms is found unenforceable, the remaining provisions will continue in effect.
                </p>
                <p className="text-gray-600 leading-relaxed mb-4">
                  <strong>Waiver:</strong> Our failure to enforce any right or provision shall not constitute a waiver of such right or provision.
                </p>
                <p className="text-gray-600 leading-relaxed">
                  <strong>Assignment:</strong> You may not assign these Terms without our prior written consent. We may assign these Terms at any time without notice.
                </p>
              </div>

              {/* Contact */}
              <div className="mb-6">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">15. Contact Information</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  If you have any questions about these Terms, please contact us:
                </p>
                <div className="bg-gray-50 rounded-lg p-6">
                  <p className="text-gray-700 mb-2"><strong>AutoTrader AI</strong></p>
                  <p className="text-gray-600">Email: legal@autotrader.ai</p>
                  <p className="text-gray-600">Support: support@autotrader.ai</p>
                </div>
              </div>

            </div>
          </div>

          {/* Related Links */}
          <div className="mt-8 flex flex-wrap gap-4 justify-center">
            <Link
              to="/privacy"
              className="text-blue-600 hover:underline font-medium"
            >
              Privacy Policy →
            </Link>
            <Link
              to="/risk-disclosure"
              className="text-blue-600 hover:underline font-medium"
            >
              Risk Disclosure →
            </Link>
          </div>
        </div>
      </section>
    </PublicPageLayout>
  )
}
