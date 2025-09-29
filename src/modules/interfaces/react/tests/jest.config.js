/** @type {import('jest').Config} */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/unit/setup.ts'],
  testMatch: [
    '<rootDir>/unit/**/*.test.ts',
    '<rootDir>/unit/**/*.test.tsx'
  ],
  collectCoverageFrom: [
    '../src/**/*.{ts,tsx}',
    '!../src/**/*.d.ts',
    '!../src/index.tsx',
    '!../src/**/__mocks__/**',
    '!../src/**/test-utils.tsx'
  ],
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 70,
      lines: 80,
      statements: 80
    }
  },
  coverageReporters: ['text', 'lcov', 'html'],
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
    '^ink-testing-library$': '<rootDir>/unit/mocks/ink-testing-library.js',
    '^ink$': '<rootDir>/unit/mocks/ink.js',
    '^ink-gradient$': '<rootDir>/unit/mocks/ink-components.js',
    '^ink-big-text$': '<rootDir>/unit/mocks/ink-components.js',
    '^ink-box$': '<rootDir>/unit/mocks/ink-components.js',
    '^ink-divider$': '<rootDir>/unit/mocks/ink-components.js',
    '^ink-link$': '<rootDir>/unit/mocks/ink-components.js',
    '^ink-progress-bar$': '<rootDir>/unit/mocks/ink-components.js',
    '^ink-select-input$': '<rootDir>/unit/mocks/ink-components.js',
    '^ink-spinner$': '<rootDir>/unit/mocks/ink-components.js',
    '^ink-table$': '<rootDir>/unit/mocks/ink-components.js',
    '^ink-text-input$': '<rootDir>/unit/mocks/ink-components.js'
  },
  transform: {
    '^.+\\.(ts|tsx)$': ['ts-jest', {
      tsconfig: 'tsconfig.jest.json'
    }],
    '^.+\\.(js|jsx|mjs)$': 'babel-jest'
  },
  transformIgnorePatterns: [
    'node_modules/(?!(strip-ansi|ansi-regex)/)'
  ],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx'],
  testTimeout: 10000,
  verbose: true
};