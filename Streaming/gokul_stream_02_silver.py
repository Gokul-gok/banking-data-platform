# Databricks notebook source
# MAGIC %md
# MAGIC ## Stream Silver: Clean all 3 Bronze streams
# MAGIC Reads from Bronze Delta (transactions, fraud_alerts, login_events), cleans, and writes to Silver.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Config

# COMMAND ----------

storage_account = "gokulprojectadls"
kv_scope = "kv-bd-training-uk"

account_key = dbutils.secrets.get(scope=kv_scope, key="gokul-storage-account-key")
spark.conf.set(f"fs.azure.account.key.{storage_account}.dfs.core.windows.net", account_key)

bronze_base = f"abfss://bronze@{storage_account}.dfs.core.windows.net"
silver_base = f"abfss://silver@{storage_account}.dfs.core.windows.net"
checkpoint_base = f"abfss://silver@{storage_account}.dfs.core.windows.net/_checkpoints"

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

# MAGIC %md
# MAGIC ### Silver 1: Transactions

# COMMAND ----------

txn_bronze = spark.readStream.format("delta").load(f"{bronze_base}/transactions")

txn_silver = (
    txn_bronze
    .filter(F.col("transaction_id").isNotNull())
    .filter(F.col("amount") > 0)
    .withColumn("timestamp", F.to_timestamp("timestamp"))
    .withColumn("date", F.to_date("timestamp"))
    .withColumn("hour", F.hour("timestamp"))
    .withColumn("day_of_week", F.dayofweek("timestamp"))
    .withColumn("day_name", F.date_format("timestamp", "EEEE"))
    .withColumn("year", F.year("timestamp"))
    .withColumn("month", F.month("timestamp"))
    .withColumn("year_month", F.date_format("timestamp", "yyyy-MM"))
    .withColumn("transaction_type", F.initcap(F.trim("transaction_type")))
    .withColumn("channel", F.initcap(F.trim("channel")))
    .withColumn("city", F.initcap(F.trim("city")))
    .withColumn("status", F.initcap(F.trim("status")))
    .withColumn("amount_category",
        F.when(F.col("amount") > 5000, "High Value")
         .when(F.col("amount") > 500, "Medium Value")
         .otherwise("Low Value")
    )
    .select(
        "transaction_id", "account_id", "customer_id",
        "transaction_type", "amount", "amount_category", "currency",
        "merchant", "channel", "city", "status",
        "timestamp", "date", "hour", "day_of_week", "day_name",
        "year", "month", "year_month",
        "_enqueued_time", "_ingested_at",
    )
)

(
    txn_silver.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", f"{checkpoint_base}/transactions")
    .start(f"{silver_base}/stream_transactions")
)

print("Silver stream started: transactions")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Silver 2: Fraud Alerts

# COMMAND ----------

fraud_bronze = spark.readStream.format("delta").load(f"{bronze_base}/fraud_alerts")

fraud_silver = (
    fraud_bronze
    .filter(F.col("alert_id").isNotNull())
    .withColumn("timestamp", F.to_timestamp("timestamp"))
    .withColumn("date", F.to_date("timestamp"))
    .withColumn("hour", F.hour("timestamp"))
    .withColumn("year", F.year("timestamp"))
    .withColumn("month", F.month("timestamp"))
    .withColumn("year_month", F.date_format("timestamp", "yyyy-MM"))
    .withColumn("fraud_type", F.initcap(F.trim("fraud_type")))
    .withColumn("severity", F.initcap(F.trim("severity")))
    .withColumn("action_taken", F.initcap(F.trim("action_taken")))
    .withColumn("channel", F.initcap(F.trim("channel")))
    .withColumn("city", F.initcap(F.trim("city")))
    .withColumn("severity_level",
        F.when(F.col("severity") == "Critical", 4)
         .when(F.col("severity") == "High", 3)
         .when(F.col("severity") == "Medium", 2)
         .otherwise(1)
    )
    .select(
        "alert_id", "transaction_id", "account_id", "customer_id",
        "fraud_type", "severity", "severity_level", "action_taken",
        "amount", "currency", "channel", "city",
        "risk_score", "is_confirmed_fraud",
        "timestamp", "date", "hour", "year", "month", "year_month",
        "_enqueued_time", "_ingested_at",
    )
)

(
    fraud_silver.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", f"{checkpoint_base}/fraud_alerts")
    .start(f"{silver_base}/stream_fraud_alerts")
)

print("Silver stream started: fraud_alerts")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Silver 3: Login Events

# COMMAND ----------

login_bronze = spark.readStream.format("delta").load(f"{bronze_base}/login_events")

login_silver = (
    login_bronze
    .filter(F.col("event_id").isNotNull())
    .withColumn("timestamp", F.to_timestamp("timestamp"))
    .withColumn("date", F.to_date("timestamp"))
    .withColumn("hour", F.hour("timestamp"))
    .withColumn("year", F.year("timestamp"))
    .withColumn("month", F.month("timestamp"))
    .withColumn("year_month", F.date_format("timestamp", "yyyy-MM"))
    .withColumn("login_status", F.initcap(F.trim("login_status")))
    .withColumn("login_method", F.initcap(F.trim("login_method")))
    .withColumn("device", F.initcap(F.trim("device")))
    .withColumn("browser", F.initcap(F.trim("browser")))
    .withColumn("city", F.initcap(F.trim("city")))
    .withColumn("session_category",
        F.when(F.col("session_duration_seconds") == 0, "Failed Login")
         .when(F.col("session_duration_seconds") < 300, "Quick Session")
         .when(F.col("session_duration_seconds") < 1800, "Normal Session")
         .otherwise("Long Session")
    )
    .select(
        "event_id", "customer_id",
        "login_status", "failure_reason", "login_method",
        "device", "browser", "city", "ip_address",
        "session_duration_seconds", "session_category", "is_new_device",
        "timestamp", "date", "hour", "year", "month", "year_month",
        "_enqueued_time", "_ingested_at",
    )
)

(
    login_silver.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", f"{checkpoint_base}/login_events")
    .start(f"{silver_base}/stream_login_events")
)

print("Silver stream started: login_events")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Verify — check row counts (run after a few minutes)

# COMMAND ----------

# for table in ["stream_transactions", "stream_fraud_alerts", "stream_login_events"]:
#     count = spark.read.format("delta").load(f"{silver_base}/{table}").count()
#     print(f"{table}: {count} rows")
