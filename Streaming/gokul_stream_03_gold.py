# Databricks notebook source
# MAGIC %md
# MAGIC ## Stream Gold: Business-ready tables from streaming data
# MAGIC Reads from Silver streaming tables and writes Gold aggregations for dashboards.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Config

# COMMAND ----------

storage_account = "gokulprojectadls"
kv_scope = "kv-bd-training-uk"

account_key = dbutils.secrets.get(scope=kv_scope, key="gokul-storage-account-key")
spark.conf.set(f"fs.azure.account.key.{storage_account}.dfs.core.windows.net", account_key)

silver_base = f"abfss://silver@{storage_account}.dfs.core.windows.net"
gold_path = f"abfss://gold@{storage_account}.dfs.core.windows.net"

# COMMAND ----------

from pyspark.sql import functions as F

# Read Silver tables (batch read — Gold runs periodically, not as a stream)
transactions = spark.read.format("delta").load(f"{silver_base}/stream_transactions")
fraud_alerts = spark.read.format("delta").load(f"{silver_base}/stream_fraud_alerts")
login_events = spark.read.format("delta").load(f"{silver_base}/stream_login_events")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Gold 1: Transaction Summary by Hour
# MAGIC Real-time volume and amount trends

# COMMAND ----------

gold_txn_hourly = (
    transactions
    .groupBy("date", "hour")
    .agg(
        F.count("transaction_id").alias("total_transactions"),
        F.round(F.sum("amount"), 2).alias("total_amount"),
        F.round(F.avg("amount"), 2).alias("avg_amount"),
        F.sum(F.when(F.col("status") == "Completed", 1).otherwise(0)).alias("completed"),
        F.sum(F.when(F.col("status") == "Failed", 1).otherwise(0)).alias("failed"),
        F.sum(F.when(F.col("status") == "Pending", 1).otherwise(0)).alias("pending"),
    )
    .orderBy("date", "hour")
)

gold_txn_hourly.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/stream_txn_hourly")
print(f"Gold saved: stream_txn_hourly  ({gold_txn_hourly.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Gold 2: Transaction Summary by City
# MAGIC Which cities have the most transaction activity

# COMMAND ----------

gold_txn_city = (
    transactions
    .groupBy("city")
    .agg(
        F.count("transaction_id").alias("total_transactions"),
        F.round(F.sum("amount"), 2).alias("total_amount"),
        F.round(F.avg("amount"), 2).alias("avg_amount"),
        F.sum(F.when(F.col("transaction_type") == "Deposit", 1).otherwise(0)).alias("deposits"),
        F.sum(F.when(F.col("transaction_type") == "Withdrawal", 1).otherwise(0)).alias("withdrawals"),
        F.sum(F.when(F.col("transaction_type") == "Payment", 1).otherwise(0)).alias("payments"),
        F.sum(F.when(F.col("transaction_type") == "Transfer", 1).otherwise(0)).alias("transfers"),
        F.sum(F.when(F.col("status") == "Failed", 1).otherwise(0)).alias("failed_transactions"),
    )
    .orderBy(F.desc("total_transactions"))
)

gold_txn_city.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/stream_txn_city")
print(f"Gold saved: stream_txn_city  ({gold_txn_city.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Gold 3: Transaction Type Breakdown
# MAGIC Volume and amount by transaction type and channel

# COMMAND ----------

gold_txn_type = (
    transactions
    .groupBy("transaction_type", "channel")
    .agg(
        F.count("transaction_id").alias("total_transactions"),
        F.round(F.sum("amount"), 2).alias("total_amount"),
        F.round(F.avg("amount"), 2).alias("avg_amount"),
        F.sum(F.when(F.col("amount_category") == "High Value", 1).otherwise(0)).alias("high_value_count"),
    )
    .orderBy("transaction_type", "channel")
)

gold_txn_type.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/stream_txn_type")
print(f"Gold saved: stream_txn_type  ({gold_txn_type.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Gold 4: Fraud Monitoring Dashboard
# MAGIC Fraud alerts by severity, type, and city

# COMMAND ----------

gold_fraud_summary = (
    fraud_alerts
    .groupBy("fraud_type", "severity", "action_taken")
    .agg(
        F.count("alert_id").alias("total_alerts"),
        F.round(F.sum("amount"), 2).alias("total_amount_flagged"),
        F.round(F.avg("risk_score"), 2).alias("avg_risk_score"),
        F.sum(F.when(F.col("is_confirmed_fraud") == True, 1).otherwise(0)).alias("confirmed_frauds"),
    )
    .orderBy(F.desc("total_alerts"))
)

gold_fraud_summary.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/stream_fraud_summary")
print(f"Gold saved: stream_fraud_summary  ({gold_fraud_summary.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Gold 5: Fraud by City
# MAGIC Which cities have the most fraud alerts

# COMMAND ----------

gold_fraud_city = (
    fraud_alerts
    .groupBy("city")
    .agg(
        F.count("alert_id").alias("total_alerts"),
        F.round(F.sum("amount"), 2).alias("total_amount_flagged"),
        F.round(F.avg("risk_score"), 2).alias("avg_risk_score"),
        F.sum(F.when(F.col("severity") == "Critical", 1).otherwise(0)).alias("critical_alerts"),
        F.sum(F.when(F.col("severity") == "High", 1).otherwise(0)).alias("high_alerts"),
        F.sum(F.when(F.col("is_confirmed_fraud") == True, 1).otherwise(0)).alias("confirmed_frauds"),
    )
    .orderBy(F.desc("total_alerts"))
)

gold_fraud_city.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/stream_fraud_city")
print(f"Gold saved: stream_fraud_city  ({gold_fraud_city.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Gold 6: Fraud Hourly Trend
# MAGIC Fraud alerts over time for real-time monitoring

# COMMAND ----------

gold_fraud_hourly = (
    fraud_alerts
    .groupBy("date", "hour")
    .agg(
        F.count("alert_id").alias("total_alerts"),
        F.round(F.sum("amount"), 2).alias("total_amount_flagged"),
        F.sum(F.when(F.col("severity").isin("High", "Critical"), 1).otherwise(0)).alias("high_severity_alerts"),
        F.sum(F.when(F.col("action_taken") == "Blocked", 1).otherwise(0)).alias("blocked_count"),
    )
    .orderBy("date", "hour")
)

gold_fraud_hourly.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/stream_fraud_hourly")
print(f"Gold saved: stream_fraud_hourly  ({gold_fraud_hourly.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Gold 7: Login Analytics
# MAGIC Login success/failure rates by method and device

# COMMAND ----------

gold_login_summary = (
    login_events
    .groupBy("login_method", "device")
    .agg(
        F.count("event_id").alias("total_logins"),
        F.sum(F.when(F.col("login_status") == "Success", 1).otherwise(0)).alias("successful"),
        F.sum(F.when(F.col("login_status") == "Failed", 1).otherwise(0)).alias("failed"),
        F.round(
            F.sum(F.when(F.col("login_status") == "Failed", 1).otherwise(0)) / F.count("event_id") * 100, 2
        ).alias("failure_rate_pct"),
        F.round(F.avg("session_duration_seconds"), 0).alias("avg_session_seconds"),
        F.sum(F.when(F.col("is_new_device") == True, 1).otherwise(0)).alias("new_device_logins"),
    )
    .orderBy(F.desc("total_logins"))
)

gold_login_summary.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/stream_login_summary")
print(f"Gold saved: stream_login_summary  ({gold_login_summary.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Gold 8: Login Failure Analysis
# MAGIC Why are logins failing — breakdown by reason and city

# COMMAND ----------

gold_login_failures = (
    login_events
    .filter(F.col("login_status") == "Failed")
    .groupBy("failure_reason", "city")
    .agg(
        F.count("event_id").alias("failed_logins"),
        F.sum(F.when(F.col("is_new_device") == True, 1).otherwise(0)).alias("new_device_failures"),
    )
    .orderBy(F.desc("failed_logins"))
)

gold_login_failures.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/stream_login_failures")
print(f"Gold saved: stream_login_failures  ({gold_login_failures.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Gold 9: Login Hourly Trend
# MAGIC Login activity over time

# COMMAND ----------

gold_login_hourly = (
    login_events
    .groupBy("date", "hour")
    .agg(
        F.count("event_id").alias("total_logins"),
        F.sum(F.when(F.col("login_status") == "Success", 1).otherwise(0)).alias("successful"),
        F.sum(F.when(F.col("login_status") == "Failed", 1).otherwise(0)).alias("failed"),
        F.round(F.avg("session_duration_seconds"), 0).alias("avg_session_seconds"),
    )
    .orderBy("date", "hour")
)

gold_login_hourly.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/stream_login_hourly")
print(f"Gold saved: stream_login_hourly  ({gold_login_hourly.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Verify — list all streaming Gold tables

# COMMAND ----------

stream_gold_tables = [
    "stream_txn_hourly", "stream_txn_city", "stream_txn_type",
    "stream_fraud_summary", "stream_fraud_city", "stream_fraud_hourly",
    "stream_login_summary", "stream_login_failures", "stream_login_hourly",
]

for table in stream_gold_tables:
    df = spark.read.format("delta").load(f"{gold_path}/{table}")
    print(f"{table}: {df.count()} rows, {len(df.columns)} cols")
