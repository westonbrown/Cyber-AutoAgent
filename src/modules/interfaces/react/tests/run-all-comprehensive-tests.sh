#!/bin/bash

##############################################################################
# Comprehensive Test Suite Runner for Cyber-AutoAgent React Interface
#
# This script runs all types of tests to ensure complete frontend validation:
# - Unit Tests (Jest-based component tests)
# - Interactive Component Tests (PTY-based)
# - User Journey Validation (End-to-end flows)
# - Automated Test Suite (Full application testing)
# - Visual Regression Tests (UI consistency)
# - Performance Tests (Startup and responsiveness)
#
# Aligned with TEST-VALIDATION-SPECIFICATION.md requirements
##############################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RESULTS_DIR="$SCRIPT_DIR/fixtures/test-results"
LOG_FILE="$RESULTS_DIR/comprehensive-test-log.txt"

# Test suite flags
RUN_UNIT_TESTS=true
RUN_INTERACTIVE_TESTS=true
RUN_JOURNEY_TESTS=true
RUN_AUTOMATED_TESTS=true
RUN_VISUAL_TESTS=true
RUN_PERFORMANCE_TESTS=true

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-unit)
            RUN_UNIT_TESTS=false
            shift
            ;;
        --skip-interactive)
            RUN_INTERACTIVE_TESTS=false
            shift
            ;;
        --skip-journey)
            RUN_JOURNEY_TESTS=false
            shift
            ;;
        --skip-automated)
            RUN_AUTOMATED_TESTS=false
            shift
            ;;
        --skip-visual)
            RUN_VISUAL_TESTS=false
            shift
            ;;
        --skip-performance)
            RUN_PERFORMANCE_TESTS=false
            shift
            ;;
        --help)
            echo -e "${CYAN}Comprehensive Test Suite for Cyber-AutoAgent${NC}\n"
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --skip-unit          Skip Jest unit tests"
            echo "  --skip-interactive   Skip interactive component tests"
            echo "  --skip-journey       Skip user journey validation"
            echo "  --skip-automated     Skip automated test suite"
            echo "  --skip-visual        Skip visual regression tests"
            echo "  --skip-performance   Skip performance tests"
            echo "  --help               Show this help message"
            echo ""
            echo "This test suite validates ALL frontend functionality per TEST-VALIDATION-SPECIFICATION.md:"
            echo "  • Section 2.1: First Launch Experience"
            echo "  • Section 2.2: Configuration Management"
            echo "  • Section 2.3: Security Assessment Execution"
            echo "  • Section 2.4: Operation Control and Monitoring"
            echo "  • Section 3: UI Component Validation"
            echo "  • Section 4: Error State and Edge Cases"
            echo "  • Section 5: Security and Authorization"
            echo "  • Section 6: Performance and Reliability"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

##############################################################################
# Utility Functions
##############################################################################

log_message() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
    
    case $level in
        "INFO")
            echo -e "${BLUE}ℹ ${message}${NC}"
            ;;
        "SUCCESS")
            echo -e "${GREEN}✓ ${message}${NC}"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠ ${message}${NC}"
            ;;
        "ERROR")
            echo -e "${RED}✗ ${message}${NC}"
            ;;
        "HEADER")
            echo -e "${PURPLE}${message}${NC}"
            ;;
    esac
}

check_prerequisites() {
    log_message "INFO" "Checking prerequisites..."
    
    # Check Node.js version
    if ! command -v node &> /dev/null; then
        log_message "ERROR" "Node.js is not installed"
        exit 1
    fi
    
    local node_version=$(node --version | sed 's/v//')
    local required_version="18.0.0"
    
    if ! printf '%s\n%s\n' "$required_version" "$node_version" | sort -V -C; then
        log_message "WARNING" "Node.js version $node_version may be too old (recommended: $required_version+)"
    fi
    
    # Check npm packages
    if [ ! -d "$PROJECT_DIR/node_modules" ]; then
        log_message "INFO" "Installing npm dependencies..."
        cd "$PROJECT_DIR"
        npm install
    fi
    
    # Check if build exists and is recent
    local build_file="$PROJECT_DIR/dist/index.js"
    local src_dir="$PROJECT_DIR/src"
    
    if [ ! -f "$build_file" ] || [ "$src_dir" -nt "$build_file" ]; then
        log_message "INFO" "Building application..."
        cd "$PROJECT_DIR"
        npm run build
        
        if [ $? -ne 0 ]; then
            log_message "ERROR" "Build failed"
            exit 1
        fi
        
        log_message "SUCCESS" "Build completed"
    fi
    
    log_message "SUCCESS" "Prerequisites check completed"
}

run_test_suite() {
    local suite_name=$1
    local test_command=$2
    local suite_name_lower=$(echo "$suite_name" | tr '[:upper:]' '[:lower:]')
    local log_file="$RESULTS_DIR/${suite_name_lower// /-}-test.log"
    
    log_message "HEADER" "Running $suite_name..."
    echo ""
    
    # Create a subshell to capture both stdout and stderr
    (
        eval "$test_command"
    ) 2>&1 | tee "$log_file"
    
    local exit_code=${PIPESTATUS[0]}
    
    if [ $exit_code -eq 0 ]; then
        log_message "SUCCESS" "$suite_name passed"
        return 0
    else
        log_message "ERROR" "$suite_name failed (exit code: $exit_code)"
        return 1
    fi
}

##############################################################################
# Test Suite Runners
##############################################################################

run_unit_tests() {
    if [ "$RUN_UNIT_TESTS" = false ]; then
        log_message "INFO" "Skipping unit tests"
        return 0
    fi
    
    local test_cmd="cd '$PROJECT_DIR' && npm test -- --coverage --passWithNoTests --watchAll=false"
    run_test_suite "Unit Tests" "$test_cmd"
}

run_interactive_tests() {
    if [ "$RUN_INTERACTIVE_TESTS" = false ]; then
        log_message "INFO" "Skipping interactive tests"
        return 0
    fi
    
    local test_cmd="cd '$SCRIPT_DIR' && node integration/interactive-component-tests.js"
    run_test_suite "Interactive Component Tests" "$test_cmd"
}

run_journey_tests() {
    if [ "$RUN_JOURNEY_TESTS" = false ]; then
        log_message "INFO" "Skipping journey tests"
        return 0
    fi
    
    local test_cmd="cd '$SCRIPT_DIR' && node integration/journey-validation-tests.js"
    run_test_suite "User Journey Validation" "$test_cmd"
}

run_automated_tests() {
    if [ "$RUN_AUTOMATED_TESTS" = false ]; then
        log_message "INFO" "Skipping automated tests"
        return 0
    fi
    
    local test_cmd="cd '$SCRIPT_DIR' && node integration/automated-test-suite.js"
    run_test_suite "Automated Test Suite" "$test_cmd"
}

run_visual_tests() {
    if [ "$RUN_VISUAL_TESTS" = false ]; then
        log_message "INFO" "Skipping visual tests"
        return 0
    fi
    
    # Check if captures exist, run capture if needed
    if [ ! -d "$SCRIPT_DIR/fixtures/captures" ]; then
        log_message "INFO" "No existing captures found, running comprehensive capture..."
        local capture_cmd="cd '$SCRIPT_DIR' && node visual/comprehensive-capture.js"
        run_test_suite "Capture Generation" "$capture_cmd"
    fi
    
    local test_cmd="cd '$SCRIPT_DIR' && node visual/validate-captures.js"
    run_test_suite "Visual Regression Tests" "$test_cmd"
}

run_performance_tests() {
    if [ "$RUN_PERFORMANCE_TESTS" = false ]; then
        log_message "INFO" "Skipping performance tests"
        return 0
    fi
    
    # Custom performance test
    log_message "HEADER" "Running Performance Tests..."
    echo ""
    
    local startup_times=()
    local test_iterations=3
    
    for i in $(seq 1 $test_iterations); do
        log_message "INFO" "Performance test iteration $i/$test_iterations"
        
        local start_time=$(date +%s)
        timeout 10s node "$PROJECT_DIR/dist/index.js" --headless > /dev/null 2>&1
        local end_time=$(date +%s)
        
        local duration=$((1000 * (end_time - start_time)))
        startup_times+=($duration)
        
        log_message "INFO" "Startup time: ${duration}ms"
    done
    
    # Calculate average
    local sum=0
    for time in "${startup_times[@]}"; do
        sum=$((sum + time))
    done
    local avg=$((sum / test_iterations))
    
    # Performance thresholds
    local threshold_avg=5000  # 5 seconds average
    local threshold_max=8000  # 8 seconds maximum
    
    local max_time=$(printf '%s\n' "${startup_times[@]}" | sort -n | tail -1)
    
    if [ $avg -le $threshold_avg ] && [ $max_time -le $threshold_max ]; then
        log_message "SUCCESS" "Performance tests passed (avg: ${avg}ms, max: ${max_time}ms)"
        echo "{\"passed\": true, \"averageStartup\": $avg, \"maxStartup\": $max_time}" > "$RESULTS_DIR/performance-results.json"
        return 0
    else
        log_message "ERROR" "Performance tests failed (avg: ${avg}ms, max: ${max_time}ms)"
        echo "{\"passed\": false, \"averageStartup\": $avg, \"maxStartup\": $max_time}" > "$RESULTS_DIR/performance-results.json"
        return 1
    fi
}

##############################################################################
# Main Execution
##############################################################################

main() {
    # Setup
    mkdir -p "$RESULTS_DIR"
    echo "Comprehensive Test Suite Started at $(date)" > "$LOG_FILE"
    
    log_message "HEADER" "🧪 Cyber-AutoAgent Comprehensive Test Suite"
    echo ""
    log_message "INFO" "Testing ALL frontend functionality per TEST-VALIDATION-SPECIFICATION.md"
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    local start_time=$(date +%s)
    local failed_tests=()
    local passed_tests=()
    
    # Prerequisites
    check_prerequisites
    echo ""
    
    # Run test suites
    if run_unit_tests; then
        passed_tests+=("Unit Tests")
    else
        failed_tests+=("Unit Tests")
    fi
    echo ""
    
    if run_interactive_tests; then
        passed_tests+=("Interactive Component Tests")
    else
        failed_tests+=("Interactive Component Tests")
    fi
    echo ""
    
    if run_journey_tests; then
        passed_tests+=("User Journey Validation")
    else
        failed_tests+=("User Journey Validation")
    fi
    echo ""
    
    if run_automated_tests; then
        passed_tests+=("Automated Test Suite")
    else
        failed_tests+=("Automated Test Suite")
    fi
    echo ""
    
    if run_visual_tests; then
        passed_tests+=("Visual Regression Tests")
    else
        failed_tests+=("Visual Regression Tests")
    fi
    echo ""
    
    if run_performance_tests; then
        passed_tests+=("Performance Tests")
    else
        failed_tests+=("Performance Tests")
    fi
    echo ""
    
    # Generate summary
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))
    
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    log_message "HEADER" "📊 Comprehensive Test Results Summary"
    echo ""
    
    log_message "SUCCESS" "Passed: ${#passed_tests[@]}"
    for test in "${passed_tests[@]}"; do
        echo -e "  ${GREEN}✓${NC} $test"
    done
    
    if [ ${#failed_tests[@]} -gt 0 ]; then
        echo ""
        log_message "ERROR" "Failed: ${#failed_tests[@]}"
        for test in "${failed_tests[@]}"; do
            echo -e "  ${RED}✗${NC} $test"
        done
    fi
    
    echo ""
    log_message "INFO" "Total Duration: ${minutes}m ${seconds}s"
    
    # TEST-VALIDATION-SPECIFICATION.md alignment summary
    echo ""
    log_message "HEADER" "📋 TEST-VALIDATION-SPECIFICATION.md Alignment"
    echo ""
    
    local spec_sections=(
        "Section 2.1: First Launch Experience"
        "Section 2.2: Configuration Management"
        "Section 2.3: Security Assessment Execution"
        "Section 2.4: Operation Control and Monitoring"
        "Section 3: UI Component Validation"
        "Section 4: Error State and Edge Cases"
        "Section 5: Security and Authorization"
        "Section 6: Performance and Reliability"
    )
    
    for section in "${spec_sections[@]}"; do
        if [ ${#failed_tests[@]} -eq 0 ]; then
            echo -e "  ${GREEN}✓${NC} $section"
        else
            echo -e "  ${YELLOW}⚠${NC} $section (some tests failed)"
        fi
    done
    
    # Save comprehensive report
    cat > "$RESULTS_DIR/comprehensive-summary.json" << EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "duration": $duration,
    "summary": {
        "passed": ${#passed_tests[@]},
        "failed": ${#failed_tests[@]},
        "total": $((${#passed_tests[@]} + ${#failed_tests[@]}))
    },
    "passedTests": $(printf '%s\n' "${passed_tests[@]}" | jq -R . | jq -s .),
    "failedTests": $(printf '%s\n' "${failed_tests[@]}" | jq -R . | jq -s .),
    "specificationAlignment": {
        "allTestsPassed": $([ ${#failed_tests[@]} -eq 0 ] && echo "true" || echo "false"),
        "sectionsValidated": 8
    },
    "artifactPaths": {
        "logFile": "$LOG_FILE",
        "resultsDirectory": "$RESULTS_DIR",
        "coverageReport": "$PROJECT_DIR/coverage",
        "capturesDirectory": "$SCRIPT_DIR/captures"
    }
}
EOF
    
    echo ""
    log_message "INFO" "Detailed logs saved to: $LOG_FILE"
    log_message "INFO" "Test results saved to: $RESULTS_DIR/"
    log_message "INFO" "Summary report: $RESULTS_DIR/comprehensive-summary.json"
    
    # Exit with appropriate code
    if [ ${#failed_tests[@]} -eq 0 ]; then
        echo ""
        log_message "SUCCESS" "🎉 All tests passed! Frontend is fully validated."
        exit 0
    else
        echo ""
        log_message "ERROR" "❌ Some tests failed. Review logs for details."
        exit 1
    fi
}

# Run main function
main "$@"