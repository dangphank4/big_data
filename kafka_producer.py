from confluent_kafka import Producer
import json
import time

TOPIC = "stocks-history"

conf = {
    "bootstrap.servers": "kafka:9092",
}

producer = Producer(conf)

def delivery_report(err, msg):
    if err:
        print("Delivery failed:", err)
    else:
        print(f"Sent to {msg.topic()} [{msg.partition()}] offset {msg.offset()}")

# Load dữ liệu JSON
with open("history_all.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Loaded {len(data)} history records")

# Gửi từng bản ghi
for record in data:
    producer.produce(
        TOPIC,
        value=json.dumps(record).encode("utf-8"),
        callback=delivery_report
    )
    producer.poll(0)  # cần cho confluent-kafka
    print("Sent:", record["ticker"], record["time"])
    time.sleep(0.2)

producer.flush()
print("Done sending history.")