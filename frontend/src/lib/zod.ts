import { z } from 'zod'

// Строгая CSP запрещает проверку доступности new Function в Zod.
z.config({ jitless: true })

export { z }
