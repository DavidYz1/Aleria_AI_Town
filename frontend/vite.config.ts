import { resolve } from 'node:path'

import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@vue/test-utils': resolve(
        __dirname,
        'node_modules/@vue/test-utils/dist/vue-test-utils.esm-bundler.mjs',
      ),
      pinia: resolve(__dirname, 'node_modules/pinia/dist/pinia.mjs'),
    },
  },
  server: {
    fs: {
      allow: [resolve(__dirname, '..')],
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['../tests/frontend/**/*.spec.ts'],
  },
})
