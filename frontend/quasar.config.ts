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

      extendManifestJson (json) {
        // Garante que o manifest gerado herda tudo do nosso public/manifest.json
        json.name        = 'ANAGRAPH — AI Trading Bot'
        json.short_name  = 'ANAGRAPH'
        json.description = 'Bot de trading IA para Deriv — opera 24h no servidor'
        json.theme_color = '#00D4FF'
        json.background_color = '#080d1a'
        json.display     = 'standalone'
        json.start_url   = '/#/live'
        json.lang        = 'pt-BR'
        json.prefer_related_applications = false
        return json
      },

      workboxOptions: {
        // Pré-cache dos assets do app (shell)
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],

        // Estratégias de cache por tipo de recurso
        runtimeCaching: [

          // API do backend — Network First (dados ao vivo têm prioridade)
          {
            urlPattern: /\/api\//,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 50, maxAgeSeconds: 60 },
            },
          },

          // Fontes Google / CDN — Cache First (raramente mudam)
          {
            urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'fonts-cache',
              expiration: { maxEntries: 20, maxAgeSeconds: 60 * 60 * 24 * 365 },
            },
          },

          // Deriv API — Network Only (dados financeiros não podem ser stale)
          {
            urlPattern: /\.(derivws|deriv)\.com/,
            handler: 'NetworkOnly',
          },
        ],
      },
    },

    electron: { inspectPort: 5858 },
    bex: { extraScripts: [] },
  }
})
