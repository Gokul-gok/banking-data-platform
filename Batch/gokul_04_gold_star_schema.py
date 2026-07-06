# Databricks notebook source
# MAGIC %md
# MAGIC ## 04 - Gold: Star Schema (Dimension & Fact Tables)
# MAGIC Builds a proper star schema from Silver layer for Power BI dashboards.
# MAGIC
# MAGIC **Dimensions:** dim_customer, dim_date, dim_account_type, dim_risk
# MAGIC **Facts:** fact_account, fact_loan, fact_card

# COMMAND ----------

# MAGIC %md
# MAGIC ### Config & Authentication

# COMMAND ----------

storage_account = "gokulprojectadls"
silver_path = f"abfss://silver@{storage_account}.dfs.core.windows.net"
gold_path = f"abfss://gold@{storage_account}.dfs.core.windows.net"

# ============================================================
# FOR DATABRICKS: uncomment these 4 lines, comment Synapse block
# ============================================================
kv_scope = "kv-bd-training-uk"
kv_secret_key = "gokul-storage-account-key"
account_key = dbutils.secrets.get(scope=kv_scope, key=kv_secret_key)
spark.conf.set(f"fs.azure.account.key.{storage_account}.dfs.core.windows.net", account_key)

# ============================================================
# FOR SYNAPSE: uncomment these lines, comment Databricks block
# ============================================================
# spark.conf.set(f"fs.azure.account.auth.type.{storage_account}.dfs.core.windows.net", "OAuth")
# spark.conf.set(f"fs.azure.account.oauth.provider.type.{storage_account}.dfs.core.windows.net", "com.microsoft.azure.synapse.tokenlibrary.LinkedServiceBasedTokenProvider")
# spark.conf.set(f"fs.azure.account.oauth2.msi.tenantid.{storage_account}.dfs.core.windows.net", "<your-tenant-id>")
# spark.conf.set(f"spark.storage.synapse.linkedServiceName", "ls_gokulprojectadls")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Read Silver Tables

# COMMAND ----------

from pyspark.sql import functions as F

customers = spark.read.format("delta").load(f"{silver_path}/customers")
accounts = spark.read.format("delta").load(f"{silver_path}/accounts")
cards = spark.read.format("delta").load(f"{silver_path}/cards")
loans = spark.read.format("delta").load(f"{silver_path}/loans")

# COMMAND ----------

# MAGIC %md
# MAGIC ### dim_customer
# MAGIC Customer details with city — used for churn, gap analysis, city metrics

# COMMAND ----------

dim_customer = (
    customers
    .select(
        "customer_id",
        "first_name",
        "last_name",
        "email",
        "city",
        "credit_score",
        "created_at",
    )
    .withColumn("credit_tier",
        F.when(F.col("credit_score") >= 700, "Excellent")
         .when(F.col("credit_score") >= 600, "Good")
         .when(F.col("credit_score") >= 500, "Fair")
         .otherwise("Poor")
    )
)

dim_customer.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/dim_customer")
print(f"Gold saved: dim_customer  ({dim_customer.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### dim_date
# MAGIC Full date dimension — day, month, quarter, year for all dates in the data (2019–2027)

# COMMAND ----------

from pyspark.sql.types import DateType

date_range = spark.sql("SELECT sequence(to_date('2019-01-01'), to_date('2027-12-31'), interval 1 day) AS dates").selectExpr("explode(dates) AS date")

dim_date = (
    date_range
    .withColumn("date_key", F.date_format("date", "yyyyMMdd").cast("int"))
    .withColumn("day", F.dayofmonth("date"))
    .withColumn("month", F.month("date"))
    .withColumn("month_name", F.date_format("date", "MMMM"))
    .withColumn("month_short", F.date_format("date", "MMM"))
    .withColumn("quarter", F.quarter("date"))
    .withColumn("quarter_name", F.concat(F.lit("Q"), F.quarter("date")))
    .withColumn("year", F.year("date"))
    .withColumn("year_month", F.date_format("date", "yyyy-MM"))
    .withColumn("day_of_week", F.dayofweek("date"))
    .withColumn("day_name", F.date_format("date", "EEEE"))
    .withColumn("is_weekend", F.when(F.dayofweek("date").isin(1, 7), True).otherwise(False))
    .select(
        "date_key", "date", "day", "month", "month_name", "month_short",
        "quarter", "quarter_name", "year", "year_month",
        "day_of_week", "day_name", "is_weekend",
    )
)

dim_date.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/dim_date")
print(f"Gold saved: dim_date  ({dim_date.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### dim_account_type
# MAGIC Lookup table for account types

# COMMAND ----------

from pyspark.sql import Row

account_types = spark.createDataFrame([
    Row(account_type_id=1, account_type="Savings", description="Personal savings account"),
    Row(account_type_id=2, account_type="Checking", description="Daily transactions account"),
    Row(account_type_id=3, account_type="Business", description="Business operations account"),
])

account_types.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/dim_account_type")
print(f"Gold saved: dim_account_type  ({account_types.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### dim_risk
# MAGIC Risk categories based on credit score ranges

# COMMAND ----------

risk_categories = spark.createDataFrame([
    Row(risk_id=1, risk_category="Low Risk", score_min=700, score_max=850, description="Excellent credit, low default probability"),
    Row(risk_id=2, risk_category="Medium Risk", score_min=500, score_max=699, description="Average credit, moderate default probability"),
    Row(risk_id=3, risk_category="High Risk", score_min=300, score_max=499, description="Poor credit, high default probability"),
])

risk_categories.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/dim_risk")
print(f"Gold saved: dim_risk  ({risk_categories.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### fact_account
# MAGIC One row per account — balance, status, dates, churn & gap analysis fields

# COMMAND ----------

first_account_per_customer = (
    accounts
    .groupBy("customer_id")
    .agg(F.min("open_date").alias("first_account_date"))
)

fact_account = (
    accounts
    .join(customers.select("customer_id", "created_at", "credit_score"), "customer_id", "left")
    .join(first_account_per_customer, "customer_id", "left")
    .withColumn("open_date_key", F.date_format("open_date", "yyyyMMdd").cast("int"))
    .withColumn("account_type_id",
        F.when(F.col("account_type") == "Savings", 1)
         .when(F.col("account_type") == "Checking", 2)
         .when(F.col("account_type") == "Business", 3)
    )
    .withColumn("risk_id",
        F.when(F.col("credit_score") >= 700, 1)
         .when(F.col("credit_score") >= 500, 2)
         .otherwise(3)
    )
    .withColumn("days_since_last_activity",
        F.datediff(F.current_date(), F.col("last_activity_date"))
    )
    .withColumn("churn_status",
        F.when(F.col("account_status") == "Closed", "Churned")
         .when(F.col("days_since_last_activity") > 365, "At Risk")
         .when(F.col("days_since_last_activity") > 180, "Inactive")
         .otherwise("Active")
    )
    .withColumn("is_first_account",
        F.when(F.col("open_date") == F.col("first_account_date"), True).otherwise(False)
    )
    .withColumn("days_signup_to_account",
        F.datediff(F.col("open_date"), F.col("created_at"))
    )
    .withColumn("gap_category",
        F.when(F.col("days_signup_to_account").isNull(), "No Account")
         .when(F.col("days_signup_to_account") <= 0, "Same Day or Before")
         .when(F.col("days_signup_to_account") <= 7, "Within 1 Week")
         .when(F.col("days_signup_to_account") <= 30, "Within 1 Month")
         .when(F.col("days_signup_to_account") <= 90, "Within 3 Months")
         .otherwise("More than 3 Months")
    )
    .select(
        "account_id", "customer_id", "account_type_id", "risk_id", "open_date_key",
        "account_type", "balance_usd", "open_date", "account_status",
        "closed_date", "last_activity_date",
        "days_since_last_activity", "churn_status",
        "is_first_account", "days_signup_to_account", "gap_category",
    )
)

fact_account.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/fact_account")
print(f"Gold saved: fact_account  ({fact_account.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### fact_loan
# MAGIC One row per loan — amount, interest rate, risk category

# COMMAND ----------

fact_loan = (
    loans
    .join(customers.select("customer_id", "credit_score", "city"), "customer_id", "left")
    .withColumn("start_date_key", F.date_format("start_date", "yyyyMMdd").cast("int"))
    .withColumn("risk_id",
        F.when(F.col("credit_score") >= 700, 1)
         .when(F.col("credit_score") >= 500, 2)
         .otherwise(3)
    )
    .withColumn("risk_category",
        F.when(F.col("credit_score") >= 700, "Low Risk")
         .when(F.col("credit_score") >= 500, "Medium Risk")
         .otherwise("High Risk")
    )
    .withColumn("year", F.year("start_date"))
    .withColumn("month", F.month("start_date"))
    .select(
        "loan_id", "customer_id", "risk_id", "start_date_key",
        "loan_amount", "interest_rate", "start_date",
        "credit_score", "city", "risk_category",
        "year", "month",
    )
)

fact_loan.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/fact_loan")
print(f"Gold saved: fact_loan  ({fact_loan.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### fact_card
# MAGIC One row per card — linked to account

# COMMAND ----------

fact_card = (
    cards
    .join(accounts.select("account_id", "customer_id", "account_type"), "account_id", "left")
    .withColumn("expiration_date_key", F.date_format("expiration_date", "yyyyMMdd").cast("int"))
    .select(
        "card_id", "account_id", "customer_id",
        "card_type", "account_type", "expiration_date", "expiration_date_key",
    )
)

fact_card.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(f"{gold_path}/fact_card")
print(f"Gold saved: fact_card  ({fact_card.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Verify — list all Star Schema tables

# COMMAND ----------

star_tables = [
    "dim_customer", "dim_date", "dim_account_type", "dim_risk",
    "fact_account", "fact_loan", "fact_card",
]

for table in star_tables:
    df = spark.read.format("delta").load(f"{gold_path}/{table}")
    print(f"{table}: {df.count()} rows, {len(df.columns)} cols")
