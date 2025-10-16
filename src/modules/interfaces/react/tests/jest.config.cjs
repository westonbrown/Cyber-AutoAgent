/** @type {import('ts-jest').JestConfigWithTsJest} */
module.exports = {
  preset: 'ts-jest/presets/default-esm',
  testEnvironment: 'jsdom',
  extensionsToTreatAsEsm: ['.ts', '.tsx'],
  transform: {
    '^.+\\\.tsx?$': [
      'ts-jest',
      {
        useESM: true,
        tsconfig: '<rootDir>/tsconfig.test.json',
      },
    ],
  },
  rootDir: '..', // The root of the project is one level up from the /tests directory
  testMatch: [
    '<rootDir>/tests/**/*.test.ts',
    '<rootDir>/tests/**/*.test.tsx',
  ],
  setupFilesAfterEnv: ['<rootDir>/tests/unit/setup.ts'],
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/index.tsx',
    '!src/**/__mocks__/**',
    '!src/**/test-utils.tsx'
  ],
  coverageThreshold: {
  global: {
      branches: 0,
      functions: 0,
      lines: 0,
      statements: 0
    }
  },
  coverageReporters: ['text', 'lcov', 'html'],
  moduleNameMapper: {
'^(\\\.{1,2}/.*)\\.js$': '$1',
    // Force ESM mock for ink
    '^ink$': '<rootDir>/tests/unit/mocks/ink.js',
    '^ink$': '<rootDir>/tests/unit/mocks/ink.js',
    '^ink-gradient$': '<rootDir>/tests/unit/mocks/ink-components.js',
    '^ink-big-text$': '<rootDir>/tests/unit/mocks/ink-components.js',
    '^ink-box$': '<rootDir>/tests/unit/mocks/ink-components.js',
    '^ink-divider$': '<rootDir>/tests/unit/mocks/ink-components.js',
    '^ink-link$': '<rootDir>/tests/unit/mocks/ink-components.js',
    '^ink-progress-bar$': '<rootDir>/tests/unit/mocks/ink-components.js',
    '^ink-select-input$': '<rootDir>/tests/unit/mocks/ink-components.js',
    '^ink-spinner$': '<rootDir>/tests/unit/mocks/ink-components.js',
    '^ink-table$': '<rootDir>/tests/unit/mocks/ink-components.js',
    '^ink-text-input$': '<rootDir>/tests/unit/mocks/ink-components.js',
    '^js-yaml$': '<rootDir>/tests/unit/mocks/js-yaml.js',
    '^node-pty$': '<rootDir>/tests/unit/mocks/node-pty.js',
    'strip-ansi': '<rootDir>/tests/unit/mocks/strip-ansi.js',
    'yaml': '<rootDir>/tests/unit/mocks/yaml.js'
  },
  transformIgnorePatterns: [
    'node_modules/(?!(strip-ansi|ansi-regex)/)'
  ],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx'],
  testTimeout: 10000,
  verbose: true
};
