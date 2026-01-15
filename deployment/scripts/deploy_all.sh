#!/usr/bin/env bash
# ==============================================================================
# deploy_all.sh - Triển khai toàn bộ hệ thống theo đúng thứ tự + chờ healthcheck
# Usage:
#   NAMESPACE=bigdata SMALL_NODES=1 ./deploy_all.sh
# ==============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S_DIR="${ROOT_DIR}/k8s"
NAMESPACE="${NAMESPACE:-bigdata}"
TIMEOUT="${TIMEOUT:-600}"
SMALL_NODES="${SMALL_NODES:-1}"  # 1 = giảm resource cho node nhỏ (e2-medium)

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${BLUE}ℹ️  $*${NC}"; }
ok()  { echo -e "${GREEN}✅ $*${NC}"; }
warn(){ echo -e "${YELLOW}⚠️  $*${NC}"; }
err() { echo -e "${RED}❌ $*${NC}"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { err "Missing command: $1"; exit 1; }
}

wait_statefulset() {
  local name="$1"
  log "Waiting for StatefulSet/${name}..."
  kubectl rollout status statefulset/${name} -n "${NAMESPACE}" --timeout=10m
}

wait_deployment() {
  local name="$1"
  log "Waiting for Deployment/${name}..."
  kubectl rollout status deployment/${name} -n "${NAMESPACE}" --timeout=10m
}

wait_pods_label() {
  local label="$1"
  log "Waiting for pods with label app=${label}..."
  kubectl wait --for=condition=ready pod -l app="${label}" -n "${NAMESPACE}" --timeout=${TIMEOUT}s \
    2>&1 | grep -v "no matching resources" || true
}

apply_small_node_patches() {
  if [[ "${SMALL_NODES}" != "1" ]]; then
    return
  fi

  warn "Applying small-node resource patches..."

  # Zookeeper
  kubectl patch statefulset zookeeper -n "${NAMESPACE}" --type='json' -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"100m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"256Mi"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"300m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"512Mi"}
  ]' || true

  # Kafka
  kubectl patch statefulset kafka -n "${NAMESPACE}" --type='json' -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"100m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"512Mi"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"500m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"1Gi"}
  ]' || true

  # HDFS
  kubectl patch statefulset hadoop-namenode -n "${NAMESPACE}" --type='json' -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"100m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"512Mi"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"500m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"1Gi"}
  ]' || true

  kubectl patch statefulset hadoop-datanode -n "${NAMESPACE}" --type='json' -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"200m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"768Mi"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"800m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"1536Mi"}
  ]' || true

  # Elasticsearch
  kubectl patch statefulset elasticsearch -n "${NAMESPACE}" --type='json' -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/env/2/value","value":"-Xms512m -Xmx512m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"200m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"1Gi"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"500m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"1536Mi"}
  ]' || true

  # Kafka Producer
  kubectl patch deployment kafka-producer-crawl -n "${NAMESPACE}" --type='json' -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"100m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"256Mi"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"300m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"512Mi"}
  ]' || true

  # Spark Streaming
  kubectl patch deployment spark-streaming-consumer -n "${NAMESPACE}" --type='json' -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"100m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"512Mi"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"300m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"1Gi"}
  ]' || true

  # Spark Alerts
  kubectl patch deployment spark-streaming-alerts -n "${NAMESPACE}" --type='json' -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"100m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"512Mi"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"300m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"1Gi"}
  ]' || true

  # Kibana
  kubectl patch deployment kibana -n "${NAMESPACE}" --type='json' -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"100m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"256Mi"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"300m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"512Mi"}
  ]' || true
}

format_hdfs_if_needed() {
  if kubectl exec -it hadoop-namenode-0 -n "${NAMESPACE}" -- hdfs dfsadmin -report >/dev/null 2>&1; then
    ok "HDFS already formatted"
    return
  fi

  warn "HDFS NameNode not formatted. Formatting now..."
  kubectl scale statefulset hadoop-namenode -n "${NAMESPACE}" --replicas=0

  cat <<'EOF' | kubectl apply -n "${NAMESPACE}" -f -
apiVersion: v1
kind: Pod
metadata:
  name: hdfs-namenode-format
spec:
  restartPolicy: Never
  containers:
  - name: formatter
    image: bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8
    command: ["bash","-lc","/entrypoint.sh /bin/true && HADOOP_CONF_DIR=/etc/hadoop /opt/hadoop-3.2.1/bin/hdfs namenode -format -force -nonInteractive"]
    env:
    - name: CLUSTER_NAME
      value: "bigdata-cluster"
    - name: CORE_CONF_fs_defaultFS
      value: "hdfs://hadoop-namenode:9000"
    - name: HDFS_CONF_dfs_namenode_name_dir
      value: "file:///hadoop/dfs/name"
    - name: HDFS_CONF_dfs_permissions_enabled
      value: "false"
    volumeMounts:
    - name: namenode-storage
      mountPath: /hadoop/dfs/name
  volumes:
  - name: namenode-storage
    persistentVolumeClaim:
      claimName: hdfs-namenode-pvc
EOF

  for i in {1..60}; do
    phase=$(kubectl get pod hdfs-namenode-format -n "${NAMESPACE}" -o jsonpath='{.status.phase}' 2>/dev/null || true)
    if [[ "${phase}" == "Succeeded" ]]; then
      break
    fi
    sleep 2
  done

  kubectl delete pod hdfs-namenode-format -n "${NAMESPACE}" || true
  kubectl scale statefulset hadoop-namenode -n "${NAMESPACE}" --replicas=1
}

fix_es_permissions_if_needed() {
  local logs
  logs=$(kubectl logs elasticsearch-0 -n "${NAMESPACE}" --tail=50 2>/dev/null || true)
  if echo "${logs}" | grep -q "AccessDeniedException"; then
    warn "Elasticsearch data permission issue detected. Fixing permissions..."
    kubectl scale statefulset elasticsearch -n "${NAMESPACE}" --replicas=0

    cat <<'EOF' | kubectl apply -n "${NAMESPACE}" -f -
apiVersion: v1
kind: Pod
metadata:
  name: elasticsearch-perms
spec:
  restartPolicy: Never
  containers:
  - name: fix-perms
    image: busybox:1.36
    command: ["sh","-c","chown -R 1000:1000 /data && chmod -R 770 /data"]
    volumeMounts:
    - name: es-data
      mountPath: /data
  volumes:
  - name: es-data
    persistentVolumeClaim:
      claimName: elasticsearch-pvc
EOF

    for i in {1..60}; do
      phase=$(kubectl get pod elasticsearch-perms -n "${NAMESPACE}" -o jsonpath='{.status.phase}' 2>/dev/null || true)
      if [[ "${phase}" == "Succeeded" ]]; then
        break
      fi
      sleep 2
    done

    kubectl delete pod elasticsearch-perms -n "${NAMESPACE}" || true
    kubectl scale statefulset elasticsearch -n "${NAMESPACE}" --replicas=1
  fi
}

main() {
  require_cmd kubectl

  log "Deploying Big Data system to namespace: ${NAMESPACE}"

  # Phase 00-01
  kubectl apply -f "${K8S_DIR}/00-namespace/"
  kubectl apply -f "${K8S_DIR}/01-config/"

  # Phase 02
  kubectl apply -f "${K8S_DIR}/02-storage/persistent-volumes-gke.yaml"
  sleep 10

  # Phase 03
  kubectl apply -f "${K8S_DIR}/03-infrastructure/zookeeper-statefulset.yaml"
  wait_statefulset zookeeper

  kubectl apply -f "${K8S_DIR}/03-infrastructure/kafka-statefulset.yaml"
  wait_statefulset kafka

  # Create Kafka topics if missing
  kubectl exec -it kafka-0 -n "${NAMESPACE}" -- kafka-topics --create --topic stocks-realtime \
    --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1 2>/dev/null || true
  kubectl exec -it kafka-0 -n "${NAMESPACE}" -- kafka-topics --create --topic stocks-realtime-spark \
    --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1 2>/dev/null || true

  kubectl apply -f "${K8S_DIR}/03-infrastructure/hdfs-statefulset.yaml"
  wait_pods_label hadoop-namenode
  wait_pods_label hadoop-datanode
  format_hdfs_if_needed

  kubectl apply -f "${K8S_DIR}/03-infrastructure/elasticsearch-statefulset.yaml"
  kubectl wait --for=condition=ready pod -l app=elasticsearch -n "${NAMESPACE}" --timeout=400s || true
  fix_es_permissions_if_needed
  kubectl wait --for=condition=ready pod -l app=elasticsearch -n "${NAMESPACE}" --timeout=400s || true

  # Apply small-node patches (after core services exist)
  apply_small_node_patches

  # Phase 04
  kubectl apply -f "${K8S_DIR}/04-applications/kafka-producer-crawl-deployment.yaml"
  wait_deployment kafka-producer-crawl

  kubectl apply -f "${K8S_DIR}/04-applications/kafka-spark-bridge-deployment.yaml"
  wait_deployment kafka-spark-bridge

  kubectl apply -f "${K8S_DIR}/04-applications/spark-streaming-consumer-deployment.yaml"
  wait_deployment spark-streaming-consumer

  kubectl apply -f "${K8S_DIR}/04-applications/spark-alerts-deployment.yaml"
  wait_deployment spark-streaming-alerts

  kubectl apply -f "${K8S_DIR}/04-applications/kibana-deployment-updated.yaml"
  wait_deployment kibana

  # Phase 05
  kubectl apply -f "${K8S_DIR}/05-jobs/hdfs-archiver-cronjob.yaml"
  kubectl apply -f "${K8S_DIR}/05-jobs/spark-batch-features-cronjob.yaml"

  ok "Deployment completed"
  kubectl get all -n "${NAMESPACE}"
}

main "$@"
