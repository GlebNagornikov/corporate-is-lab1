export function nextPath(value: string | null): string {
  if (!value?.startsWith('/') || value.startsWith('//')) return '/'

  const origin = window.location.origin
  try {
    const url = new URL(value, origin)
    if (url.origin !== origin || url.pathname.startsWith('//')) return '/'
    return url.pathname + url.search + url.hash
  } catch {
    return '/'
  }
}
