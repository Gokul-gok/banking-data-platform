import json
import random
import time
import threading
from datetime import datetime
from azure.eventhub import EventHubProducerClient, EventData

# ============================================================
# CONFIGURATION — update before running
# ============================================================
EVENT_HUB_CONNECTION_STRING = "Endpoint=sb://banking-gokul.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=<YOUR_SHARED_ACCESS_KEY>"
EVENT_HUB_NAME = "banking-transactions"
# ============================================================

CITIES = [
    "London", "Manchester", "Birmingham", "Leeds", "Glasgow",
    "Liverpool", "Bristol", "Edinburgh", "Sheffield", "Cardiff",
    "Newcastle", "Nottingham", "Belfast", "Leicester", "Southampton",
    "Brighton", "Oxford", "Cambridge", "York", "Bath",
]

MERCHANTS = [
    "Tesco", "Sainsbury's", "Amazon UK", "Shell", "BP",
    "Costa Coffee", "Starbucks", "McDonald's", "Netflix", "Spotify",
    "TfL", "National Rail", "Uber", "Deliveroo", "Just Eat",
    "Apple Store", "Argos", "John Lewis", "Boots", "Primark",
]

def rand_id(prefix):
    return f"{prefix}{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=12))}"

def now_time():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def now_short():
    return datetime.now().strftime("%H:%M:%S")


def generate_transaction():
    txn_type = random.choice(["Deposit", "Withdrawal", "Transfer", "Payment", "Refund"])
    amounts = {"Deposit": (2000, 1500), "Withdrawal": (200, 150), "Transfer": (500, 400), "Payment": (80, 60), "Refund": (50, 30)}
    mean, std = amounts[txn_type]

    return {
        "event_type": "transaction",
        "transaction_id": rand_id("TXN"),
        "account_id": rand_id("ACC"),
        "customer_id": rand_id("CUS"),
        "transaction_type": txn_type,
        "amount": max(1.0, round(random.gauss(mean, std), 2)),
        "currency": "GBP",
        "merchant": random.choice(MERCHANTS) if txn_type == "Payment" else None,
        "channel": random.choice(["ATM", "Online", "Mobile App", "Branch", "POS"]),
        "city": random.choice(CITIES),
        "status": random.choice(["Completed", "Completed", "Completed", "Completed", "Failed", "Pending"]),
        "timestamp": now_time(),
    }


def generate_fraud_alert():
    fraud_type = random.choice([
        "Unusual Location", "Large Transaction", "Multiple Failed Attempts",
        "Card Not Present", "Velocity Check", "Account Takeover",
        "Suspicious Merchant", "Cross-Border Transaction",
    ])
    amounts = {"Large Transaction": (15000, 8000), "Card Not Present": (500, 300), "Cross-Border Transaction": (3000, 2000)}
    mean, std = amounts.get(fraud_type, (1000, 800))

    severity = random.choice(["Low", "Low", "Medium", "Medium", "Medium", "High", "High", "Critical"])
    if severity == "Critical":
        action = "Blocked"
    elif severity == "High":
        action = random.choice(["Blocked", "Flagged for Review"])
    else:
        action = random.choice(["Blocked", "Blocked", "Flagged for Review", "Flagged for Review", "Allowed with Alert"])

    return {
        "event_type": "fraud_alert",
        "alert_id": rand_id("FRD"),
        "transaction_id": rand_id("TXN"),
        "account_id": rand_id("ACC"),
        "customer_id": rand_id("CUS"),
        "fraud_type": fraud_type,
        "severity": severity,
        "action_taken": action,
        "amount": max(10.0, round(random.gauss(mean, std), 2)),
        "currency": "GBP",
        "channel": random.choice(["ATM", "Online", "Mobile App", "POS", "Wire Transfer"]),
        "city": random.choice(CITIES),
        "risk_score": round(random.uniform(0.3, 1.0) if severity in ("High", "Critical") else random.uniform(0.1, 0.7), 2),
        "is_confirmed_fraud": random.choice([True, False, False, False, False]),
        "timestamp": now_time(),
    }


def generate_login_event():
    is_success = random.choices([True, False], weights=[85, 15], k=1)[0]

    return {
        "event_type": "login_event",
        "event_id": rand_id("LOG"),
        "customer_id": rand_id("CUS"),
        "login_status": "Success" if is_success else "Failed",
        "failure_reason": None if is_success else random.choice(["Wrong Password", "Account Locked", "Expired Session", "Invalid OTP", "Suspicious IP"]),
        "login_method": random.choice(["Password", "Password", "Biometric", "Biometric", "OTP", "SSO"]),
        "device": random.choice(["iPhone", "Android", "Windows PC", "MacBook", "iPad", "Linux PC"]),
        "browser": random.choice(["Chrome", "Safari", "Firefox", "Edge", "Mobile App"]),
        "city": random.choice(CITIES),
        "ip_address": f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,255)}",
        "session_duration_seconds": random.randint(30, 3600) if is_success else 0,
        "is_new_device": random.choices([True, False], weights=[20, 80], k=1)[0],
        "timestamp": now_time(),
    }


def send_stream(producer, generator_fn, batch_size, interval_seconds, label):
    batch_count = 0
    try:
        while True:
            event_batch = producer.create_batch()
            for _ in range(batch_size):
                event_batch.add(EventData(json.dumps(generator_fn())))
            producer.send_batch(event_batch)
            batch_count += 1
            print(f"[{label}] Batch {batch_count}: Sent {batch_size} events at {now_short()}")
            time.sleep(interval_seconds)
    except Exception as e:
        print(f"[{label}] Error: {e}")


if __name__ == "__main__":
    print(f"Sending all events to single Event Hub: {EVENT_HUB_NAME}")
    print("Press Ctrl+C to stop.\n")

    producer = EventHubProducerClient.from_connection_string(
        conn_str=EVENT_HUB_CONNECTION_STRING,
        eventhub_name=EVENT_HUB_NAME,
    )

    streams = [
        (generate_transaction, 3, 11, "TRANSACTIONS"),
        (generate_fraud_alert, 1, 12, "FRAUD"),
        (generate_login_event, 2, 10, "LOGIN"),
    ]

    threads = []
    for gen_fn, batch, interval, label in streams:
        t = threading.Thread(target=send_stream, args=(producer, gen_fn, batch, interval, label), daemon=True)
        t.start()
        threads.append(t)
        print(f"  Started: {label} (batch={batch}, interval={interval}s)")

    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        producer.close()
