/** @type {import('jest').Config} */
export default {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/react/setup.ts'],
  testMatch: [
    '<rootDir>/react/**/*.test.ts',
    '<rootDir>/react/**/*.test.tsx'
  ],
  collectCoverageFrom: [
    '../src/modules/interfaces/react/src/**/*.{ts,tsx}',
    '!../src/modules/interfaces/react/src/**/*.d.ts'
  ],
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
    '^ink-testing-library$': '<rootDir>/react/__mocks__/ink-testing-library.js',
    '^ink$': '<rootDir>/react/__mocks__/ink.js',
    '^ink-gradient$': '<rootDir>/react/__mocks__/ink-components.js',
    '^ink-big-text$': '<rootDir>/react/__mocks__/ink-components.js',
    '^ink-box$': '<rootDir>/react/__mocks__/ink-components.js',
    '^ink-divider$': '<rootDir>/react/__mocks__/ink-components.js',
    '^ink-link$': '<rootDir>/react/__mocks__/ink-components.js',
    '^ink-progress-bar$': '<rootDir>/react/__mocks__/ink-components.js',
    '^ink-select-input$': '<rootDir>/react/__mocks__/ink-components.js',
    '^ink-spinner$': '<rootDir>/react/__mocks__/ink-components.js',
    '^ink-table$': '<rootDir>/react/__mocks__/ink-components.js',
    '^ink-text-input$': '<rootDir>/react/__mocks__/ink-components.js'
  },
  transform: {
    '^.+\\.(ts|tsx)$': ['ts-jest', {
      tsconfig: {
        module: 'CommonJS',
        target: 'ES2022'
      }
    }],
    '^.+\\.(js|jsx|mjs)$': 'babel-jest'
  },
  transformIgnorePatterns: [
    'node_modules/'
  ],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx'],
  verbose: true
};