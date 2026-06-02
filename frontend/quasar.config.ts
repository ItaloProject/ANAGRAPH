import { configure } from 'quasar/wrappers'

export default configure(function (/* ctx */) {
  return {
    eslint: { warnings: true, errors: true },
    boot: ['pinia', 'axios', 'oauth-redirect', 'background-sync'],
    css: ['app.scss'],
    extras: ['material-icons', 'fontawesome-v6', 'roboto-font'],
    build: {
      target: { browser: ['es2019', 'edge88', 'firefox78', 'chrome87', 'safari13.1'] },
      vueRouterMode: 'hash',
      vitePlugins: [],
    },
    devServer: {
      open: true,
      proxy: {
        '/api': {
          target: 'http://localhost:8001',
          changeOrigin: true,
        },
        '/ws': {
          target: 'ws://localhost:8001',
          ws: true,
        },
      },
    },
    framework: {
      config: {
        dark: true,
        notify: { position: 'top-right' },
      },
      plugins: ['Notify', 'Loading', 'Dialog', 'LocalStorage'],
    },
    animations: 'all',
    ssr: { pwa: false },
    pwa: {
      workboxMode: 'generateSW',
      injectPwaMetaTags: true,
      swFilename: 'sw.js',
      manifestFilename: 'manifest.json',
    },
    electron: { inspectPort: 5858 },
    bex: { extraScripts: [] },
  }
})
