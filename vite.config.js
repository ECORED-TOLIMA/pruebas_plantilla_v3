const { defineConfig } = require('vite')
const vue = require('@vitejs/plugin-vue')
const path = require('path')
const titulo = require('./src/config/titulo.js')

module.exports = defineConfig(({ mode }) => {
  const fileSchemeBuild = mode === 'file'

  return {
    base: fileSchemeBuild ? './' : '/NUEVA_BASE_TOLIMA/',
    optimizeDeps: {
      // UMD de aos usa }(this,function(){…}); en ESM `this` es undefined → rompe e.AOS = …
      include: ['aos'],
    },
    build: {
      commonjsOptions: {
        defaultIsModuleExports: true,
      },
      ...(fileSchemeBuild
        ? {
            // Chrome bloquea <script type="module"> bajo file:// (origen null + CORS).
            // Un único IIFE + script clásico evita el cargador de módulos.
            cssCodeSplit: false,
            rollupOptions: {
              output: {
                format: 'iife',
                inlineDynamicImports: true,
                name: '__ecoredFileBuild',
              },
            },
          }
        : {}),
    },
    plugins: [
      vue(),
      {
        name: 'aos-umd-globalthis',
        enforce: 'pre',
        transform(code, id) {
          if (!id.includes('aos') || !id.endsWith('aos.js')) return null
          const needle = '}(this,function(){return'
          if (!code.includes(needle)) return null
          return code.replace(needle, '}(globalThis,function(){return')
        },
      },
      {
        name: 'html-title',
        transformIndexHtml(html) {
          return html.replace(/<title>.*?<\/title>/, `<title>${titulo}</title>`)
        },
      },
      fileSchemeBuild && {
        name: 'html-file-scheme-compat',
        transformIndexHtml: {
          order: 'post',
          handler(html) {
            let out = html.replace(/\s+crossorigin(?:="[^"]*")?/gi, '')
            out = out.replace(/<link[^>]*rel="modulepreload"[^>]*>/gi, '')
            out = out.replace(/<script type="module"/gi, '<script defer')
            return out
          },
        },
      },
    ].filter(Boolean),
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
      extensions: ['.vue', '.mjs', '.js', '.ts', '.jsx', '.tsx', '.json'],
    },
    server: {
      fs: {
        allow: ['.', '..'],
      },
    },
    css: {
      preprocessorOptions: {
        scss: {
          silenceDeprecations: ['legacy-js-api', 'import', 'global-builtin'],
        },
        sass: {
          additionalData: `@use "@/styles/_variables.sass" as *\n`,
          silenceDeprecations: ['legacy-js-api', 'import', 'global-builtin'],
        },
      },
    },
  }
})
