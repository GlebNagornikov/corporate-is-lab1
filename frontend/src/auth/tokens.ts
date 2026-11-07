const ACCESS_KEY = 'shop-access'
const REFRESH_KEY = 'shop-refresh'
let sessionVersion = 0

export const tokens = {
  access: () => localStorage.getItem(ACCESS_KEY),
  refresh: () => localStorage.getItem(REFRESH_KEY),
  version: () => sessionVersion,
  save({ access, refresh }: { access: string; refresh?: string }) {
    localStorage.setItem(ACCESS_KEY, access)
    if (refresh !== undefined) {
      localStorage.setItem(REFRESH_KEY, refresh)
      sessionVersion += 1
    }
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
    sessionVersion += 1
  },
}
