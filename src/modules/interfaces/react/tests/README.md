# Cyber-AutoAgent React Interface Test Suite

Comprehensive testing infrastructure for the Cyber-AutoAgent React terminal interface, aligned with `TEST-VALIDATION-SPECIFICATION.md`.

## Quick Start

```bash
# Install dependencies (first time)
npm install

# Run all tests
./run-all-comprehensive-tests.sh

# Run specific test types
node run-enhanced-tests.js --skip-visual --skip-performance

# Run only Jest unit tests
cd .. && npm test

# Run terminal stream rendering tests (uses tsx)
node integration/terminal-stream-tests.js --verbose

# Headless UI smoke test
node integration/headless-auto-run.js

# End-to-end operation stream simulation (mock execution)
node integration/operation-stream-simulation.js
```

## Test Suite Overview

### Core Test Types

| Test Type | Status | Coverage | Purpose |
|-----------|---------|----------|---------|
| **Unit Tests** | Working | Component logic | Jest-based component validation |
| **Interactive Tests** | Infrastructure Ready | User interactions | PTY-based terminal testing |
| **Journey Tests** | Infrastructure Ready | End-to-end flows | Complete user workflow validation |  
| **Visual Regression** | Infrastructure Ready | UI consistency | Screen capture comparison |
| **Performance Tests** | Working | Startup & responsiveness | Performance benchmarks |

### Working Test Files

#### Jest Unit Tests (`react/`)
- **`simple.test.ts`** - Basic Jest setup validation
- **`components/ConfigEditor-simple.test.tsx`** - Configuration editor logic (15 tests)
- **`components/ModuleSelector-simple.test.tsx`** - Module selection logic (15 tests)  
- **`components/SafetyWarning-simple.test.tsx`** - Safety authorization logic (10 tests)
- **`test-utils.js`** - Shared testing utilities and mocks

#### Interactive Test Infrastructure
- **`interactive-component-tests.js`** - Component interaction testing
- **`automated-test-suite.js`** - Full application testing
- **`journey-validation-tests.js`** - User journey validation
- **`terminal-stream-tests.js`** - Terminal stream rendering tests (uses a JSX harness with `tsx` and `EventRenderer.jsx`)
- **`operation-stream-simulation.js`** - PTY-driven mock execution flow with stream assertions
- **`headless-auto-run.js`** - Headless UI smoke test (opens config, checks responsiveness)
- **`comprehensive-capture.js`** - Screen capture generation
- **`validate-captures.js`** - Visual regression validation
- **`frame-analyzer.js`** - Terminal frame analysis utilities
- **`EventRenderer.jsx`** - Lightweight JSX wrapper that renders `EventLine` directly for integration tests

### Terminal Stream Tests

- Purpose: Validate the real terminal UI rendering pipeline for streamed events (same code paths used in production: `Terminal` → `normalizeEvent` → `StreamDisplay` → `EventLine`).
- Execution:
  - `node integration/terminal-stream-tests.js --verbose`
- Under the hood:
  - Spawns a tiny JSX app via `npx tsx` that renders `EventRenderer.jsx`, which uses the real `EventLine` from `src/components/StreamDisplay.tsx`.
  - Saves a JSON report to `tests/fixtures/test-results/`.
- Environment:
  - No special env needed; runner ensures the results directory exists.

### Mock Operation Stream Tests

- Purpose: Exercise a realistic end-to-end mock run of the UI, including safety modal, guided flow, and streaming events.
- Execution:
  - `node integration/operation-stream-simulation.js`
- Environment used by the script:
  - `NODE_ENV=test`, `CYBER_TEST_MODE=true`, `CYBER_TEST_EXECUTION=mock` (ensures `TestExecutionService` is selected and UI emits test markers).
- Notes:
  - In test mode, the UI auto-confirms the safety prompt and auto-drives the guided flow to start streaming.

### Headless UI Smoke Test

- Purpose: Ensure the app mounts in headless mode and the config editor opens without fatal errors.
- Execution:
  - `node integration/headless-auto-run.js`

## Current Test Results

### Unit Tests Status
```
ConfigEditor Component: 15/15 tests passing
ModuleSelector Component: 15/15 tests passing  
SafetyWarning Component: 10/10 tests passing
Basic Infrastructure: 3/3 tests passing
Total: 43/43 unit tests passing
```

### Performance Tests Status
```
Average Startup: 240ms (< 5s threshold)
Max Startup: 276ms (< 8s threshold)  
Memory Usage: Within normal bounds
UI Responsiveness: Good
```

## Test Configuration

### Jest Configuration (`jest.config.js`)
- **Preset**: `ts-jest` with JSX support
- **Environment**: `jsdom`
- **Coverage Thresholds**: 80% lines, 70% branches
- **Mock Strategy**: Comprehensive Ink component mocking

### Coverage Requirements
```javascript
coverageThreshold: {
  global: {
    branches: 70,
    functions: 70, 
    lines: 80,
    statements: 80
  }
}
```

## Directory Structure

```
tests/
├── README.md                           # This documentation
├── jest.config.js                      # Jest test configuration
├── mock-config.js                      # Shared mock configurations
├── run-all-comprehensive-tests.sh      # Main test runner script
├── run-enhanced-tests.js               # Enhanced test orchestrator
│
├── unit/                               # Jest unit tests
│   ├── components/                     # Component-specific tests
│   │   ├── ConfigEditor-simple.test.tsx
│   │   ├── ModuleSelector-simple.test.tsx
│   │   └── SafetyWarning-simple.test.tsx
│   ├── mocks/                          # Jest mocks
│   │   ├── ink.js                      # Ink framework mock
│   │   ├── ink-components.js           # Ink components mock
│   │   └── ink-testing-library.js      # Testing library mock
│   ├── simple.test.ts                  # Basic Jest validation
│   ├── setup.ts                        # Test environment setup
│   └── test-utils.js                   # Shared testing utilities
│
├── integration/                        # Integration tests
│   ├── interactive-component-tests.js  # PTY-based interaction tests
│   ├── automated-test-suite.js         # Full application testing
│   ├── journey-validation-tests.js     # End-to-end user journeys
│   ├── terminal-stream-tests.js        # Terminal stream rendering tests (uses tsx + EventRenderer)
│   ├── operation-stream-simulation.js  # PTY-driven mock execution stream
│   ├── headless-auto-run.js            # Headless UI smoke test
│   └── EventRenderer.jsx               # JSX harness for rendering EventLine
│
├── visual/                             # Visual regression tests
│   ├── comprehensive-capture.js        # Screen capture generation
│   ├── validate-captures.js            # Visual regression validation
│   └── frame-analyzer.js               # Terminal frame analysis
│
├── fixtures/                           # Test data and fixtures
│   ├── captures/                       # Screen captures for visual testing
│   ├── coverage/                       # Jest coverage reports
│   └── test-results/                   # Test execution reports (auto-created)
```

## TEST-VALIDATION-SPECIFICATION.md Alignment

| Specification Section | Test Implementation | Status |
|----------------------|---------------------|---------|
| **2.1 First Launch Experience** | `journey-validation-tests.js` | Infrastructure Ready |
| **2.2 Configuration Management** | `ConfigEditor-simple.test.tsx` | Validated |
| **2.3 Security Assessment Execution** | `automated-test-suite.js` | Infrastructure Ready |
| **2.4 Operation Control** | `interactive-component-tests.js` | Infrastructure Ready |
| **3.0 UI Component Validation** | All component tests | Validated |
| **4.0 Error State Handling** | Component error tests | Validated |
| **5.0 Security Authorization** | `SafetyWarning-simple.test.tsx` | Validated |
| **6.0 Performance Requirements** | Performance test suite | Validated |

## Running Tests

### Complete Test Suite
```bash
# Run all tests with full reporting
./run-all-comprehensive-tests.sh

# Skip specific test types
./run-all-comprehensive-tests.sh --skip-visual --skip-performance
```

### Individual Test Types
```bash
# Jest unit tests only
cd .. && npm test

# Interactive component tests
node integration/interactive-component-tests.js

# User journey validation
node integration/journey-validation-tests.js

# Terminal stream rendering tests
node integration/terminal-stream-tests.js --verbose

# Headless UI smoke test
node integration/headless-auto-run.js

# Operation stream simulation
node integration/operation-stream-simulation.js

# Performance benchmarks
node run-enhanced-tests.js --skip-unit --skip-interactive --skip-journey --skip-automated --skip-visual
```

### Development Testing
```bash
# Watch mode for unit tests
cd .. && npm run test:watch

# Quick validation
cd .. && npm run test:coverage
```

## Test Development

### Test Mode and Mock Execution

Some integration tests rely on a controlled test mode:
- `CYBER_TEST_MODE=true`: Enables PTY-visible markers and safe auto-flows in the UI.
- `CYBER_TEST_EXECUTION=mock`: Selects the `TestExecutionService` so tests do not require Python/Docker.

In test mode the UI will:
- Auto-open and auto-confirm the safety prompt.
- Auto-drive the guided flow (target → objective → execute) for mock runs.
- Emit `[TEST_EVENT]` markers (e.g., step headers, tool starts, metrics updates) to stdout for robust assertions.

These behaviors are gated to test mode and do not affect production.

### Adding New Unit Tests
1. Create test file in `unit/components/`
2. Import utilities from `../test-utils.js`
3. Follow existing component test patterns
4. Run `npm test` to validate

### Mock Configuration
- Use `mockConfiguredState` from `test-utils.js` for consistent config mocking
- Leverage Ink component mocks in `mocks/` directory
- Follow established mocking patterns for predictable behavior

### Performance Testing
- Startup time tests measure application launch performance
- UI responsiveness tests validate interaction timing
- Memory usage monitoring ensures efficient resource usage

## Coverage and Quality

### Current Coverage
- **Lines**: 80%+ (meeting threshold)
- **Branches**: 70%+ (meeting threshold)  
- **Functions**: 70%+ (meeting threshold)
- **Statements**: 80%+ (meeting threshold)

### Quality Metrics
- All critical user interactions tested
- Safety authorization patterns validated
- Configuration management fully covered
- Performance requirements met
- Error handling comprehensive

## Maintenance

### Test File Organization
- Keep working tests in designated directories
- Remove broken/obsolete test files regularly
- Maintain clear separation between test types
- Update documentation when adding new test capabilities

### Infrastructure Updates
- Monitor Jest and testing library versions
- Update mock configurations as components evolve
- Refresh visual regression captures periodically
- Review performance thresholds quarterly

## Test Metrics Dashboard

Run the comprehensive test suite to generate detailed metrics:
- Test execution times and performance data
- Visual regression comparison results
- Coverage reports with line-by-line analysis
- User journey completion statistics
- Component interaction success rates

Reports are saved in `fixtures/test-results/` with timestamps for historical tracking.