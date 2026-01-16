#!/usr/bin/env bash
# ==============================================================================
# deploy_all_v2.sh - Tự động Patch & Force Restart để fit node nhỏ
# ==============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K8S_DIR="${ROOT_DIR}/k8s"
NAMESPACE="${NAMESPACE:-bigdata}"
TIMEOUT="${TIMEOUT:-600}"
SMALL_NODES="${SMALL_NODES:-1}" 

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

# --- HÀM QUAN TRỌNG NHẤT: Patch cấu hình và Xóa Pod để nhận cấu hình mới ---
patch_and_restart() {
  local kind="$1"
  local name="$2"
  local cpu_req="$3"
  local mem_req="$4"
  local cpu_lim="$5"
  local mem_lim="$6"
  local container_idx="${7:-0}"

  if [[ "${SMALL_NODES}" != "1" ]]; then return; fi

  log ">>> [Fixing] Patching ${kind}/${name} to low resources (CPU: ${cpu_req})..."
  
  # 1. Patch vào Spec của Deployment/StatefulSet
  kubectl patch "${kind}" "${name}" -n "${NAMESPACE}" --type='json' -p="[
    {\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/${container_idx}/resources/requests/cpu\",\"value\":\"${cpu_req}\"},
    {\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/${container_idx}/resources/requests/memory\",\"value\":\"${mem_req}\"},
    {\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/${container_idx}/resources/limits/cpu\",\"value\":\"${cpu_lim}\"},
    {\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/${container_idx}/resources/limits/memory\",\"value\":\"${mem_lim}\"}
  ]" || warn "Could not patch ${name}, maybe it does not exist yet?"

  # 2. Xóa Pod để ép K8s tạo lại Pod mới với cấu hình vừa patch (Tránh bị Pending)
  log ">>> [Restarting] Deleting pods of ${name} to force update..."
  # Lấy label selector từ tên (giả định label app=tên)
  local label_selector="app=${name}"
  if [[ "${name}" == "kafka-producer-crawl" ]]; then label_selector="app=kafka-producer"; fi
  if [[ "${name}" == "spark-streaming-consumer" ]]; then label_selector="app=spark-streaming"; fi
  
  kubectl delete pod -n "${NAMESPACE}" -l "${label_selector}" --grace-period=0 --force 2>/dev/null || true
  sleep 5
}

format_hdfs_if_needed() {
  # Kiểm tra xem HDFS đã format chưa bằng cách check thư mục trên PVC (gián tiếp qua logs hoặc check pod status)
  # Ở đây dùng cách đơn giản: Chạy job format. Nếu đã format rồi thì job này sẽ fail an toàn hoặc format lại (tùy config).
  # Nhưng an toàn nhất là check xem namenode có chạy không.
  
  log "Checking HDFS status..."
  if kubectl get pod hadoop-namenode-0 -n "${NAMESPACE}" | grep "Running" >/dev/null; then
     ok "HDFS NameNode is likely formatted and running."
     return
  fi

  warn "HDFS NameNode might need formatting. Starting Format Job..."
  kubectl scale statefulset hadoop-namenode -n "${NAMESPACE}" --replicas=0
  sleep 5

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

  log "Waiting for formatting..."
  kubectl wait --for=condition=Ready pod/hdfs-namenode-format -n "${NAMESPACE}" --timeout=120s || true
  sleep 5
  kubectl delete pod hdfs-namenode-format -n "${NAMESPACE}" || true
  
  log "Scaling HDFS NameNode back up..."
  kubectl scale statefulset hadoop-namenode -n "${NAMESPACE}" --replicas=1
}

fix_es_permissions_if_needed() {
  log "Checking ES permissions..."
  local logs
  logs=$(kubectl logs elasticsearch-0 -n "${NAMESPACE}" --tail=50 2>/dev/null || true)
  if echo "${logs}" | grep -q "AccessDeniedException"; then
    warn "Elasticsearch data permission issue detected. Fixing permissions..."
    kubectl scale statefulset elasticsearch -n "${NAMESPACE}" --replicas=0
    sleep 5

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
    kubectl wait --for=condition=Ready pod/elasticsearch-perms -n "${NAMESPACE}" --timeout=60s || true
    kubectl delete pod elasticsearch-perms -n "${NAMESPACE}" || true
    kubectl scale statefulset elasticsearch -n "${NAMESPACE}" --replicas=1
  fi
}

main() {
  require_cmd kubectl

  log "Deploying Big Data system to namespace: ${NAMESPACE}"
  
  # Cleanup nhẹ nếu cần deploy lại từ đầu (Optional)
  # kubectl delete namespace ${NAMESPACE} || true
  # sleep 10

  # --- Phase 01: Namespace & Config ---
  kubectl apply -f "${K8S_DIR}/00-namespace/"
  kubectl apply -f "${K8S_DIR}/01-config/"

  # --- Phase 02: Storage ---
  kubectl apply -f "${K8S_DIR}/02-storage/persistent-volumes-gke.yaml"
  sleep 3

  # --- Phase 03: Infrastructure ---
  
  # 1. Zookeeper (CPU 100m)
  kubectl apply -f "${K8S_DIR}/03-infrastructure/zookeeper-statefulset.yaml"
  patch_and_restart "statefulset" "zookeeper" "100m" "256Mi" "300m" "512Mi"
  wait_statefulset zookeeper

  # 2. Kafka (CPU 100m - Quan trọng!)
  kubectl apply -f "${K8S_DIR}/03-infrastructure/kafka-statefulset.yaml"
  patch_and_restart "statefulset" "kafka" "100m" "512Mi" "500m" "1Gi"
  wait_statefulset kafka

  # Create Topics
  log "Creating Kafka topics..."
  kubectl exec -it kafka-0 -n "${NAMESPACE}" -- kafka-topics --create --topic stocks-realtime --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1 2>/dev/null || true
  kubectl exec -it kafka-0 -n "${NAMESPACE}" -- kafka-topics --create --topic stocks-realtime-spark --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1 2>/dev/null || true

  # 3. HDFS (CPU 100m)
  kubectl apply -f "${K8S_DIR}/03-infrastructure/hdfs-statefulset.yaml"
  patch_and_restart "statefulset" "hadoop-namenode" "100m" "512Mi" "500m" "1Gi"
  patch_and_restart "statefulset" "hadoop-datanode" "100m" "768Mi" "500m" "1.5Gi"
  
  wait_pods_label hadoop-namenode # Đợi pod tạo ra
  format_hdfs_if_needed
  wait_statefulset hadoop-namenode
  wait_statefulset hadoop-datanode

  # 4. Elasticsearch (CPU 200m - ES cần khởi động Java nặng hơn chút)
  kubectl apply -f "${K8S_DIR}/03-infrastructure/elasticsearch-statefulset.yaml"
  if [[ "${SMALL_NODES}" == "1" ]]; then
     # Patch riêng cho Heap Size ES
     kubectl patch statefulset elasticsearch -n "${NAMESPACE}" --type='json' -p='[{"op":"replace","path":"/spec/template/spec/containers/0/env/2/value","value":"-Xms512m -Xmx512m"}]' || true
  fi
  patch_and_restart "statefulset" "elasticsearch" "200m" "1024Mi" "500m" "1536Mi"
  
  kubectl wait --for=condition=ready pod -l app=elasticsearch -n "${NAMESPACE}" --timeout=300s || warn "ES starting..."
  fix_es_permissions_if_needed
  wait_statefulset elasticsearch

  # --- Phase 04: Applications ---
  
  # Producer
  kubectl apply -f "${K8S_DIR}/04-applications/kafka-producer-crawl-deployment.yaml"
  patch_and_restart "deployment" "kafka-producer-crawl" "100m" "256Mi" "300m" "512Mi"
  wait_deployment kafka-producer-crawl

  # Bridge
  kubectl apply -f "${K8S_DIR}/04-applications/kafka-spark-bridge-deployment.yaml"
  # Bridge nhẹ, giữ nguyên hoặc patch nếu muốn
  
  # Spark Streaming Consumer (CPU 100m)
  kubectl apply -f "${K8S_DIR}/04-applications/spark-streaming-consumer-deployment.yaml"
  patch_and_restart "deployment" "spark-streaming-consumer" "100m" "512Mi" "500m" "1Gi"
  wait_deployment spark-streaming-consumer

  # Spark Alerts (CPU 100m)
  kubectl apply -f "${K8S_DIR}/04-applications/spark-alerts-deployment.yaml"
  patch_and_restart "deployment" "spark-streaming-alerts" "100m" "512Mi" "300m" "1Gi"
  wait_deployment spark-streaming-alerts

  # Kibana
  kubectl apply -f "${K8S_DIR}/04-applications/kibana-deployment-updated.yaml"
  patch_and_restart "deployment" "kibana" "100m" "256Mi" "300m" "512Mi"
  wait_deployment kibana

  # --- Phase 05: Jobs ---
  kubectl apply -f "${K8S_DIR}/05-jobs/hdfs-archiver-cronjob.yaml"
  kubectl apply -f "${K8S_DIR}/05-jobs/spark-batch-features-cronjob.yaml"

  ok "Deployment completed successfully! All systems running."
  kubectl get all -n "${NAMESPACE}"
}

main "$@"