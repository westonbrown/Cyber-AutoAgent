#!/bin/bash

# Cyber-AutoAgent Terminal Testing System
# Captures actual terminal output for validation

echo "🎬 Cyber-AutoAgent Terminal Testing"
echo "==================================="
echo ""

# Check if we're in the right directory
if [ ! -f "../dist/index.js" ]; then
    echo "❌ Error: dist/index.js not found. Please build the project first."
    echo "   Run: npm run build"
    exit 1
fi

# Parse arguments
CAPTURE_ONLY=false
VALIDATE_ONLY=false
QUICK=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --capture-only)
            CAPTURE_ONLY=true
            shift
            ;;
        --validate-only)
            VALIDATE_ONLY=true
            shift
            ;;
        --quick)
            QUICK=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--capture-only|--validate-only|--quick]"
            echo "  --capture-only  Run only capture phase"
            echo "  --validate-only Run only validation on existing captures"
            echo "  --quick        Run quick subset of tests"
            exit 1
            ;;
    esac
done

# Run captures if not validate-only
if [ "$VALIDATE_ONLY" = false ]; then
    echo "📸 Running comprehensive terminal capture..."
    echo ""
    node comprehensive-capture.js
    if [ $? -ne 0 ]; then
        echo "❌ Capture failed!"
        exit 1
    fi
fi

# Run validation if not capture-only
if [ "$CAPTURE_ONLY" = false ]; then
    echo ""
    echo "🔍 Running validation..."
    echo ""
    node validate-captures.js
    if [ $? -ne 0 ]; then
        echo "❌ Validation failed!"
        exit 1
    fi
fi

echo ""
echo "✅ Testing complete!"
echo ""
echo "📁 Captures are in: tests/captures/"
echo "📊 Review the master validation report"
echo ""
echo "Key files to review:"
echo "  tests/captures/MASTER-VALIDATION-REPORT.md"
echo "  tests/captures/setup-wizard-complete-flow/000-JOURNEY-SUMMARY.md"
echo "  tests/captures/main-interface-all-commands/000-JOURNEY-SUMMARY.md"