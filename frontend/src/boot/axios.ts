import { boot } from 'quasar/wrappers'
import { api } from '../services/http'

export default boot(({ app }) => {
  app.config.globalProperties.$api = api
})

export { api }
