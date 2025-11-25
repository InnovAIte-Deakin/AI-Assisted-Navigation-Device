// eslint.config.js

const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  expoConfig,

  {
    ignores: [
      'dist/*',
      'build/*',
      'node_modules/*',
      '.expo/*',
      '.expo-shared/*'
    ],

    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        __DEV__: 'readonly'
      }
    },

    rules: {
      // React Native sanity
      'react-native/no-inline-styles': 'warn',
      'react-native/no-unused-styles': 'error',

      // Consistent imports
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],

      // Avoid accidental console spam
      'no-console': ['warn', { allow: ['warn', 'error'] }],

      // Clean code, but not obnoxious
      'no-multiple-empty-lines': ['warn', { max: 1 }],
      'prefer-const': 'warn',

      // Allow JSX in TSX only
      'react/jsx-filename-extension': [
        'error',
        { extensions: ['.tsx'] }
      ],

      // Prevent accidental any’s in TSX component files
      '@typescript-eslint/no-explicit-any': 'warn'
    }
  }
]);