# Cyber-AutoAgent Terminal Testing System

This testing system captures actual terminal output from the CLI application for manual validation by Claude or developers.

## Overview

Unlike traditional unit tests that check for specific values, this system:
- Runs the actual CLI application through comprehensive user journeys
- Captures terminal output at each step with PTY for accurate rendering
- Saves captures as text files for manual review
- Provides automated validation for common issues
- Tests every screen and interaction possibility

## Files

- `comprehensive-capture.js` - Complete journey testing system
- `validate-captures.js` - Automated validation for common UI issues  
- `frame-analyzer.js` - Terminal frame analysis utilities
- `run-tests.sh` - Test runner with options

## Usage

### Run Complete Test Suite
```bash
./run-tests.sh
```

### Capture Only (no validation)
```bash
./run-tests.sh --capture-only
```

### Validate Existing Captures
```bash
./run-tests.sh --validate-only
```

## User Journeys Tested

1. **Setup Flow - Local CLI**
   - Welcome screen → Local CLI setup → Python environment → Main interface

2. **Setup Flow - Single Container**  
   - Welcome screen → Single container setup → Docker setup → Main interface

3. **Main Interface Navigation**
   - Help command → Config editor → Memory search → Navigation

4. **Operation Launch**
   - Set target → Set module → Run operation → Kill operation

5. **Error Handling**
   - Missing target → Invalid URL → Unknown commands

6. **Configuration Changes**
   - Open config → Navigate fields → Toggle options → Save changes

## Output Structure

```
captures/
├── MASTER-SUMMARY.md              # Overview of all journeys
├── VALIDATION-REPORT.md           # Automated validation results
├── setup-flow-local-cli/          # Journey folder
│   ├── 000-JOURNEY-SUMMARY.md     # Journey overview
│   ├── 001-initial-welcome.txt    # First capture
│   ├── 002-deployment-mode.txt    # Second capture
│   └── ...
└── setup-flow-single-container/   # Another journey
    └── ...
```

## Validation Checks

The automated validator checks for:
- Double ASCII branding
- Duplicate log entries (3+ times)
- Overlapping UI elements  
- Visible escape sequences (^[)
- Error text (undefined, null, NaN)
- Frame quality issues

## Manual Review Process

1. Run the test suite: `./run-tests.sh`
2. Review `VALIDATION-REPORT.md` for automated findings
3. Open individual capture files to visually inspect:
   - UI alignment and formatting
   - Color consistency
   - Smooth transitions
   - Professional appearance
4. Check journey summaries for context

## For Claude Validation

When reviewing captures, Claude should check:
- Visual quality and professional appearance
- Consistent spacing and alignment
- No rendering artifacts or corruption
- Smooth user experience flow
- Clear error messages
- Responsive input handling

## Adding New Journeys

Edit `terminal-capture.js` and add to the `journeys` array:

```javascript
{
  name: 'My New Journey',
  config: { isConfigured: true }, // Optional config override
  steps: [
    { wait: 1000, capture: 'Initial State' },
    { input: '/help', wait: 500, capture: 'Typing Command' },
    { input: '\r', wait: 1000, capture: 'Command Result' }
  ]
}
```

## Notes

- Captures include ANSI color codes (disabled with NO_COLOR=1)
- Each capture includes metadata (timestamp, action taken)
- The system uses the compiled dist/index.js file
- Build the project before running tests: `npm run build`