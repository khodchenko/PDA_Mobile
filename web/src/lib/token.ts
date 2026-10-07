const TOKEN_KEY = "stalker-pda.token"

export function readStoredToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function storeToken(token: string | null): void {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token)
    else window.localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Private mode on some Android browsers: the token lives for this tab only.
  }
}

/** Accepts a bare token or the full link from the QR code. */
export function parseTokenInput(input: string): string | null {
  const text = input.trim()
  if (!text) return null
  const match = text.match(/[?&]token=([^&#\s]+)/)
  if (match) return decodeURIComponent(match[1])
  if (/^[A-Za-z0-9_-]{8,}$/.test(text)) return text
  return null
}

/** Takes ?token= from the address bar and removes it so it is not shared by accident. */
export function takeTokenFromUrl(): string | null {
  const url = new URL(window.location.href)
  const token = url.searchParams.get("token")
  if (!token) return null
  url.searchParams.delete("token")
  window.history.replaceState(null, "", url.pathname + url.search + url.hash)
  return token
}
