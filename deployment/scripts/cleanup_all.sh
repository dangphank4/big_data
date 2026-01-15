#!/usr/bin/env bash
# ==============================================================================
# cleanup_all.sh - Xóa sạch toàn bộ tài nguyên K8s trong namespace
# Usage:
#   NAMESPACE=bigdata ./cleanup_all.sh
# ==============================================================================

set -euo pipefail

NAMESPACE="${NAMESPACE:-bigdata}"

RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

warn(){ echo -e "${YELLOW}⚠️  $*${NC}"; }
err(){ echo -e "${RED}❌ $*${NC}"; }

warn "This will DELETE all resources in namespace: ${NAMESPACE}"
warn "This action CANNOT be undone!"
echo ""
read -p "Type 'yes' to confirm: " -r

if [[ "${REPLY}" != "yes" ]]; then
  echo "Cleanup cancelled."
  exit 0
fi

warn "Deleting namespace resources..."

kubectl delete all --all -n "${NAMESPACE}" || true
kubectl delete pvc --all -n "${NAMESPACE}" || true
kubectl delete configmap --all -n "${NAMESPACE}" || true
kubectl delete secret --all -n "${NAMESPACE}" || true
kubectl delete hpa --all -n "${NAMESPACE}" || true
kubectl delete networkpolicy --all -n "${NAMESPACE}" || true
kubectl delete ingress --all -n "${NAMESPACE}" || true
kubectl delete cronjob --all -n "${NAMESPACE}" || true

# Delete PVs bound to this namespace
pv_list=$(kubectl get pv -o jsonpath="{range .items[?(@.spec.claimRef.namespace=='${NAMESPACE}')]}{.metadata.name}{'\n'}{end}" || true)
if [[ -n "${pv_list}" ]]; then
  warn "Deleting PVs bound to ${NAMESPACE}..."
  kubectl delete pv ${pv_list} || true
fi

# Delete namespace
kubectl delete namespace "${NAMESPACE}" || true

err "Cleanup completed. All resources deleted."
