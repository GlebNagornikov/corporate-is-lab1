// Удаляем токены, оставшиеся в браузере от предыдущей версии витрины.
localStorage.removeItem('shop-access')
localStorage.removeItem('shop-refresh')

let accessToken: string | null = null
let sessionVersion = 0

export const tokens = {
  access: () => accessToken,
  version: () => sessionVersion,
  save({ access }: { access: string }) {
    accessToken = access
    sessionVersion += 1
  },
  refreshAccess(access: string) {
    accessToken = access
  },
  clear() {
    accessToken = null
    sessionVersion += 1
  },
}
