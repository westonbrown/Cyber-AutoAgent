#!/bin/bash
# Validate the benchmark deployment

set -e

NAMESPACE="benchmark-harness"

echo "=== Validating CAA Benchmark Harness Deployment ==="

# Check if kubectl is configured
if ! kubectl cluster-info &>/dev/null; then
    echo "❌ kubectl is not configured or cluster is not accessible"
    exit 1
fi

echo "✅ kubectl is configured and cluster is accessible"

# Check namespace
if kubectl get namespace $NAMESPACE &>/dev/null; then
    echo "✅ Namespace '$NAMESPACE' exists"
else
    echo "❌ Namespace '$NAMESPACE' does not exist"
    exit 1
fi

# Count deployments
TOTAL_DEPLOYMENTS=$(kubectl get deployments -n $NAMESPACE --no-headers | wc -l)
EXPECTED_DEPLOYMENTS=130

echo "📊 Found $TOTAL_DEPLOYMENTS deployments (expected: $EXPECTED_DEPLOYMENTS)"

if [ "$TOTAL_DEPLOYMENTS" -eq "$EXPECTED_DEPLOYMENTS" ]; then
    echo "✅ All deployments are present"
else
    echo "⚠️  Deployment count mismatch"
fi

# Check pod status
echo ""
echo "📋 Pod Status Summary:"
kubectl get pods -n $NAMESPACE --no-headers | awk '{print $3}' | sort | uniq -c | sort -nr

# Count ready pods
READY_PODS=$(kubectl get pods -n $NAMESPACE --no-headers | grep -E '1/1.*Running' | wc -l)
TOTAL_PODS=$(kubectl get pods -n $NAMESPACE --no-headers | wc -l)

echo ""
echo "📊 Pod Statistics:"
echo "  Total Pods: $TOTAL_PODS"
echo "  Ready Pods: $READY_PODS"
echo "  Ready Percentage: $(( READY_PODS * 100 / TOTAL_PODS ))%"

# Check for problematic pods
FAILED_PODS=$(kubectl get pods -n $NAMESPACE --no-headers | grep -E 'Error|Failed|CrashLoopBackOff|ImagePullBackOff' | wc -l)
if [ "$FAILED_PODS" -gt 0 ]; then
    echo "⚠️  Found $FAILED_PODS problematic pods"
    echo ""
    echo "Problematic pods:"
    kubectl get pods -n $NAMESPACE --no-headers | grep -E 'Error|Failed|CrashLoopBackOff|ImagePullBackOff' | head -10
else
    echo "✅ No failed pods found"
fi

# Check services
TOTAL_SERVICES=$(kubectl get services -n $NAMESPACE --no-headers | wc -l)
echo ""
echo "📊 Found $TOTAL_SERVICES services"

# Check nodes
TOTAL_NODES=$(kubectl get nodes --no-headers | wc -l)
READY_NODES=$(kubectl get nodes --no-headers | grep ' Ready ' | wc -l)

echo ""
echo "🖥️  Node Status:"
echo "  Total Nodes: $TOTAL_NODES"
echo "  Ready Nodes: $READY_NODES"

if [ "$READY_NODES" -eq "$TOTAL_NODES" ]; then
    echo "✅ All nodes are ready"
else
    echo "⚠️  Some nodes are not ready"
fi

# Check resource usage
echo ""
echo "📈 Resource Usage:"
if kubectl top nodes &>/dev/null; then
    kubectl top nodes | head -5
else
    echo "⚠️  Metrics server not available"
fi

# Overall health score
HEALTH_SCORE=0
[ "$TOTAL_DEPLOYMENTS" -eq "$EXPECTED_DEPLOYMENTS" ] && HEALTH_SCORE=$((HEALTH_SCORE + 25))
[ "$FAILED_PODS" -eq 0 ] && HEALTH_SCORE=$((HEALTH_SCORE + 25))
[ "$READY_NODES" -eq "$TOTAL_NODES" ] && HEALTH_SCORE=$((HEALTH_SCORE + 25))
[ "$READY_PODS" -gt $((TOTAL_PODS / 2)) ] && HEALTH_SCORE=$((HEALTH_SCORE + 25))

echo ""
echo "🎯 Overall Health Score: $HEALTH_SCORE/100"

if [ "$HEALTH_SCORE" -ge 75 ]; then
    echo "✅ Deployment is healthy"
    exit 0
elif [ "$HEALTH_SCORE" -ge 50 ]; then
    echo "⚠️  Deployment has some issues"
    exit 1
else
    echo "❌ Deployment has significant issues"
    exit 2
fi