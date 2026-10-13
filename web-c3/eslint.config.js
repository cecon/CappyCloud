import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';
import { defineConfig, globalIgnores } from 'eslint/config';

export default defineConfig([
  globalIgnores(['node_modules', 'dist', 'coverage']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, tseslint.configs.recommended, reactHooks.configs.flat.recommended, reactRefresh.configs.vite],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    rules: {
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      // Telas falam com a API só por src/data (specs/013, research R3).
      'no-restricted-imports': ['error', { patterns: [{ group: ['@cappy/*', '@/*'], message: 'Importe de "data", não do web/ direto.' }] }]
    }
  },
  {
    files: ['src/data/**'],
    rules: { 'no-restricted-imports': 'off' }
  }
]);
