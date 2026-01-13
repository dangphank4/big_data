#!/bin/bash
# ==============================================================================
# CLEANUP - Delete all resources
# ==============================================================================

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

NAMESPACE="bigdata"

log_warning "This will DELETE all resources in namespace: $NAMESPACE"
log_warning "This action CANNOT be undone!"
echo ""

read -p "Are you sure? Type 'yes' to confirm: " -r
echo

if [[ ! $REPLY == "yes" ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

log_warning "Starting cleanup..."

# Delete all resources
kubectl delete all --all -n ${NAMESPACE} || true
kubectl delete pvc --all -n ${NAMESPACE} || true
kubectl delete configmap --all -n ${NAMESPACE} || true
kubectl delete secret --all -n ${NAMESPACE} || true
kubectl delete hpa --all -n ${NAMESPACE} || true
kubectl delete networkpolicy --all -n ${NAMESPACE} || true

# Delete namespace
kubectl delete namespace ${NAMESPACE} || true

log_error "All resources deleted!"
