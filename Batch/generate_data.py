import csv, random, string
from datetime import datetime, timedelta

random.seed(42)

DATA_DIR = "Data"

CITIES = {
    "London": 8000, "Manchester": 4500, "Birmingham": 4000, "Leeds": 3500,
    "Glasgow": 3000, "Liverpool": 2500, "Bristol": 2500, "Edinburgh": 2000,
    "Sheffield": 2000, "Cardiff": 1800, "Newcastle": 1500, "Nottingham": 1500,
    "Belfast": 1200, "Leicester": 1000, "Southampton": 1000, "Brighton": 900,
    "Oxford": 800, "Cambridge": 700, "York": 600, "Bath": 500,
    "Aberdeen": 450, "Exeter": 400, "Norwich": 350, "Dundee": 300,
    "Swansea": 250, "Plymouth": 200, "Chester": 180, "Inverness": 150,
    "Canterbury": 120, "Durham": 100,
}

FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "David", "William", "Richard", "Joseph", "Thomas", "Charles",
    "Sarah", "Emma", "Olivia", "Sophie", "Emily", "Amelia", "Grace", "Jessica", "Lucy", "Charlotte",
    "Daniel", "Matthew", "Andrew", "Jack", "Harry", "Oliver", "George", "Edward", "Samuel", "Benjamin",
    "Hannah", "Mia", "Isla", "Lily", "Ava", "Ella", "Chloe", "Ruby", "Freya", "Poppy",
]

LAST_NAMES = [
    "Smith", "Jones", "Williams", "Taylor", "Brown", "Davies", "Evans", "Wilson", "Thomas", "Roberts",
    "Johnson", "Walker", "Wright", "Thompson", "White", "Hughes", "Edwards", "Green", "Hall", "Lewis",
    "Martin", "Jackson", "Clarke", "Wood", "Harris", "King", "Baker", "Turner", "Scott", "Young",
]

START = datetime(2019, 1, 1)
END = datetime(2026, 6, 1)


def rand_id(prefix, length=12):
    return prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def rand_date(start, end):
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=random.randint(0, delta))


def credit_score_for_city(city):
    pop = CITIES[city]
    if pop >= 4000:
        base = random.gauss(680, 80)
    elif pop >= 2000:
        base = random.gauss(600, 90)
    elif pop >= 800:
        base = random.gauss(550, 100)
    else:
        base = random.gauss(480, 110)
    return max(300, min(850, int(base)))


# === CUSTOMERS ===
print("Generating customers...")
city_list = []
for city, count in CITIES.items():
    city_list.extend([city] * count)
random.shuffle(city_list)
while len(city_list) < 50000:
    city_list.append(random.choice(list(CITIES.keys())))

signup_month_weights = [15, 8, 9, 8, 7, 6, 7, 8, 14, 9, 5, 4]

customers = []
with open(f"{DATA_DIR}/customers.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["customer_id", "first_name", "last_name", "email", "city", "credit_score", "created_at"])
    for i in range(50000):
        cid = rand_id("CUS")
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        email = f"{fn.lower()}.{ln.lower()}{random.randint(1, 999)}@example.com"
        city = city_list[i]
        score = credit_score_for_city(city)
        m = random.choices(range(1, 13), weights=signup_month_weights, k=1)[0]
        year = random.randint(2019, 2025)
        day = random.randint(1, 28)
        created = datetime(year, m, day)
        if created > END:
            created = rand_date(START, END)
        w.writerow([cid, fn, ln, email, city, score, created.strftime("%d-%m-%Y")])
        customers.append({"id": cid, "city": city, "score": score, "created": created})

print(f"  customers: {len(customers)}")


# === ACCOUNTS ===
# Seasonal: Jan & Sep high, summer low
# Types: Savings 45%, Checking 35%, Business 20%
print("Generating accounts...")
acct_month_weights = [18, 9, 10, 8, 7, 5, 6, 7, 16, 9, 3, 2]
acct_types = ["Savings"] * 45 + ["Checking"] * 35 + ["Business"] * 20

accounts = []
with open(f"{DATA_DIR}/accounts.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["account_id", "customer_id", "account_type", "balance_usd", "open_date", "account_status", "closed_date", "last_activity_date"])
    for i in range(75000):
        cust = random.choice(customers)
        aid = rand_id("ACC")
        atype = random.choice(acct_types)

        if atype == "Savings":
            bal = round(random.gauss(40000, 30000), 2)
        elif atype == "Checking":
            bal = round(random.gauss(15000, 10000), 2)
        else:
            bal = round(random.gauss(80000, 50000), 2)
        bal = max(100, bal)

        gap_days = random.choices(
            [0, 1, 3, 7, 14, 30, 60, 90, 180, 365],
            weights=[15, 10, 8, 12, 10, 15, 10, 8, 7, 5],
            k=1,
        )[0]
        open_date = cust["created"] + timedelta(days=gap_days + random.randint(0, 30))
        if open_date > END:
            open_date = rand_date(cust["created"], END)

        if cust["score"] < 450:
            status = random.choices(["Active", "Closed", "Dormant"], weights=[30, 40, 30], k=1)[0]
        elif cust["score"] < 600:
            status = random.choices(["Active", "Closed", "Dormant"], weights=[55, 20, 25], k=1)[0]
        else:
            status = random.choices(["Active", "Closed", "Dormant"], weights=[80, 8, 12], k=1)[0]

        closed_date = ""
        if status == "Closed":
            cd = open_date + timedelta(days=random.randint(30, 800))
            if cd <= END:
                closed_date = cd.strftime("%d-%m-%Y")
            else:
                status = "Active"

        if status == "Active":
            last_act = rand_date(datetime(2025, 6, 1), END)
        elif status == "Dormant":
            last_act = rand_date(datetime(2023, 1, 1), datetime(2024, 12, 31))
        else:
            last_act = datetime.strptime(closed_date, "%d-%m-%Y") if closed_date else open_date

        w.writerow([aid, cust["id"], atype, bal, open_date.strftime("%d-%m-%Y"), status,
                    closed_date, last_act.strftime("%d-%m-%Y")])
        accounts.append({"id": aid, "cust_id": cust["id"], "open_date": open_date})

print(f"  accounts: {len(accounts)}")


# === CARDS ===
print("Generating cards...")
with open(f"{DATA_DIR}/cards.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["card_id", "account_id", "card_type", "expiration_date"])
    for i in range(100000):
        acct = random.choice(accounts)
        cid = rand_id("CRD")
        ctype = random.choices(["Credit", "Debit"], weights=[55, 45], k=1)[0]
        exp = acct["open_date"] + timedelta(days=random.randint(365, 2500))
        w.writerow([cid, acct["id"], ctype, exp.strftime("%d-%m-%Y")])

print("  cards: 100000")


# === LOANS ===
# Seasonal: Q4 high (holiday spending), Jan high (post-holiday)
# Credit score affects amount and interest rate
print("Generating loans...")
loan_month_weights = [14, 8, 7, 6, 5, 5, 6, 7, 8, 13, 12, 9]

with open(f"{DATA_DIR}/loans.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["loan_id", "customer_id", "loan_amount", "interest_rate", "start_date"])
    for i in range(30000):
        cust = random.choice(customers)
        lid = rand_id("LON")

        if cust["score"] >= 700:
            amount = round(random.gauss(50000, 20000), 2)
            rate = round(random.gauss(4.5, 1.5), 2)
        elif cust["score"] >= 500:
            amount = round(random.gauss(25000, 15000), 2)
            rate = round(random.gauss(8.5, 2.5), 2)
        else:
            amount = round(random.gauss(8000, 5000), 2)
            rate = round(random.gauss(13.5, 3), 2)
        amount = max(500, amount)
        rate = max(1.0, min(20.0, rate))

        m = random.choices(range(1, 13), weights=loan_month_weights, k=1)[0]
        year = random.randint(2019, 2025)
        day = random.randint(1, 28)
        sd = datetime(year, m, day)
        if sd > END:
            sd = rand_date(START, END)
        w.writerow([lid, cust["id"], amount, rate, sd.strftime("%d-%m-%Y")])

print("  loans: 30000")


# === BRANCHES ===
print("Generating branches...")
with open(f"{DATA_DIR}/branches.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["branch_id", "branch_name", "manager_name"])
    for city in list(CITIES.keys())[:20]:
        bid = rand_id("BRN")
        mgr = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        w.writerow([bid, f"{city} Branch", mgr])

print("  branches: 20")


# === MERCHANTS ===
print("Generating merchants...")
biz_names = ["Tech Solutions", "Food Express", "Auto Services", "Health Plus", "Fashion Hub",
             "Home Depot", "Travel World", "Book Corner", "Sports Arena", "Music House"]
with open(f"{DATA_DIR}/merchants.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["merchant_id", "merchant_name", "city"])
    for i in range(500):
        mid = rand_id("MER")
        name = f"{random.choice(LAST_NAMES)} {random.choice(biz_names)}"
        city = random.choice(list(CITIES.keys()))
        w.writerow([mid, name, city])

print("  merchants: 500")

print("\nDone! All datasets regenerated with realistic variations.")
