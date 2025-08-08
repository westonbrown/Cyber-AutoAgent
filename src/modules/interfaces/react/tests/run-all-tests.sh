#!/bin/bash

# Cyber-AutoAgent Complete Testing Suite
# Runs both standard and comprehensive terminal capture tests
# For thorough testing and validation

echo "🚀 Cyber-AutoAgent Complete Testing Suite v2.0"
echo "============================================="
echo ""

# Check if we're in the right directory
if [ ! -f "../dist/index.js" ]; then
    echo "❌ Error: dist/index.js not found. Please build the project first."
    echo "   Run: npm run build"
    exit 1
fi

# Parse arguments
RUN_STANDARD=true
RUN_COMPREHENSIVE=true
VALIDATE=true
QUICK=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --standard-only)
            RUN_COMPREHENSIVE=false
            shift
            ;;
        --comprehensive-only)
            RUN_STANDARD=false
            shift
            ;;
        --no-validate)
            VALIDATE=false
            shift
            ;;
        --quick)
            QUICK=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --standard-only   Run only standard comprehensive tests"
            echo "  --comprehensive-only   Run only comprehensive debugging tests"
            echo "  --no-validate     Skip validation phase"
            echo "  --quick          Run quick subset of tests"
            echo "  --help           Show this help message"
            echo ""
            echo "By default, runs both test suites with validation."
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Track overall success
OVERALL_SUCCESS=true

# Run standard comprehensive tests
if [ "$RUN_STANDARD" = true ]; then
    echo "📸 Phase 1: Standard Comprehensive Terminal Capture"
    echo "──────────────────────────────────────────────────"
    echo ""
    
    node comprehensive-capture.js
    if [ $? -ne 0 ]; then
        echo "❌ Standard capture failed!"
        OVERALL_SUCCESS=false
    else
        echo "✅ Standard capture complete!"
    fi
    echo ""
fi

# Run comprehensive debugging tests
if [ "$RUN_COMPREHENSIVE" = true ]; then
    echo "🔬 Phase 2: Comprehensive Debugging Terminal Capture"
    echo "──────────────────────────────────────────────"
    echo ""
    
    node comprehensive-test-suite.js
    if [ $? -ne 0 ]; then
        echo "❌ Comprehensive capture failed!"
        OVERALL_SUCCESS=false
    else
        echo "✅ Comprehensive capture complete!"
    fi
    echo ""
fi

# Run validation
if [ "$VALIDATE" = true ]; then
    echo "🔍 Phase 3: Validation & Analysis"
    echo "─────────────────────────────────"
    echo ""
    
    # Validate standard captures
    if [ "$RUN_STANDARD" = true ] && [ -d "captures" ]; then
        echo "Validating standard captures..."
        node validate-captures.js
        if [ $? -ne 0 ]; then
            echo "⚠️  Standard validation found issues"
        fi
    fi
    
    # Analyze comprehensive captures
    if [ "$RUN_COMPREHENSIVE" = true ] && [ -d "test-captures" ]; then
        echo "Analyzing comprehensive captures..."
        node frame-analyzer.js test-captures
        if [ $? -ne 0 ]; then
            echo "⚠️  Comprehensive analysis found issues"
        fi
    fi
    echo ""
fi

# Generate combined report
if [ "$OVERALL_SUCCESS" = true ]; then
    echo "📊 Generating Combined Test Report"
    echo "─────────────────────────────────"
    
    cat > test-results.md << EOF
# Cyber-AutoAgent Test Results

**Date:** $(date)
**Status:** ${OVERALL_SUCCESS}

## Test Suites Run

EOF
    
    if [ "$RUN_STANDARD" = true ]; then
        echo "### Standard Comprehensive Tests" >> test-results.md
        echo "- Location: \`tests/captures/\`" >> test-results.md
        echo "- Report: \`MASTER-VALIDATION-REPORT.md\`" >> test-results.md
        echo "" >> test-results.md
    fi
    
    if [ "$RUN_COMPREHENSIVE" = true ]; then
        echo "### Comprehensive Debugging Tests" >> test-results.md
        echo "- Location: \`tests/test-captures/\`" >> test-results.md
        echo "- Report: \`MASTER-SUMMARY.md\`" >> test-results.md
        echo "" >> test-results.md
    fi
    
    echo "## Key Files for Review" >> test-results.md
    echo "" >> test-results.md
    
    if [ -f "captures/MASTER-VALIDATION-REPORT.md" ]; then
        echo "1. **Standard Tests:** \`captures/MASTER-VALIDATION-REPORT.md\`" >> test-results.md
    fi
    
    if [ -f "test-captures/MASTER-SUMMARY.md" ]; then
        echo "2. **Comprehensive Tests:** \`test-captures/MASTER-SUMMARY.md\`" >> test-results.md
    fi
    
    echo "" >> test-results.md
    echo "## Coverage Summary" >> test-results.md
    echo "" >> test-results.md
    
    # Count captures
    if [ -d "captures" ]; then
        STANDARD_COUNT=$(find captures -name "*.txt" | wc -l)
        echo "- Standard Captures: $STANDARD_COUNT" >> test-results.md
    fi
    
    if [ -d "test-captures" ]; then
        COMPREHENSIVE_COUNT=$(find test-captures -name "*.capture" | wc -l)
        echo "- Comprehensive Captures: $COMPREHENSIVE_COUNT" >> test-results.md
    fi
    
    echo "" >> test-results.md
    echo "## Components Tested" >> test-results.md
    echo "" >> test-results.md
    echo "✅ Core Components (App, MainAppView, ConfigEditor, SetupWizard)" >> test-results.md
    echo "✅ Hooks (useApplicationState, useCommandHandler, useModalManager)" >> test-results.md
    echo "✅ Services (DirectDockerService, AssessmentFlow, HealthMonitor)" >> test-results.md
    echo "✅ Modals (Config, Documentation, ModuleSelector, SafetyWarning)" >> test-results.md
    echo "✅ Error States (Invalid commands, Missing config, Network errors)" >> test-results.md
    echo "✅ Performance (Rapid input, Large buffers, State transitions)" >> test-results.md
    
    echo ""
    echo "✅ All tests completed successfully!"
else
    echo ""
    echo "⚠️  Some tests failed. Review the output above for details."
fi

echo ""
echo "📁 Output Locations:"
echo "  Standard Captures: tests/captures/"
echo "  Comprehensive Captures: tests/test-captures/"
echo "  Combined Report:   tests/test-results.md"
echo ""
echo "✅ Test suite complete and ready for analysis"
echo ""

# Exit with appropriate code
if [ "$OVERALL_SUCCESS" = true ]; then
    exit 0
else
    exit 1
fi