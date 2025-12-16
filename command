#Xóa container cũ và network
docker-compose down
docker network prune -f
docker volume prune -f

#tao network thủ công
docker network create bigdata-network

#chay stack voi docker compose
docker-compose build python-worker
docker-compose up -d

#kiem tra network
docker network inspect bigdata-network


#tao topic
docker exec -it kafka bash
kafka-topics --create --topic stocks-history --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
kafka-topics --list --bootstrap-server localhost:9092

#chay producer
docker exec -it python-worker bash
python kafka_producer.py

#chay consumer
docker exec -it python-worker bash
python kafka_consumer.py

#kiem tra file tren hdfs
docker exec -it hadoop-namenode bash
hdfs dfs -ls /user/kafka_data/real_estate_by_date/2025/12/10

#xem nd
hdfs dfs -cat /user/kafka_data/real_estate_by_date/2025/12/10/data_*.jsonl | head


#xoa thu muc va toan bo file
hdfs dfs -rm -r /user/kafka_data/real_estate_by_date/2025/12/10