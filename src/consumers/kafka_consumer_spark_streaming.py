"""Kafka -> Spark Streaming bridge.

Goal:
- This consumer reads raw events from Kafka (e.g. topic: stocks-realtime)
- Republishes those events to a Spark-consumed topic (default: stocks-realtime-spark)
"""

import os
import signal
import sys
from typing import Optional

from confluent_kafka import Consumer, Producer, KafkaError


KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")

# Read raw producer events from here
INPUT_TOPIC = os.getenv("INPUT_TOPIC", os.getenv("KAFKA_TOPIC", "stocks-realtime"))

# Spark jobs should subscribe to this topic
SPARK_TOPIC = os.getenv("SPARK_TOPIC", "stocks-realtime-spark")

GROUP_ID = os.getenv("KAFKA_GROUP_ID", "spark-bridge")
AUTO_OFFSET_RESET = os.getenv("AUTO_OFFSET_RESET", "latest")


_shutdown = False


def _handle_signal(_signum: int, _frame: Optional[object]) -> None:
    global _shutdown
    _shutdown = True


def main() -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BROKER,
            "group.id": GROUP_ID,
            "auto.offset.reset": AUTO_OFFSET_RESET,
            "enable.auto.commit": False,
        }
    )

    producer = Producer({"bootstrap.servers": KAFKA_BROKER})

    print("[INIT] Kafka -> Spark bridge", flush=True)
    print(f"  broker={KAFKA_BROKER}", flush=True)
    print(f"  input_topic={INPUT_TOPIC}", flush=True)
    print(f"  spark_topic={SPARK_TOPIC}", flush=True)
    print(f"  group_id={GROUP_ID}", flush=True)

    consumer.subscribe([INPUT_TOPIC])

    delivered = 0
    try:
        while not _shutdown:
            msg = consumer.poll(1.0)
            if msg is None:
                continue

            if msg.error():
                # EOF is expected when reaching end of partition
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"[WARN] consumer error: {msg.error()}", flush=True)
                continue

            def _delivery_cb(err, _msg):
                if err is not None:
                    print(f"[WARN] produce failed: {err}", flush=True)

            ts = msg.timestamp()[1]
            kwargs = {}
            if ts is not None and ts > 0:
                kwargs["timestamp"] = ts

            producer.produce(
                SPARK_TOPIC,
                value=msg.value(),
                key=msg.key(),
                headers=msg.headers(),
                on_delivery=_delivery_cb,
                **kwargs,
            )
            producer.poll(0)
            consumer.commit(message=msg, asynchronous=True)

            delivered += 1
            if delivered % 1000 == 0:
                print(f"  bridged {delivered} messages...", flush=True)

    except KeyboardInterrupt:
        pass
    finally:
        try:
            print("[SHUTDOWN] Flushing producer...", flush=True)
            producer.flush(10)
        finally:
            consumer.close()
        print(f"[DONE] bridged_total={delivered}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FATAL] {e}", file=sys.stderr, flush=True)
        raise
