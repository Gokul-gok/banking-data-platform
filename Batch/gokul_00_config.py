# Databricks notebook source
# MAGIC %md
# MAGIC ## 00 - Config
# MAGIC Shared settings for Bronze, Silver, and Gold notebooks.
# MAGIC
# MAGIC - Storage account: `gokulprojectadls`
# MAGIC - Containers: `raw`, `bronze`, `silver`, `gold`
# MAGIC - Key Vault: `kv-bd-training-uk`, secret `storage-account-key`
# MAGIC - Databricks secret scope: `kv-bd-training-uk`

# COMMAND ----------

dbutils.widgets.text("storage_account", "gokulprojectadls", "Storage account name")
dbutils.widgets.text("raw_container", "raw", "Raw container name")
dbutils.widgets.text("bronze_container", "bronze", "Bronze container name")
dbutils.widgets.text("silver_container", "silver", "Silver container name")
dbutils.widgets.text("gold_container", "gold", "Gold container name")
dbutils.widgets.text("kv_scope", "kv-bd-training-uk", "Key Vault-backed secret scope name")
dbutils.widgets.text("kv_secret_key", "gokul-storage-account-key", "Secret name holding the storage key")

storage_account = dbutils.widgets.get("storage_account")
raw_container = dbutils.widgets.get("raw_container")
bronze_container = dbutils.widgets.get("bronze_container")
silver_container = dbutils.widgets.get("silver_container")
gold_container = dbutils.widgets.get("gold_container")
kv_scope = dbutils.widgets.get("kv_scope")
kv_secret_key = dbutils.widgets.get("kv_secret_key")

def require(value, widget_name):
    assert value and value.strip(), f"Set the {widget_name} widget before running."

require(storage_account, "storage_account")
require(raw_container, "raw_container")
require(bronze_container, "bronze_container")
require(silver_container, "silver_container")
require(gold_container, "gold_container")
require(kv_scope, "kv_scope")
require(kv_secret_key, "kv_secret_key")

# COMMAND ----------

account_key = dbutils.secrets.get(scope=kv_scope, key=kv_secret_key)
spark.conf.set(f"fs.azure.account.key.{storage_account}.dfs.core.windows.net", account_key)

# COMMAND ----------

raw_path = f"abfss://{raw_container}@{storage_account}.dfs.core.windows.net"
bronze_path = f"abfss://{bronze_container}@{storage_account}.dfs.core.windows.net"
silver_path = f"abfss://{silver_container}@{storage_account}.dfs.core.windows.net"
gold_path = f"abfss://{gold_container}@{storage_account}.dfs.core.windows.net"

spark.sql("CREATE DATABASE IF NOT EXISTS bronze")
spark.sql("CREATE DATABASE IF NOT EXISTS silver")
spark.sql("CREATE DATABASE IF NOT EXISTS gold")

DATASETS = {
    "accounts":   "accounts.csv",
    "cards":      "cards.csv",
    "customers":  "customers.csv",
    "loans":      "loans.csv",
}

print("raw_path   :", raw_path)
print("bronze_path:", bronze_path)
print("silver_path:", silver_path)
print("gold_path  :", gold_path)
print("datasets   :", list(DATASETS.keys()))
