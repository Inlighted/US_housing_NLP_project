"""
generate_dataset.py
--------------------
Creates a synthetic US Housing dataset with columns:
id, name, address, location, area, price, tenure_of_stay

This is used ONLY to demonstrate evaluation metrics / exploratory
data analysis in the Streamlit app (Admin > Dataset Insights).
It has no bearing on the live MongoDB-backed complaint system.
"""

import csv
import random

random.seed(42)

FIRST_NAMES = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
               "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
               "Thomas", "Sarah", "Charles", "Karen", "Daniel", "Nancy", "Matthew", "Lisa",
               "Anthony", "Betty", "Mark", "Margaret", "Donald", "Sandra"]

LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
              "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
              "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White"]

STREET_NAMES = ["Maple St", "Oak Ave", "Pine Rd", "Cedar Blvd", "Elm St", "Washington Ave",
                "Lincoln Dr", "Sunset Blvd", "Park Ave", "Main St", "Broadway", "Highland Dr",
                "River Rd", "Lake St", "Church St", "5th Ave", "2nd St", "Hillcrest Dr"]

CITIES = [
    ("Austin", "TX"), ("Dallas", "TX"), ("Houston", "TX"),
    ("Los Angeles", "CA"), ("San Francisco", "CA"), ("San Diego", "CA"),
    ("New York", "NY"), ("Buffalo", "NY"),
    ("Chicago", "IL"), ("Springfield", "IL"),
    ("Miami", "FL"), ("Orlando", "FL"), ("Tampa", "FL"),
    ("Seattle", "WA"), ("Spokane", "WA"),
    ("Denver", "CO"), ("Boulder", "CO"),
    ("Atlanta", "GA"), ("Savannah", "GA"),
    ("Phoenix", "AZ"), ("Tucson", "AZ"),
    ("Boston", "MA"), ("Portland", "OR"),
    ("Nashville", "TN"), ("Charlotte", "NC"),
    ("Columbus", "OH"), ("Detroit", "MI"),
    ("Minneapolis", "MN"), ("Las Vegas", "NV"), ("Salt Lake City", "UT"),
]

def generate_row(i):
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    name = f"{first} {last}"

    street_num = random.randint(100, 9999)
    street = random.choice(STREET_NAMES)
    unit = random.choice(["", f" Apt {random.randint(1,40)}", f" Unit {random.randint(1,20)}"])
    address = f"{street_num} {street}{unit}"

    city, state = random.choice(CITIES)
    location = f"{city}, {state}"

    area = random.randint(450, 3200)  # sq ft

    # price roughly correlated with area + noise
    base_price_per_sqft = random.uniform(0.9, 3.2)
    price = round(area * base_price_per_sqft * 100 + random.uniform(-5000, 15000), 2)
    price = max(price, 500)

    tenure_of_stay = random.choice([
        "1 month", "3 months", "6 months", "1 year", "2 years",
        "3 years", "5 years", "Month-to-month", "Lease (12 months)"
    ])

    is_vacant = random.choice([True, False, False])  # ~1/3 vacant
    priority = random.choices(
        ["Low", "Medium", "High", "Featured"], weights=[40, 35, 20, 5]
    )[0]
    image_url = f"https://picsum.photos/seed/house{i}/400/300"

    return {
        "id": i,
        "name": name,
        "address": address,
        "location": location,
        "area": area,
        "price": price,
        "tenure_of_stay": tenure_of_stay,
        "is_vacant": is_vacant,
        "priority": priority,
        "image_url": image_url,
    }


def main(n=500, out_path="us_housing_dataset.csv"):
    rows = [generate_row(i) for i in range(1, n + 1)]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {n} rows to {out_path}")


if __name__ == "__main__":
    main()
