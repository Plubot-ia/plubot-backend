import js from '@eslint/js';
import globals from 'globals';

import babelParser from '@babel/eslint-parser';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import importPlugin from 'eslint-plugin-import';
import promisePlugin from 'eslint-plugin-promise';
import securityPlugin from 'eslint-plugin-security';
import sonarjs from 'eslint-plugin-sonarjs';
import unicorn from 'eslint-plugin-unicorn';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import prettierPlugin from 'eslint-plugin-prettier';
import prettierConfig from 'eslint-config-prettier';



// Configuración compartida para resolver alias de Vite y React
const sharedSettings = {
  'import/resolver': {
    typescript: {},
    node: {
      extensions: ['.js', '.jsx', '.ts', '.tsx'],
    },
  },
  react: {
    version: 'detect',
  },
};

// Create a sanitized version of browser globals
const sanitizedGlobals = { ...globals.browser };
delete sanitizedGlobals['AudioWorkletGlobalScope '];
sanitizedGlobals.AudioWorkletGlobalScope = true;

export default [
  {
    // Configuración para archivos de build y configuración (ej. vite.config.js, eslint.config.js)
    // Habilita los globals de Node.js para evitar errores como 'process is not defined'.
    files: ['**/*config.js', '**/*config.mjs'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },
  {
    // Patrones de archivos y directorios a ignorar, sincronizados con .gitignore
    // para asegurar que los archivos no rastreados no sean analizados por el linter.
    ignores: [
      // Directorios de compilación y dependencias
      'dist/',
      'dist-ssr/',
      'build/',
      'node_modules/',
      '.vite/',
      '.vercel/',
      
      // Logs
      '*.log',
      '*.log.*',
      'npm-debug.log*',
      'yarn-debug.log*',
      'yarn-error.log*',
      'pnpm-debug.log*',
      'lerna-debug.log*',

      // Archivos de entorno
      '.env',
      '.env.*',
      '!.env.example',

      // Archivos de sistema y editor
      '.DS_Store',
      '.Trash/',
      '.idea/',
      '.vscode/',

      // Cache y reportes
      'coverage/',
      '*.lcov',
      '.nyc_output/',
      '.eslintcache',
      '.stylelintcache',

      // Archivos temporales y backups
      '*.db',
      '*.pyc',
      '__pycache__/',
      '*.bak',
      '*.backup',
      '*.temp.jsx',
      '**/backup/',
      'backup-old-files/',
      'Plubot-backup-*/',
      'Plubot-backup-2025-05-09/',

      // Archivos no relacionados con el frontend
      'plubot-backend/',
      'PAGROK/',
      'edge-fix.js',
      'fix_edge_type.js',
      'dump.rdb',
      'plubot.py',
      'plubots6.py',
      'static/js/create-claude.js',

      // Otros
      '*.local',
    ],
  },

  // === CONFIGURACIÓN PARA ARCHIVOS JS/JSX ===
  {
    files: ['src/**/*.{js,mjs,cjs,jsx}'],
    languageOptions: {
      globals: sanitizedGlobals,
      parser: babelParser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
        requireConfigFile: false,
        babelOptions: {
          presets: ['@babel/preset-react'],
        },
      },
    },
    plugins: {
      react,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      'jsx-a11y': jsxA11y,
      import: importPlugin,
      promise: promisePlugin,
      security: securityPlugin,
      sonarjs,
      unicorn,
      prettier: prettierPlugin,
    },
    settings: sharedSettings,
    rules: {
      // === PRETTIER ===
      'prettier/prettier': 'error',
      
      // === REGLAS BASE ===
      ...js.configs.recommended.rules,
      ...sonarjs.configs.recommended.rules,
      ...unicorn.configs.recommended.rules,
      // Las reglas de Prettier se aplican al final del archivo para anular conflictos.
      'unicorn/filename-case': ['warn', { 'case': 'kebabCase' }], // ADVERTENCIA: Temporalmente como advertencia para no bloquear refactors.

      // === REGLAS REACT ===
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'warn', // ADVERTENCIA: Pasado a warn. Idealmente usar TS.
      'react/jsx-uses-react': 'off',
      'react/jsx-uses-vars': 'error',
      'react/no-unescaped-entities': 'warn',
      'react/no-unknown-property': 'error',
      'react/self-closing-comp': 'error',
      'react/jsx-boolean-value': ['error', 'never'],
      'react/jsx-curly-brace-presence': ['error', { props: 'never', children: 'never' }],
      'react/jsx-fragments': ['error', 'syntax'],
      'react/jsx-no-useless-fragment': 'error',
      'react/no-array-index-key': 'warn',
      'react/no-children-prop': 'error',
      'react/no-danger': 'error',
      'react/no-deprecated': 'error',
      'react/no-direct-mutation-state': 'error',
      'react/no-find-dom-node': 'error',
      'react/no-is-mounted': 'error',
      'react/no-redundant-should-component-update': 'error',
      'react/no-render-return-value': 'error',
      'react/no-string-refs': 'error',
      'react/no-this-in-sfc': 'error',
      'react/no-typos': 'error',
      'react/no-unsafe': 'error',
      'react/no-unused-prop-types': 'error',
      'react/no-unused-state': 'error',
      'react/prefer-es6-class': 'error',
      'react/prefer-stateless-function': 'error',
      'react/require-render-return': 'error',
      'react/sort-comp': 'error',
      'react/void-dom-elements-no-children': 'error',
      
      // === ACCESIBILIDAD (jsx-a11y) ===
      ...jsxA11y.configs.recommended.rules,
      'jsx-a11y/alt-text': 'error',
      'jsx-a11y/anchor-has-content': 'error',
      'jsx-a11y/anchor-is-valid': 'error',
      'jsx-a11y/aria-activedescendant-has-tabindex': 'error',
      'jsx-a11y/aria-props': 'error',
      'jsx-a11y/aria-proptypes': 'error',
      'jsx-a11y/aria-role': 'error',
      'jsx-a11y/aria-unsupported-elements': 'error',
      'jsx-a11y/click-events-have-key-events': 'error',
      'jsx-a11y/heading-has-content': 'error',
      'jsx-a11y/html-has-lang': 'error',
      'jsx-a11y/img-redundant-alt': 'error',
      'jsx-a11y/interactive-supports-focus': 'error',
      'jsx-a11y/label-has-associated-control': 'error',
      'jsx-a11y/mouse-events-have-key-events': 'error',
      'jsx-a11y/no-access-key': 'error',
      'jsx-a11y/no-autofocus': 'error',
      'jsx-a11y/no-distracting-elements': 'error',
      'jsx-a11y/no-redundant-roles': 'error',
      'jsx-a11y/role-has-required-aria-props': 'error',
      'jsx-a11y/role-supports-aria-props': 'error',
      'jsx-a11y/scope': 'error',
      'jsx-a11y/tabindex-no-positive': 'error',
      
      // === IMPORTS/EXPORTS ===
      ...importPlugin.configs.recommended.rules,
      'react-hooks/exhaustive-deps': 'warn', // ADVERTENCIA: Pasado a warn. Es importante pero puede ser ruidoso.
      'import/order': ['warn', {
        groups: [
          'builtin',
          'external',
          'internal',
          'parent',
          'sibling',
          'index',
        ],
        'newlines-between': 'always',
        alphabetize: { order: 'asc', caseInsensitive: true },
      }],
      'import/no-unresolved': 'warn', // ADVERTENCIA: Pasado a warn. Puede ser problemático con alias.
      'import/no-duplicates': 'error',
      'import/no-unused-modules': 'error',
      'import/no-cycle': 'error',
      'import/no-self-import': 'error',
      'import/no-useless-path-segments': 'error',
      'import/newline-after-import': 'error',
      'import/no-anonymous-default-export': 'error',
      'import/prefer-default-export': 'off',
      'import/named': 'error',
      'import/default': 'error',
      'import/namespace': 'error',
      
      // === PROMESAS ===
      ...promisePlugin.configs.recommended.rules,
      'promise/always-return': 'off', // Desactivada para evitar conflictos con Unicorn
      'promise/catch-or-return': 'error',
      'promise/no-callback-in-promise': 'error',
      'promise/no-nesting': 'error',
      'promise/no-promise-in-callback': 'error',
      'promise/no-return-wrap': 'error',
      'promise/param-names': 'error',
      'promise/valid-params': 'error',
      
      // === SEGURIDAD ===
      ...securityPlugin.configs.recommended.rules,
      'security/detect-buffer-noassert': 'error',
      'security/detect-child-process': 'error',
      'security/detect-disable-mustache-escape': 'error',
      'security/detect-eval-with-expression': 'error',
      'security/detect-new-buffer': 'error',
      'security/detect-no-csrf-before-method-override': 'error',
      'security/detect-non-literal-fs-filename': 'error',
      'security/detect-non-literal-regexp': 'error',
      'security/detect-non-literal-require': 'error',
      'security/detect-object-injection': 'warn', // ADVERTENCIA: Pasado a warn por posibles falsos positivos.
      'security/detect-possible-timing-attacks': 'error',
      'security/detect-pseudoRandomBytes': 'error',
      'security/detect-unsafe-regex': 'error',
      
      // === VARIABLES Y FUNCIONES ===
      'no-unused-vars': ['warn', { 
        varsIgnorePattern: '^[A-Z_]|^_',
        argsIgnorePattern: '^_',
        ignoreRestSiblings: true,
        destructuredArrayIgnorePattern: '^_'
      }],
      'no-undef': 'error',
      'no-redeclare': 'error',
      'no-shadow': 'error',
      'no-shadow-restricted-names': 'error',
      'prefer-const': 'error',
      'no-var': 'error',
      'no-use-before-define': ['error', { functions: false, classes: true, variables: true }],
      'no-unused-expressions': ['error', { allowShortCircuit: true, allowTernary: true }],
      
      // === CALIDAD DE CÓDIGO ===
      'eqeqeq': ['error', 'always', { null: 'ignore' }],
      'no-console': 'warn', // ADVERTENCIA: Pasado a warn para permitir logs en desarrollo.
      'no-debugger': 'error',
      'no-alert': 'error',
      'no-eval': 'error',
      'no-implied-eval': 'error',
      'no-script-url': 'error',
      'no-with': 'error',
      'no-void': 'error',
      'no-useless-concat': 'error',
      'no-useless-return': 'warn',
      'no-unreachable': 'error',
      'no-unreachable-loop': 'error',
      'no-duplicate-case': 'error',
      'no-fallthrough': 'error',
      'no-empty': ['error', { allowEmptyCatch: true }],
      'no-empty-function': 'error',
      'no-lonely-if': 'error',
      'no-nested-ternary': 'warn', // ADVERTENCIA: Pasado a warn.
      'no-unneeded-ternary': 'error',
      'complexity': ['warn', 15], // ADVERTENCIA: Límite de complejidad aumentado temporalmente a 15.
      'max-depth': ['error', 4], // Limita la anidación de bloques
      'max-lines-per-function': ['warn', { max: 150, skipBlankLines: true, skipComments: true }], // ADVERTENCIA: Límite de líneas por función aumentado a 150.
      'max-params': ['warn', 5], // ADVERTENCIA: Pasado a warn y aumentado a 5.
      
      // === ARRAYS Y OBJETOS ===
      'no-array-constructor': 'error',
      'no-new-object': 'error',
      'object-shorthand': 'error',
      'prefer-destructuring': ['error', {
        array: true,
        object: true
      }, {
        enforceForRenamedProperties: false
      }],
      'prefer-object-spread': 'error',
      'prefer-spread': 'error',
      'prefer-template': 'error',
      
      // === PROMESAS Y ASYNC/AWAIT ===
      'no-async-promise-executor': 'error',
      'no-await-in-loop': 'warn',
      'no-promise-executor-return': 'error',
      'prefer-promise-reject-errors': 'error',
      'require-atomic-updates': 'error',
      
      // === PERFORMANCE ===
      'no-loop-func': 'error',
      'no-caller': 'error',
      'no-extend-native': 'error',
      'no-extra-bind': 'error',
      'no-implicit-coercion': 'error',
      'no-implicit-globals': 'error',
      'no-new': 'error',
      'no-new-func': 'error',
      'no-new-wrappers': 'error',
      'no-octal-escape': 'error',
      'no-proto': 'error',
      'no-return-assign': 'error',
      'no-sequences': 'error',
      'no-throw-literal': 'error',
      'prefer-arrow-callback': 'error',
      'prefer-numeric-literals': 'error',
      'prefer-rest-params': 'error',
      'radix': 'error',
      'yoda': 'error',
      'unicorn/filename-case': 'off', // Desactivado por decisión del usuario para mantener camelCase.
      'unicorn/prevent-abbreviations': ['warn', { 
        replacements: { 
          props: false, // Permite 'props' en componentes de React
          ref: false, // Permite 'ref' en React
          params: false, // Permite 'params'
          res: false, // Permite 'res' en contextos de servidor
          req: false, // Permite 'req' en contextos de servidor
        }
      }],
      
      // === React Refresh ===
      'react-refresh/only-export-components': [
        'error',
        { allowConstantExport: true },
      ],
    },
  },

  // === CONFIGURACIÓN EXCLUSIVA PARA ARCHIVOS JSX ===
  // Desactiva la regla de nombre de archivo para componentes de React, que usan PascalCase.
  {
    files: ['**/*.jsx'],
    rules: {
      'unicorn/filename-case': 'off',
    },
  },

  // === ANULACIÓN ESPECÍFICA PARA RICH TEXT EDITOR ===
  {
    files: ['src/components/common/RichTextEditor.jsx'],
    rules: {
      // JUSTIFICACIÓN: El uso de dangerouslySetInnerHTML es esencial para la funcionalidad
      // de un editor de texto enriquecido. El riesgo de XSS se mitiga profesionalmente
      // sanitizando el contenido con DOMPurify antes de renderizarlo.
      // Esta anulación es una excepción documentada y controlada.
      'react/no-danger': 'off',
    },
  },
  
  // === CONFIGURACIÓN PARA ARCHIVOS TS/TSX ===
  {
    files: ['**/*.{ts,tsx}'],
        languageOptions: {
      parser: tsParser,
      globals: sanitizedGlobals,
      parserOptions: {
        project: './tsconfig.json',
        tsconfigRootDir: import.meta.dirname,
        ecmaVersion: 'latest',
        sourceType: 'module',
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      sonarjs,
      react,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      'jsx-a11y': jsxA11y,
      import: importPlugin,
      promise: promisePlugin,
      security: securityPlugin,
      unicorn,
      prettier: prettierPlugin,
    },
    settings: sharedSettings,
    rules: {
      // === PRETTIER ===
      'prettier/prettier': 'error',
      
      // === REGLAS TYPESCRIPT ===
      ...tsPlugin.configs.recommended.rules,
      ...tsPlugin.configs['recommended-requiring-type-checking'].rules,
      // Las reglas de Prettier se aplican al final del archivo para anular conflictos.
      
      // Desactivar reglas JS que son manejadas por TS
      'no-unused-vars': 'off',
      'no-undef': 'off',
      'no-redeclare': 'off',
      'no-use-before-define': 'off',
      'no-shadow': 'off',
      'no-empty-function': 'off',
      'no-array-constructor': 'off',
      'no-loss-of-precision': 'off',
      'default-param-last': 'off',
      'prefer-promise-reject-errors': 'off',
      
      // Activar versiones TypeScript
      '@typescript-eslint/no-unused-vars': 'error',
      '@typescript-eslint/no-redeclare': 'error',
      '@typescript-eslint/no-use-before-define': ['error', { functions: false, classes: true, variables: true }],
      '@typescript-eslint/no-shadow': 'warn',
      '@typescript-eslint/no-empty-function': 'error',
      '@typescript-eslint/no-array-constructor': 'error',
      '@typescript-eslint/no-loss-of-precision': 'error',
      '@typescript-eslint/default-param-last': 'error',
      '@typescript-eslint/prefer-promise-reject-errors': 'error',
      
      // Reglas específicas de TypeScript
      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/explicit-module-boundary-types': 'off',
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-non-null-assertion': 'warn',
      '@typescript-eslint/prefer-as-const': 'error',
      '@typescript-eslint/prefer-nullish-coalescing': 'error',
      '@typescript-eslint/prefer-optional-chain': 'error',
      '@typescript-eslint/strict-boolean-expressions': 'off',
      '@typescript-eslint/prefer-readonly': 'error',
      '@typescript-eslint/consistent-type-imports': ['error', { prefer: 'type-imports' }],
      '@typescript-eslint/consistent-type-definitions': ['error', 'interface'],
      '@typescript-eslint/no-unused-expressions': ['error', { allowShortCircuit: true, allowTernary: true }],
      '@typescript-eslint/member-ordering': 'error',
      '@typescript-eslint/method-signature-style': ['error', 'property'],
      '@typescript-eslint/no-confusing-non-null-assertion': 'error',
      '@typescript-eslint/no-duplicate-enum-values': 'error',
      '@typescript-eslint/no-dynamic-delete': 'error',
      '@typescript-eslint/no-extraneous-class': 'error',
      '@typescript-eslint/no-invalid-void-type': 'error',
      '@typescript-eslint/no-meaningless-void-operator': 'error',
      '@typescript-eslint/no-non-null-asserted-nullish-coalescing': 'error',
      '@typescript-eslint/no-require-imports': 'error',
      '@typescript-eslint/no-useless-empty-export': 'error',
      '@typescript-eslint/prefer-enum-initializers': 'error',
      '@typescript-eslint/prefer-function-type': 'error',
      '@typescript-eslint/prefer-literal-enum-member': 'error',
      '@typescript-eslint/prefer-ts-expect-error': 'error',
      '@typescript-eslint/promise-function-async': 'error',
      '@typescript-eslint/require-array-sort-compare': 'error',
      '@typescript-eslint/switch-exhaustiveness-check': 'error',
      '@typescript-eslint/unified-signatures': 'error',
      
      // === REGLAS REACT ===
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off', // TypeScript maneja esto
      'react/jsx-uses-react': 'off',
      'react/jsx-uses-vars': 'error',
      'react/no-unescaped-entities': 'warn',
      'react/no-unknown-property': 'error',
      'react/self-closing-comp': 'error',
      'react/jsx-boolean-value': ['error', 'never'],
      'react/jsx-curly-brace-presence': ['error', { props: 'never', children: 'never' }],
      'react/jsx-fragments': ['error', 'syntax'],
      'react/jsx-no-useless-fragment': 'error',
      'react/no-array-index-key': 'warn',
      'react/no-children-prop': 'error',
      'react/no-danger': 'error',
      'react/no-deprecated': 'error',
      'react/no-direct-mutation-state': 'error',
      'react/no-find-dom-node': 'error',
      'react/no-is-mounted': 'error',
      'react/no-redundant-should-component-update': 'error',
      'react/no-render-return-value': 'error',
      'react/no-string-refs': 'error',
      'react/no-this-in-sfc': 'error',
      'react/no-typos': 'error',
      'react/no-unsafe': 'error',
      'react/no-unused-prop-types': 'off', // TypeScript maneja esto
      'react/no-unused-state': 'error',
      'react/prefer-es6-class': 'error',
      'react/prefer-stateless-function': 'error',
      'react/require-render-return': 'error',
      'react/sort-comp': 'error',
      'react/void-dom-elements-no-children': 'error',
      
      // === ACCESIBILIDAD (jsx-a11y) ===
      ...jsxA11y.configs.recommended.rules,
      
      // === IMPORTS/EXPORTS ===
      ...importPlugin.configs.recommended.rules,
      ...importPlugin.configs.typescript.rules,
      'react-hooks/exhaustive-deps': 'error',
      'import/order': ['error', {
        groups: [
          'builtin',
          'external',
          'internal',
          'parent',
          'sibling',
          'index',
        ],
        'newlines-between': 'always',
        alphabetize: { order: 'asc', caseInsensitive: true },
      }],
      'import/no-unresolved': 'error',
      'import/no-duplicates': 'error',
      'import/no-unused-modules': 'warn',
      'import/no-cycle': 'error',
      'import/no-self-import': 'error',
      'import/no-useless-path-segments': 'warn',
      'import/newline-after-import': 'warn',
      'import/no-anonymous-default-export': 'warn',
      'import/prefer-default-export': 'off',
      'import/named': 'off', // TypeScript maneja esto
      'import/default': 'off', // TypeScript maneja esto
      'import/namespace': 'off', // TypeScript maneja esto
      
      // === PROMESAS ===
      ...promisePlugin.configs.recommended.rules,
      
      // === SEGURIDAD ===
      ...securityPlugin.configs.recommended.rules,
      
      // === CALIDAD DE CÓDIGO ===
      'consistent-return': 'off', // TypeScript maneja esto
      'default-case': 'error',
      'default-case-last': 'error',
      'no-multiple-empty-lines': 'off', // Prettier maneja esto
      'no-trailing-spaces': 'off', // Prettier maneja esto
      'comma-dangle': 'off', // Prettier maneja esto
      'quotes': 'off', // Prettier maneja esto
      'semi': 'off', // Prettier maneja esto
      'indent': 'off', // Prettier maneja esto
      'linebreak-style': 'off', // Prettier maneja esto
      'max-len': 'off', // Prettier maneja esto
      'brace-style': 'off', // Prettier maneja esto
      'comma-spacing': 'off', // Prettier maneja esto
      'key-spacing': 'off', // Prettier maneja esto
      'space-before-blocks': 'off', // Prettier maneja esto
      'space-before-function-paren': 'off', // Prettier maneja esto
      'space-in-parens': 'off', // Prettier maneja esto
      'space-infix-ops': 'off', // Prettier maneja esto
      'space-unary-ops': 'off', // Prettier maneja esto
      'arrow-spacing': 'off', // Prettier maneja esto
      'block-spacing': 'off', // Prettier maneja esto
      'computed-property-spacing': 'off', // Prettier maneja esto
      'func-call-spacing': 'off', // Prettier maneja esto
      'keyword-spacing': 'off', // Prettier maneja esto
      'no-multi-spaces': 'off', // Prettier maneja esto
      'no-whitespace-before-property': 'off', // Prettier maneja esto
      'object-curly-spacing': 'off', // Prettier maneja esto
      'rest-spread-spacing': 'off', // Prettier maneja esto
      'semi-spacing': 'off', // Prettier maneja esto
      'template-curly-spacing': 'off', // Prettier maneja esto
      
      // === React Refresh ===
      'react-refresh/only-export-components': [
        'error',
        { allowConstantExport: true },
      ],
    },
  },
  
  // === CONFIGURACIÓN PARA ARCHIVOS DE CONFIGURACIÓN ===
  {
    files: ['**/*.config.{js,mjs,ts}/**/*'],
    languageOptions: {
      globals: globals.node,
    },
    rules: {
      'no-console': 'off',
      'import/no-anonymous-default-export': 'off',
      '@typescript-eslint/no-var-requires': 'off',
      'prettier/prettier': 'error',
    },
  },
  
  // === CONFIGURACIÓN PARA TESTS ===
  {
    files: ['**/*.{test,spec}.{js,jsx,ts,tsx}', '**/__tests__/**/*.{js,jsx,ts,tsx}'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.jest,
        ...globals.vitest,
      },
    },
    rules: {
      'no-console': 'off',
      'react/display-name': 'off',
      'import/no-anonymous-default-export': 'off',
      'jsx-a11y/no-autofocus': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-non-null-assertion': 'off',
      'prettier/prettier': 'error',
    },
  },
  
  // === CONFIGURACIÓN PARA HOOKS PERSONALIZADOS ===
  {
    files: ['**/hooks/**/*.{js,jsx,ts,tsx}', '**/use*.{js,jsx,ts,tsx}'],
    plugins: {
      prettier: prettierPlugin,
    },
    rules: {
      'prettier/prettier': 'error',
    },
  },

  // === CONFIGURACIÓN EXCEPCIONAL PARA LOGGER ===
  // Se deshabilita la regla 'no-console' exclusivamente para nuestro logger centralizado.
  // Esta regla se coloca al final para asegurar que anule cualquier regla global.
  {
    files: ['src/utils/logger.js'],
    plugins: {
      prettier: prettierPlugin,
    },
    rules: {
      'no-console': 'off',
      'prettier/prettier': 'error',
    },
  },

  // === PRETTIER CONFIGURATION ===
  // Esta debe ser la ÚLTIMA configuración en el array para que pueda
  // desactivar reglas de otros plugins que entren en conflicto con el formato.
  prettierConfig,
];