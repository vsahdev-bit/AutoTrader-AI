export function toFriendlyAuthErrorMessage(err: unknown): string {
  const msg = (err instanceof Error ? err.message : String(err || '')).toLowerCase()

  // Most common local-dev failure: api-gateway not running / not reachable
  if (
    msg.includes('failed to fetch') ||
    msg.includes('networkerror') ||
    msg.includes('network error') ||
    msg.includes('load failed') ||
    msg.includes('connection refused')
  ) {
    return 'Unable to reach the backend (api-gateway). Please start Docker Compose (api-gateway + postgres) and try again.'
  }

  if (msg.includes('did not return a user id')) {
    return 'Login failed because the backend did not return a valid user session. Please try again.'
  }

  return 'Login failed. Please try again.'
}
