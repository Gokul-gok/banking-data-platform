# Databricks notebook source
# MAGIC %md
# MAGIC ## 01 - Bronze: load raw CSVs as-is
# MAGIC Copy raw CSV files into Delta format without changing any data.
# MAGIC Two tracking columns are added: `_source_file` and `_ingested_at`.

# COMMAND ----------

# MAGIC %run "./gokul_00_config"

# COMMAND ----------

from pyspark.sql import functions as F

for table_name, filename in DATASETS.items():
    df = (
        spark.read
        .option("header", True)
        .option("inferSchema", True)
        .csv(f"{raw_path}/{filename}")
    )

    df = (
        df
        .withColumn("_source_file", F.lit(filename))
        .withColumn("_ingested_at", F.current_timestamp())
    )

    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .save(f"{bronze_path}/{table_name}")
    )

    print(f"Bronze loaded: {table_name}  ({df.count()} rows, {len(df.columns)} cols) -> {bronze_path}/{table_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC Quick check — read every Bronze Delta table back and print its row count.

# COMMAND ----------

for table_name in DATASETS:
    n = spark.read.format("delta").load(f"{bronze_path}/{table_name}").count()
    print(f"{table_name}: {n} rows  ({bronze_path}/{table_name})")
