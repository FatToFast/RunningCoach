import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist', 'src/types/generated']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // Enforce use of format utilities instead of manual formatting
      // Allows Math.* in utils/format.ts but warns elsewhere
      'no-restricted-syntax': [
        'warn',
        {
          selector: "CallExpression[callee.object.name='Math'][callee.property.name='floor']",
          message: 'Prefer using format utilities from @/utils/format.ts instead of Math.floor for time/distance calculations',
        },
      ],
      // Prefer const over let when variable is not reassigned
      'prefer-const': 'warn',
      // Warn on unused vars but allow underscore prefix
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    },
  },
  // Allow Math.* in format utilities
  {
    files: ['**/utils/format.ts', '**/components/**/*.tsx'],
    rules: {
      'no-restricted-syntax': 'off',
    },
  },
])
