# Databricks notebook source
# MAGIC %md
# MAGIC ## Stream Bronze: All Events from Single Event Hub
# MAGIC Reads all events (transactions, fraud alerts, login events) from one Event Hub,
# MAGIC filters by `event_type`, and writes to separate Bronze Delta tables.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Config

# COMMAND ----------

storage_account = "gokulprojectadls"
kv_scope = "kv-bd-training-uk"

account_key = dbutils.secrets.get(scope=kv_scope, key="gokul-storage-account-key")
spark.conf.set(f"fs.azure.account.key.{storage_account}.dfs.core.windows.net", account_key)

bronze_base = f"abfss://bronze@{storage_account}.dfs.core.windows.net"
checkpoint_base = f"abfss://bronze@{storage_account}.dfs.core.windows.net/_checkpoints"

# COMMAND ----------

# MAGIC %md
# MAGIC ### Event Hub Connection (Kafka Protocol)

# COMMAND ----------

eh_namespace = "banking-gokul"
eh_name = "banking-transactions"
eh_connection_string = dbutils.secrets.get(scope=kv_scope, key="eventhub-connection-string-gokul")

if "EntityPath=" in eh_connection_string:
    eh_connection_string = eh_connection_string.split(";EntityPath=")[0]

kafka_bootstrap_servers = f"{eh_namespace}.servicebus.windows.net:9093"
kafka_sasl_config = f'kafkashaded.org.apache.kafka.common.security.plain.PlainLoginModule required username="$ConnectionString" password="{eh_connection_string}";'

# COMMAND ----------

# MAGIC %md
# MAGIC ### Read Single Stream from Event Hub

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType, BooleanType

raw_stream = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", kafka_bootstrap_servers)
    .option("kafka.security.protocol", "SASL_SSL")
    .option("kafka.sasl.mechanism", "PLAIN")
    .option("kafka.sasl.jaas.config", kafka_sasl_config)
    .option("subscribe", eh_name)
    .option("startingOffsets", "earliest")
    .option("kafka.request.timeout.ms", "60000")
    .option("kafka.session.timeout.ms", "30000")
    .load()
)

parsed_stream = (
    raw_stream
    .select(
        F.col("timestamp").alias("_enqueued_time"),
        F.col("offset").cast("string").alias("_offset"),
        F.col("value").cast("string").alias("json_body"),
    )
    .withColumn("event_type", F.get_json_object("json_body", "$.event_type"))
    .withColumn("_ingested_at", F.current_timestamp())
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Stream 1: Transactions

# COMMAND ----------

transaction_schema = StructType([
    StructField("transaction_id", StringType()),
    StructField("account_id", StringType()),
    StructField("customer_id", StringType()),
    StructField("transaction_type", StringType()),
    StructField("amount", DoubleType()),
    StructField("currency", StringType()),
    StructField("merchant", StringType()),
    StructField("channel", StringType()),
    StructField("city", StringType()),
    StructField("status", StringType()),
    StructField("timestamp", StringType()),
])

txn_stream = (
    parsed_stream
    .filter(F.col("event_type") == "transaction")
    .select(
        "_enqueued_time", "_offset", "_ingested_at",
        F.from_json("json_body", transaction_schema).alias("data"),
    )
    .select("_enqueued_time", "_offset", "_ingested_at", "data.*")
)

(
    txn_stream.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", f"{checkpoint_base}/transactions")
    .start(f"{bronze_base}/transactions")
)

print("Stream started: transactions")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Stream 2: Fraud Alerts

# COMMAND ----------

fraud_schema = StructType([
    StructField("alert_id", StringType()),
    StructField("transaction_id", StringType()),
    StructField("account_id", StringType()),
    StructField("customer_id", StringType()),
    StructField("fraud_type", StringType()),
    StructField("severity", StringType()),
    StructField("action_taken", StringType()),
    StructField("amount", DoubleType()),
    StructField("currency", StringType()),
    StructField("channel", StringType()),
    StructField("city", StringType()),
    StructField("risk_score", DoubleType()),
    StructField("is_confirmed_fraud", BooleanType()),
    StructField("timestamp", StringType()),
])

fraud_stream = (
    parsed_stream
    .filter(F.col("event_type") == "fraud_alert")
    .select(
        "_enqueued_time", "_offset", "_ingested_at",
        F.from_json("json_body", fraud_schema).alias("data"),
    )
    .select("_enqueued_time", "_offset", "_ingested_at", "data.*")
)

(
    fraud_stream.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", f"{checkpoint_base}/fraud_alerts")
    .start(f"{bronze_base}/fraud_alerts")
)

print("Stream started: fraud_alerts")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Stream 3: Login Events

# COMMAND ----------

login_schema = StructType([
    StructField("event_id", StringType()),
    StructField("customer_id", StringType()),
    StructField("login_status", StringType()),
    StructField("failure_reason", StringType()),
    StructField("login_method", StringType()),
    StructField("device", StringType()),
    StructField("browser", StringType()),
    StructField("city", StringType()),
    StructField("ip_address", StringType()),
    StructField("session_duration_seconds", IntegerType()),
    StructField("is_new_device", BooleanType()),
    StructField("timestamp", StringType()),
])

login_stream = (
    parsed_stream
    .filter(F.col("event_type") == "login_event")
    .select(
        "_enqueued_time", "_offset", "_ingested_at",
        F.from_json("json_body", login_schema).alias("data"),
    )
    .select("_enqueued_time", "_offset", "_ingested_at", "data.*")
)

(
    login_stream.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", f"{checkpoint_base}/login_events")
    .start(f"{bronze_base}/login_events")
)

print("Stream started: login_events")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Verify — check row counts (run after a few minutes)

# COMMAND ----------

# for table in ["transactions", "fraud_alerts", "login_events"]:
#     count = spark.read.format("delta").load(f"{bronze_base}/{table}").count()
#     print(f"{table}: {count} rows")
