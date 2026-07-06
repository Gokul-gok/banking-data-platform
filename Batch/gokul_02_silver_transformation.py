# Databricks notebook source
# MAGIC %md
# MAGIC ## 02 - Silver: clean and fix data types
# MAGIC - Cast date columns from string to proper DATE type
# MAGIC - Cast numeric columns to correct types (int, double)
# MAGIC - Trim whitespace and standardize casing on text columns

# COMMAND ----------

# MAGIC %run "./gokul_00_config"

# COMMAND ----------

from pyspark.sql.functions import col, to_date, trim, initcap

DATE_FMT = "dd-MM-yyyy"

# COMMAND ----------

# MAGIC %md ### Customers

# COMMAND ----------

customers_silver = (
    spark.read.format("delta").load(f"{bronze_path}/customers")
    .withColumn("created_at", to_date(col("created_at"), DATE_FMT))
    .withColumn("credit_score", col("credit_score").cast("int"))
    .withColumn("city", trim(col("city")))
    .withColumn("first_name", trim(col("first_name")))
    .withColumn("last_name", trim(col("last_name")))
    .select("customer_id", "first_name", "last_name", "email", "city", "credit_score", "created_at")
)

customers_silver.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{silver_path}/customers")
print(f"Silver saved: customers  ({customers_silver.count()} rows) -> {silver_path}/customers")

# COMMAND ----------

# MAGIC %md ### Accounts

# COMMAND ----------

accounts_silver = (
    spark.read.format("delta").load(f"{bronze_path}/accounts")
    .withColumn("open_date", to_date(col("open_date"), DATE_FMT))
    .withColumn("balance_usd", col("balance_usd").cast("double"))
    .withColumn("account_type", initcap(trim(col("account_type"))))
    .withColumn("account_status", initcap(trim(col("account_status"))))
    .withColumn("closed_date", to_date(col("closed_date"), DATE_FMT))
    .withColumn("last_activity_date", to_date(col("last_activity_date"), DATE_FMT))
    .select(
        "account_id", "customer_id", "account_type", "balance_usd", "open_date",
        "account_status", "closed_date", "last_activity_date"
    )
)

accounts_silver.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{silver_path}/accounts")
print(f"Silver saved: accounts  ({accounts_silver.count()} rows) -> {silver_path}/accounts")

# COMMAND ----------

# MAGIC %md ### Cards

# COMMAND ----------

cards_silver = (
    spark.read.format("delta").load(f"{bronze_path}/cards")
    .withColumn("expiration_date", to_date(col("expiration_date"), DATE_FMT))
    .withColumn("card_type", initcap(trim(col("card_type"))))
    .select("card_id", "account_id", "card_type", "expiration_date")
)

cards_silver.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{silver_path}/cards")
print(f"Silver saved: cards  ({cards_silver.count()} rows) -> {silver_path}/cards")

# COMMAND ----------

# MAGIC %md ### Loans

# COMMAND ----------

loans_silver = (
    spark.read.format("delta").load(f"{bronze_path}/loans")
    .withColumn("start_date", to_date(col("start_date"), DATE_FMT))
    .withColumn("loan_amount", col("loan_amount").cast("double"))
    .withColumn("interest_rate", col("interest_rate").cast("double"))
    .select("loan_id", "customer_id", "loan_amount", "interest_rate", "start_date")
)

loans_silver.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{silver_path}/loans")
print(f"Silver saved: loans  ({loans_silver.count()} rows) -> {silver_path}/loans")

# COMMAND ----------

# MAGIC %md
# MAGIC Quick check — print schema of each Silver table.

# COMMAND ----------

for table_name in DATASETS:
    print(f"\n--- {table_name} ---")
    spark.read.format("delta").load(f"{silver_path}/{table_name}").printSchema()
