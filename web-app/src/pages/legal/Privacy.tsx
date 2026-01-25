import { Link } from 'react-router-dom'
import PublicPageLayout from '../../components/PublicPageLayout'

export default function Privacy() {
  const lastUpdated = 'January 15, 2026'

  return (
    <PublicPageLayout>
      {/* Hero Section */}
      <section className="pt-16 pb-8 px-4 sm:px-6 lg:px-8 bg-gray-50">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">Privacy Policy</h1>
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
                <h2 className="text-2xl font-bold text-gray-900 mb-4">1. Introduction</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  AutoTrader AI ("Company," "we," "us," or "our") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our website, applications, and services (collectively, the "Services").
                </p>
                <p className="text-gray-600 leading-relaxed">
                  By using our Services, you consent to the data practices described in this policy. If you do not agree with our policies and practices, please do not use our Services.
                </p>
              </div>

              {/* Information We Collect */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">2. Information We Collect</h2>
                
                <h3 className="text-lg font-semibold text-gray-900 mb-3">2.1 Information You Provide</h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  We collect information you provide directly to us, including:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-6">
                  <li><strong>Account Information:</strong> Name, email address, and profile picture when you sign up via Google OAuth</li>
                  <li><strong>Profile Information:</strong> Phone number, country, timezone, and trading preferences you provide during onboarding</li>
                  <li><strong>Financial Information:</strong> Trading preferences, risk tolerance, investment goals, and watchlist data</li>
                  <li><strong>Communications:</strong> Information in emails, support tickets, or feedback you send us</li>
                </ul>

                <h3 className="text-lg font-semibold text-gray-900 mb-3">2.2 Information Collected Automatically</h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  When you use our Services, we automatically collect:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-6">
                  <li><strong>Device Information:</strong> Browser type, operating system, device identifiers</li>
                  <li><strong>Usage Data:</strong> Pages visited, features used, time spent, click patterns</li>
                  <li><strong>Log Data:</strong> IP address, access times, referring URLs</li>
                  <li><strong>Location Data:</strong> General geographic location based on IP address</li>
                </ul>

                <h3 className="text-lg font-semibold text-gray-900 mb-3">2.3 Information from Third Parties</h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  We may receive information from third parties, including:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2">
                  <li><strong>Google OAuth:</strong> Basic profile information when you sign in with Google</li>
                  <li><strong>Brokerage Integrations:</strong> Account holdings, positions, and transaction history (with your authorization)</li>
                  <li><strong>Payment Processors:</strong> Transaction confirmations (we do not store full payment card details)</li>
                </ul>
              </div>

              {/* How We Use Information */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">3. How We Use Your Information</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  We use the information we collect to:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2">
                  <li>Provide, maintain, and improve our Services</li>
                  <li>Generate personalized trading recommendations based on your preferences</li>
                  <li>Process transactions and send related information</li>
                  <li>Send technical notices, updates, security alerts, and support messages</li>
                  <li>Respond to your comments, questions, and customer service requests</li>
                  <li>Monitor and analyze trends, usage, and activities</li>
                  <li>Detect, prevent, and address fraud and security issues</li>
                  <li>Personalize and improve your experience</li>
                  <li>Send promotional communications (with your consent)</li>
                  <li>Comply with legal obligations</li>
                </ul>
              </div>

              {/* Data Sharing */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">4. How We Share Your Information</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  We do not sell your personal information. We may share your information in the following circumstances:
                </p>
                
                <h3 className="text-lg font-semibold text-gray-900 mb-3">4.1 Service Providers</h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  We share information with third-party vendors who perform services on our behalf, including:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-6">
                  <li>Cloud hosting providers (AWS, Google Cloud)</li>
                  <li>Payment processors (Stripe)</li>
                  <li>Analytics providers (Google Analytics)</li>
                  <li>Customer support tools</li>
                  <li>Email service providers</li>
                </ul>

                <h3 className="text-lg font-semibold text-gray-900 mb-3">4.2 Brokerage Partners</h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  When you connect a brokerage account, we share necessary information to facilitate the connection and enable trading features. This is done through secure OAuth protocols.
                </p>

                <h3 className="text-lg font-semibold text-gray-900 mb-3">4.3 Legal Requirements</h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  We may disclose information if required by law or in response to valid legal requests, such as subpoenas, court orders, or government regulations.
                </p>

                <h3 className="text-lg font-semibold text-gray-900 mb-3">4.4 Business Transfers</h3>
                <p className="text-gray-600 leading-relaxed">
                  In the event of a merger, acquisition, or sale of assets, your information may be transferred to the acquiring entity.
                </p>
              </div>

              {/* Data Security */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">5. Data Security</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  We implement robust security measures to protect your information:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-4">
                  <li><strong>Encryption:</strong> 256-bit AES encryption for data at rest; TLS 1.3 for data in transit</li>
                  <li><strong>Authentication:</strong> Secure OAuth 2.0 for third-party integrations; optional two-factor authentication</li>
                  <li><strong>Access Controls:</strong> Role-based access controls for employees; regular access audits</li>
                  <li><strong>Infrastructure:</strong> SOC 2 Type II certified cloud infrastructure</li>
                  <li><strong>Monitoring:</strong> 24/7 security monitoring and intrusion detection</li>
                </ul>
                <p className="text-gray-600 leading-relaxed">
                  While we strive to protect your information, no method of transmission or storage is 100% secure. We cannot guarantee absolute security.
                </p>
              </div>

              {/* Cookies */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">6. Cookies and Tracking Technologies</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  We use cookies and similar technologies to:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-4">
                  <li>Keep you logged in and remember your preferences</li>
                  <li>Understand how you use our Services</li>
                  <li>Improve performance and user experience</li>
                  <li>Provide relevant content and features</li>
                </ul>
                
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Types of Cookies We Use:</h3>
                <ul className="list-disc pl-6 text-gray-600 space-y-2 mb-4">
                  <li><strong>Essential Cookies:</strong> Required for the Services to function properly</li>
                  <li><strong>Analytics Cookies:</strong> Help us understand usage patterns</li>
                  <li><strong>Preference Cookies:</strong> Remember your settings and preferences</li>
                </ul>
                <p className="text-gray-600 leading-relaxed">
                  You can control cookies through your browser settings. Note that disabling certain cookies may affect functionality.
                </p>
              </div>

              {/* Your Rights */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">7. Your Rights and Choices</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  Depending on your location, you may have the following rights:
                </p>

                <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
                  <h3 className="text-lg font-semibold text-blue-900 mb-3">For All Users:</h3>
                  <ul className="list-disc pl-6 text-blue-800 space-y-2">
                    <li><strong>Access:</strong> Request a copy of your personal information</li>
                    <li><strong>Correction:</strong> Update or correct inaccurate information</li>
                    <li><strong>Deletion:</strong> Request deletion of your account and data</li>
                    <li><strong>Portability:</strong> Receive your data in a portable format</li>
                    <li><strong>Opt-out:</strong> Unsubscribe from marketing communications</li>
                  </ul>
                </div>

                <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6">
                  <h3 className="text-lg font-semibold text-green-900 mb-3">For California Residents (CCPA):</h3>
                  <ul className="list-disc pl-6 text-green-800 space-y-2">
                    <li>Right to know what personal information is collected</li>
                    <li>Right to delete personal information</li>
                    <li>Right to opt-out of sale of personal information (we do not sell data)</li>
                    <li>Right to non-discrimination for exercising your rights</li>
                  </ul>
                </div>

                <div className="bg-purple-50 border border-purple-200 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-purple-900 mb-3">For EU/UK Residents (GDPR):</h3>
                  <ul className="list-disc pl-6 text-purple-800 space-y-2">
                    <li>Right to access, rectification, and erasure</li>
                    <li>Right to restrict or object to processing</li>
                    <li>Right to data portability</li>
                    <li>Right to withdraw consent</li>
                    <li>Right to lodge a complaint with a supervisory authority</li>
                  </ul>
                </div>

                <p className="text-gray-600 leading-relaxed mt-6">
                  To exercise these rights, contact us at privacy@autotrader.ai. We will respond within 30 days.
                </p>
              </div>

              {/* Data Retention */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">8. Data Retention</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  We retain your information for as long as necessary to provide our Services and fulfill the purposes described in this policy. Specifically:
                </p>
                <ul className="list-disc pl-6 text-gray-600 space-y-2">
                  <li><strong>Account Data:</strong> Retained while your account is active and for 30 days after deletion request</li>
                  <li><strong>Transaction Records:</strong> Retained for 7 years for legal and regulatory compliance</li>
                  <li><strong>Usage Analytics:</strong> Aggregated and anonymized data may be retained indefinitely</li>
                  <li><strong>Marketing Preferences:</strong> Retained until you opt-out</li>
                </ul>
              </div>

              {/* Children's Privacy */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">9. Children's Privacy</h2>
                <p className="text-gray-600 leading-relaxed">
                  Our Services are not intended for individuals under 18 years of age. We do not knowingly collect personal information from children. If we become aware that we have collected information from a child, we will take steps to delete it promptly. If you believe we have collected information from a child, please contact us at privacy@autotrader.ai.
                </p>
              </div>

              {/* International Transfers */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">10. International Data Transfers</h2>
                <p className="text-gray-600 leading-relaxed">
                  Your information may be transferred to and processed in countries other than your own. We ensure appropriate safeguards are in place, including Standard Contractual Clauses approved by relevant authorities, to protect your information during international transfers.
                </p>
              </div>

              {/* Changes */}
              <div className="mb-10">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">11. Changes to This Policy</h2>
                <p className="text-gray-600 leading-relaxed">
                  We may update this Privacy Policy from time to time. We will notify you of material changes by posting the updated policy on our website and updating the "Last updated" date. For significant changes, we may also send you an email notification. Your continued use of the Services after changes constitutes acceptance of the updated policy.
                </p>
              </div>

              {/* Contact */}
              <div className="mb-6">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">12. Contact Us</h2>
                <p className="text-gray-600 leading-relaxed mb-4">
                  If you have questions about this Privacy Policy or our data practices, please contact us:
                </p>
                <div className="bg-gray-50 rounded-lg p-6">
                  <p className="text-gray-700 mb-2"><strong>AutoTrader AI - Privacy Team</strong></p>
                  <p className="text-gray-600">Email: privacy@autotrader.ai</p>
                  <p className="text-gray-600">General Support: support@autotrader.ai</p>
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
