# BÁO CÁO KỸ THUẬT – HỆ THỐNG BIG DATA PHÂN TÍCH CHỨNG KHOÁN

## 1. Kiến trúc hệ thống

### 1.1. Luồng dữ liệu tổng quát

1. **Kafka Producer** lấy dữ liệu giá cổ phiếu (real-time) từ Yahoo Finance.
2. **Kafka** giữ vai trò “bộ đệm” (buffer) – giúp hệ thống không bị nghẽn khi dữ liệu đến nhanh.
3. **Spark Streaming** đọc dữ liệu từ Kafka, tổng hợp theo cửa sổ thời gian (window) và ghi vào **Elasticsearch**.
4. **Kibana** đọc dữ liệu từ Elasticsearch để hiển thị dashboard và biểu đồ.
5. **HDFS + Spark Batch** lưu dữ liệu lịch sử và xử lý theo lô (batch) để tạo chỉ số phân tích dài hạn.

### 1.2. Giải thích thuật ngữ (bình dân)

- **Pod**: “Hộp” nhỏ nhất chạy ứng dụng trong K8s. Bên trong có container.
- **Service**: “Cổng” để các Pod giao tiếp với nhau hoặc với bên ngoài.
- **Deployment**: Quản lý số lượng Pod chạy cho ứng dụng (ví dụ Producer, Spark).
- **StatefulSet**: Giống Deployment nhưng giữ “danh tính” cố định (dùng cho Kafka/HDFS/Elasticsearch).
- **Consumer Group**: Nhóm các ứng dụng đọc Kafka, giúp chia tải đọc dữ liệu.
- **PVC/PV**: Ổ đĩa gắn vào Pod để dữ liệu không mất khi Pod restart.

### 1.3. Vai trò các thành phần

- **Kafka**: Hàng đợi dữ liệu, chống mất dữ liệu khi downstream chậm.
- **Spark Streaming**: Bộ xử lý real-time (tính trung bình, khối lượng, biến động…)
- **Elasticsearch**: Lưu dữ liệu để truy vấn nhanh.
- **Kibana**: Giao diện trực quan hóa.
- **Kubernetes**: Quản lý toàn bộ hệ thống, tự phục hồi khi lỗi.

---

## 2. Tại sao thiết kế như vậy?

### 2.1. Vì sao dùng Kubernetes thay Docker Compose?

- **Self-healing**: Pod lỗi sẽ tự khởi động lại.
- **Scale dễ dàng**: Tăng số lượng Kafka/Spark khi tải tăng.
- **Quản lý tài nguyên**: Giới hạn CPU/RAM từng dịch vụ, tránh “đánh nhau” tài nguyên.
- **Sản xuất thực tế**: K8s là chuẩn vận hành phổ biến trong doanh nghiệp.

### 2.2. Vì sao chia Partition/Kafka topic?

- Kafka giúp **tách Producer và Consumer**.
- Khi dữ liệu tăng, ta chỉ cần tăng số partition và consumer để **scale ngang**.
- Ví dụ: 1 producer gửi 5 mã cổ phiếu mỗi phút, Spark đọc nhiều partition sẽ xử lý nhanh hơn.

### 2.3. Vì sao có cả Streaming và Batch?

- **Streaming**: xử lý nhanh để hiển thị gần real-time.
- **Batch**: xử lý lịch sử, tính toán chỉ số dài hạn (Monthly/Quarterly).

---

## 3. Hướng dẫn vận hành (scripts)

### 3.1. Script triển khai tự động

```bash
# Deploy toàn bộ hệ thống theo đúng thứ tự, có chờ healthcheck
NAMESPACE=bigdata SMALL_NODES=1 ./deployment/scripts/deploy_all.sh
```

- `SMALL_NODES=1`: dùng khi cluster nhỏ (e2-medium). Tự giảm CPU/RAM cho Kafka/HDFS/ES/Spark/Kibana.
- Nếu cluster mạnh, đặt `SMALL_NODES=0`.

### 3.2. Script cleanup toàn bộ

```bash
# Xóa sạch toàn bộ tài nguyên trong namespace
NAMESPACE=bigdata ./deployment/scripts/cleanup_all.sh
```

- Sẽ xóa Pod, Service, PVC, PV, CronJob, Ingress…
- **Không thể khôi phục** sau khi xóa.

---

## 4. Khắc phục lỗi thường gặp

### 4.1. Kibana báo “No available fields”

**Nguyên nhân**:

- Index chưa có dữ liệu (doc count = 0)
- Kibana đang lọc sai time-range
- Index pattern chưa refresh field list

**Cách kiểm tra**:

```bash
kubectl port-forward svc/elasticsearch 9201:9200 -n bigdata &
sleep 3
curl -X GET "http://localhost:9201/stock-alerts-1m/_count"
curl -X GET "http://localhost:9201/stock-alerts-1m/_mapping?pretty"
```

**Cách xử lý**:

1. Nếu count = 0 → kiểm tra Spark Alerts log:
   ```bash
   kubectl logs -l app=spark-streaming-alerts -n bigdata --tail=50
   ```
2. Nếu có dữ liệu → vào Kibana **Index Patterns** → **Refresh field list**.
3. Kiểm tra lại **time-range** trong Discover (Last 15 minutes → Last 24 hours).

---

### 4.2. Pod Pending do thiếu CPU/RAM

- Trên node nhỏ (e2-medium) dễ bị thiếu CPU/RAM.
- Dùng `SMALL_NODES=1` khi deploy hoặc giảm resource từng Deployment.

---

### 4.3. HDFS NameNode “not formatted”

- HDFS cần format lần đầu.
- Script deploy đã tự xử lý, nhưng có thể làm tay bằng pod formatter.

---

### 4.4. Elasticsearch lỗi “AccessDeniedException”

- Do quyền thư mục dữ liệu trên PVC.
- Cần chạy pod fix quyền và scale lại ES.

---

## Kết luận

Hệ thống Big Data này tận dụng Kafka + Spark + Elasticsearch để xử lý dữ liệu chứng khoán real-time hiệu quả.
Kubernetes giúp hệ thống ổn định, tự phục hồi và mở rộng linh hoạt.
Với 2 script `deploy_all.sh` và `cleanup_all.sh`, việc vận hành đã được tự động hóa và dễ dàng hơn cho người mới.
