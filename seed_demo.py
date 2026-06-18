"""
seed_demo.py — BSPHCL Demo Dataset
===================================
Populates the database with realistic Bihar electricity complaint data.
Run once on the deployed instance:  python seed_demo.py

Creates:
  - 1 super admin (existing)
  - 4 staff members  (operator, complaint_officer x2, field_staff)
  - 30 consumer accounts spread across Bihar districts
  - 160 complaints over the past 6 months with realistic timelines
  - Complaint logs / activity timeline for each complaint
  - Staff replies on resolved complaints
  - Satisfaction ratings on closed complaints
  - Notifications for consumers
"""

import random
from datetime import datetime, timedelta
from app import app
from extensions import db
from models import (
    User, Complaint, ComplaintLog, Reply,
    Notification, SatisfactionRating
)
from utils import generate_consumer_number

random.seed(42)

# ── Bihar districts ────────────────────────────────────────────────────────────
DISTRICTS = [
    "Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Purnia",
    "Darbhanga", "Ara", "Begusarai", "Katihar", "Munger",
    "Chapra", "Hajipur", "Sasaram", "Bettiah", "Siwan",
    "Motihari", "Samastipur", "Nawada", "Jehanabad", "Aurangabad",
]

# ── Indian names ───────────────────────────────────────────────────────────────
FIRST_NAMES = [
    "Rajesh", "Sunita", "Amit", "Priya", "Suresh", "Kavita", "Vijay", "Anita",
    "Rajan", "Meena", "Deepak", "Suman", "Ashok", "Rekha", "Manoj", "Geeta",
    "Santosh", "Usha", "Ramesh", "Shanti", "Dinesh", "Pushpa", "Arun", "Lalita",
    "Rohit", "Nirmala", "Vikas", "Seema", "Pawan", "Asha", "Naresh", "Savita",
    "Sanjay", "Radha", "Ajay", "Kiran", "Ravi", "Mamta", "Binod", "Sarita",
]
LAST_NAMES = [
    "Kumar", "Singh", "Prasad", "Sharma", "Yadav", "Verma", "Gupta", "Mishra",
    "Tiwari", "Pandey", "Sinha", "Jha", "Thakur", "Chaudhary", "Shah",
]

# ── Complaint templates by category ───────────────────────────────────────────
COMPLAINT_TEMPLATES = {
    "power_outage": [
        {
            "subjects": [
                "No electricity supply for past {days} days in {area}",
                "Complete power outage in our locality since {date}",
                "Frequent power cuts affecting daily life in {area}",
                "Unscheduled load shedding without prior notice",
                "Power supply disrupted for {days} days — urgent restoration needed",
            ],
            "descriptions": [
                "Our area {area}, {district} has been without electricity supply for the past {days} days. "
                "There has been no prior intimation from BSPHCL regarding any scheduled maintenance. "
                "The outage is affecting {households} households including residential and commercial establishments. "
                "Multiple complaints have been lodged at the local subdivision office but no action has been taken. "
                "Request urgent restoration of power supply.",

                "I wish to bring to your kind attention that our colony in {area}, {district} is experiencing "
                "continuous power failure since {date}. The local lineman visited once but could not resolve the issue. "
                "The transformer in our area seems to have developed a fault. Elderly residents and patients are "
                "severely affected. Request immediate inspection and restoration of supply.",

                "There has been no electricity in our area for {days} consecutive days due to an unresolved fault "
                "in the 11KV feeder serving {area}, {district}. The SDO office has not responded to our requests. "
                "We are forced to use generators at great expense. Kindly expedite restoration.",
            ],
            "priority_weights": {"urgent": 0.35, "high": 0.40, "medium": 0.20, "low": 0.05},
        },
    ],
    "billing": [
        {
            "subjects": [
                "Incorrect electricity bill for the month of {month}",
                "Bill amount inflated — showing {amount} units against actual consumption",
                "Billing dispute: meter reading not taken, estimated bill issued",
                "Duplicate bill received for same period",
                "Zero consumption bill showing high arrears — request correction",
            ],
            "descriptions": [
                "I have received my electricity bill for {month} showing a consumption of {amount} units "
                "which is grossly incorrect. My average monthly consumption is around 80-100 units. "
                "The bill has been generated on estimated basis without actual meter reading. "
                "Consumer number: {consumer_no}. Kindly send a meter reader to verify and issue a corrected bill.",

                "My bill for the period {month} shows arrears of Rs. {amount}/- which I dispute completely. "
                "All my previous bills have been paid promptly as evident from my payment history. "
                "I suspect the readings have been entered incorrectly. Request an immediate audit of my "
                "account and correction of the outstanding amount.",

                "Despite submitting meter reading through the mobile app, my bill for {month} has been "
                "generated on estimated basis showing {amount} units. The estimated reading is 3x my "
                "normal consumption. My consumer number is {consumer_no}. Kindly correct the bill "
                "and ensure actual reading is taken going forward.",
            ],
            "priority_weights": {"urgent": 0.05, "high": 0.25, "medium": 0.55, "low": 0.15},
        },
    ],
    "meter_fault": [
        {
            "subjects": [
                "Electricity meter not working / stopped recording units",
                "Meter display showing error code — possible tampering",
                "Meter giving shocks — safety hazard",
                "New digital meter installed but not activated",
                "Meter running fast — recording excess units",
            ],
            "descriptions": [
                "My electricity meter (Consumer No: {consumer_no}) has stopped working. The display shows "
                "no reading and has been in this condition for the past {days} days. Despite lodging a "
                "complaint at the subdivision office, the meter has not been replaced. I am concerned "
                "that I may be billed incorrectly during this period. Kindly depute a technician to "
                "inspect and replace the faulty meter at the earliest.",

                "The electricity meter at my premises is running unusually fast. My previous average "
                "consumption was around 90 units per month but the meter is now recording over 250 units "
                "monthly without any change in my appliance usage. I suspect the meter has developed a "
                "technical fault. Request inspection and testing of the meter by BSPHCL officials.",

                "The meter at my premises (Consumer No: {consumer_no}) is showing an error code 'E6' "
                "on the digital display. The local lineman said it requires replacement but it has been "
                "{days} days and no action has been taken. Meanwhile I am receiving estimated bills. "
                "Request urgent replacement of faulty meter.",
            ],
            "priority_weights": {"urgent": 0.10, "high": 0.35, "medium": 0.45, "low": 0.10},
        },
    ],
    "new_connection": [
        {
            "subjects": [
                "New domestic electricity connection — application pending since {date}",
                "Commercial connection application not processed for {days} days",
                "Agricultural pump connection — status enquiry",
                "Temporary connection for construction not issued despite approval",
                "Load enhancement application not resolved",
            ],
            "descriptions": [
                "I applied for a new domestic electricity connection on {date} with application number "
                "vide subdivision office, {district}. Despite completing all required documentation "
                "including payment of security deposit, the connection has not been provided even after "
                "{days} days. Multiple visits to the SDO office have not yielded any result. "
                "Kindly expedite the connection.",

                "My application for enhancement of sanctioned load from 2KW to 5KW submitted on {date} "
                "is still pending. All documents including load sanction fee have been submitted. "
                "The delay is causing operational problems for my small business. "
                "Consumer No: {consumer_no}. Request early disposal of my application.",
            ],
            "priority_weights": {"urgent": 0.05, "high": 0.20, "medium": 0.50, "low": 0.25},
        },
    ],
    "low_voltage": [
        {
            "subjects": [
                "Extremely low voltage in {area} — damaging appliances",
                "Voltage fluctuation causing frequent equipment failures",
                "Low voltage issue persisting for over {days} days in our area",
                "Voltage dipping to 160V during peak hours in {area}",
            ],
            "descriptions": [
                "Our area {area}, {district} has been facing severe low voltage problem for the past "
                "{days} days. The voltage frequently dips to 160-170V during peak hours (6 PM to 10 PM), "
                "causing damage to electrical appliances including refrigerators, water pumps, and fans. "
                "Multiple residents have already suffered appliance damage worth thousands of rupees. "
                "Kindly inspect the distribution transformer and feeder cables and take corrective action.",

                "I am experiencing voltage fluctuation at my premises (Consumer No: {consumer_no}). "
                "The voltage varies between 150V and 260V throughout the day. This has already damaged "
                "my washing machine and LED television. The local lineman says the issue is with the "
                "Distribution Transformer but no corrective action has been taken. Request urgent "
                "inspection and repair.",
            ],
            "priority_weights": {"urgent": 0.15, "high": 0.45, "medium": 0.35, "low": 0.05},
        },
    ],
    "transformer": [
        {
            "subjects": [
                "Distribution transformer burnt — locality without power for {days} days",
                "Transformer oil leakage near residential area — safety concern",
                "Transformer overloaded — tripping frequently",
                "Request for new transformer — existing one insufficient for locality",
                "Transformer making loud humming noise — inspection required",
            ],
            "descriptions": [
                "The 100 KVA distribution transformer serving our colony in {area}, {district} was burnt "
                "on {date} due to overloading. Since then, approximately {households} households are "
                "without electricity supply. The subdivision office has been informed but the transformer "
                "has not been replaced despite {days} days. This is causing immense hardship to residents. "
                "Kindly arrange urgent replacement.",

                "The transformer located near {area}, {district} has been tripping repeatedly every day. "
                "It trips 4-5 times daily, each time causing a power outage of 1-2 hours. The lineman "
                "resets it manually but does not address the root cause. The transformer appears to be "
                "overloaded as new connections have been added without capacity augmentation. "
                "Request permanent resolution.",
            ],
            "priority_weights": {"urgent": 0.30, "high": 0.45, "medium": 0.20, "low": 0.05},
        },
    ],
    "streetlight": [
        {
            "subjects": [
                "Street lights not working in {area} for past {days} days",
                "All street lights in our lane defunct — safety risk at night",
                "Street light pole broken — lying on road, dangerous condition",
                "Request for new street lights in newly developed colony",
            ],
            "descriptions": [
                "The street lights in {area}, {district} have been non-functional for the past {days} days. "
                "The area becomes very dark at night creating safety and security concerns for residents, "
                "especially women and children. The local body has requested BSPHCL to repair the lights "
                "but no action has been taken. Kindly depute a lineman to repair/replace the faulty "
                "street lights at the earliest.",

                "Almost all street lights in our locality {area} are not working. The issue started after "
                "a storm {days} days ago when several poles and lights were damaged. The area is a "
                "residential colony with elderly residents who find it difficult to move at night. "
                "Request urgent repair of the street lighting system.",
            ],
            "priority_weights": {"urgent": 0.05, "high": 0.20, "medium": 0.45, "low": 0.30},
        },
    ],
    "safety": [
        {
            "subjects": [
                "Loose live wire hanging in public area — immediate attention required",
                "Electric pole leaning dangerously close to road",
                "Overhead cables sagging too low — touching trees and rooftops",
                "Sparking from distribution box near school",
                "Electric shock from street light pole — urgent action needed",
            ],
            "descriptions": [
                "A live electric wire has snapped and is hanging loose near {area}, {district}. "
                "It is touching the ground at several points and poses an extreme electrocution risk "
                "to pedestrians, especially children. Despite calling the emergency helpline {days} "
                "hours ago, no team has arrived. This is a LIFE THREATENING situation requiring "
                "IMMEDIATE attention. Kindly send a team urgently.",

                "The overhead 11KV line passing through {area} is sagging dangerously low. "
                "It is touching tree branches and in one location is only about 10 feet above the "
                "road surface. Heavy vehicles passing through could make contact with the wire. "
                "Kindly inspect and rectify this dangerous condition immediately before any accident occurs.",
            ],
            "priority_weights": {"urgent": 0.60, "high": 0.35, "medium": 0.05, "low": 0.00},
        },
    ],
    "service_request": [
        {
            "subjects": [
                "Request for shifting of electricity meter to new location",
                "Name transfer on electricity account after property purchase",
                "Request for duplicate bill for past months",
                "Disconnection notice received — payment already made",
                "Connection wrongly disconnected — request immediate reconnection",
            ],
            "descriptions": [
                "I have recently purchased a property in {area}, {district} and wish to transfer the "
                "electricity connection (Consumer No: {consumer_no}) to my name. All property documents "
                "including sale deed and NOC from previous owner are available. Kindly guide on the "
                "process and initiate the name transfer at the earliest.",

                "My electricity connection (Consumer No: {consumer_no}) was disconnected on {date} "
                "citing non-payment. However, I had paid the outstanding bill amount of Rs. {amount}/- "
                "through the BSPHCL online portal on {date2}. I am attaching the payment receipt. "
                "Kindly restore the connection immediately as there is a sick patient at home.",
            ],
            "priority_weights": {"urgent": 0.10, "high": 0.20, "medium": 0.50, "low": 0.20},
        },
    ],
    "other": [
        {
            "subjects": [
                "Complaint against BSPHCL employee for demanding bribe",
                "Wrong name on electricity bill despite correction request",
                "Request for energy audit of my premises",
                "BSPHCL app not working — unable to pay bill online",
            ],
            "descriptions": [
                "I wish to register a complaint against the lineman of {area} subdivision who visited "
                "my premises on {date} for a meter check. He demanded an unofficial payment of Rs. {amount}/- "
                "to clear my application. When I refused, he threatened to disconnect my supply. "
                "I am filing this complaint under the grievance redressal mechanism. "
                "Kindly investigate and take strict action.",

                "Despite submitting a written application on {date} for correction of name on my "
                "electricity bill (Consumer No: {consumer_no}), my name continues to appear incorrectly. "
                "This is causing issues in loan applications and government document submissions. "
                "Kindly make the correction at the earliest.",
            ],
            "priority_weights": {"urgent": 0.05, "high": 0.15, "medium": 0.50, "low": 0.30},
        },
    ],
}

STAFF_REPLIES = {
    "under_review": [
        "Your complaint has been received and is under review by our team. We will assign a field officer shortly.",
        "We have noted your complaint. Our technical team is assessing the issue. You will be updated soon.",
        "Complaint registered and being reviewed. Expected resolution within {eta} working days.",
    ],
    "in_progress": [
        "A field team has been dispatched to your location. They will inspect and resolve the issue.",
        "Our lineman {staff_name} has been assigned to address your complaint. He will visit on priority.",
        "Work order has been issued. Repair team is scheduled to visit {area} tomorrow. We regret the inconvenience.",
        "Your complaint has been forwarded to the {district} subdivision office for urgent action.",
    ],
    "resolved": [
        "We are pleased to inform you that your complaint has been resolved. The {issue} has been rectified by our team. Please verify and let us know if the issue persists.",
        "The matter reported by you has been attended to. Our field team has completed the necessary repairs. Please rate your experience.",
        "Your complaint stands resolved. The {issue} in your area has been fixed. If you face any further inconvenience, please register a fresh complaint.",
    ],
}

AREAS = [
    "Rajendra Nagar", "Boring Road Colony", "Ashok Rajpath", "Kankarbagh",
    "Patliputra Colony", "Shastri Nagar", "Punaichak", "Anisabad",
    "Phulwari Sharif", "Danapur", "Khagaul", "Fatuha", "Barh",
    "Punpun", "Masaurhi", "Bakhtiyarpur", "Mokama", "Bihta",
    "Maner", "Naubatpur", "Gandhi Maidan Area", "Station Road",
    "Medical College Road", "Veterinary College Road", "BIT Mesra Road",
    "Bypass Road Colony", "Saguna More", "Rukanpura", "Mithapur",
    "New Bypass Colony", "Mithapur Nagar", "Lohia Nagar",
]

def weighted_choice(weight_dict):
    keys = list(weight_dict.keys())
    weights = list(weight_dict.values())
    return random.choices(keys, weights=weights, k=1)[0]

def random_date(days_back_start, days_back_end):
    offset = random.randint(days_back_end, days_back_start)
    return datetime.utcnow() - timedelta(days=offset)

def make_complaint_id(seq):
    return f"BSP{datetime.utcnow().year}{seq:05d}"

def fill_template(text, **kwargs):
    months = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]
    defaults = {
        "days": random.randint(2, 15),
        "date": (datetime.utcnow() - timedelta(days=random.randint(5, 30))).strftime("%d/%m/%Y"),
        "date2": (datetime.utcnow() - timedelta(days=random.randint(1, 5))).strftime("%d/%m/%Y"),
        "month": random.choice(months),
        "amount": random.choice([320, 450, 680, 1200, 1850, 2400, 3100, 4500, 6800]),
        "households": random.randint(20, 200),
        "area": random.choice(AREAS),
        "consumer_no": f"BR{random.randint(100000, 999999)}",
        "staff_name": random.choice(FIRST_NAMES),
        "issue": random.choice(["transformer fault", "feeder tripping", "meter fault", "wiring issue", "billing error"]),
        "eta": random.randint(2, 5),
    }
    defaults.update(kwargs)
    try:
        return text.format(**defaults)
    except Exception:
        return text


def seed():
    print("🌱 Starting BSPHCL demo data seeding...")

    # ── 1. Staff members ───────────────────────────────────────────────────────
    staff_data = [
        dict(name="Rajiv Ranjan", email="rajiv.ranjan@bsphcl.gov.in",
             mobile="9431100001", role="operator", department="Central Operations"),
        dict(name="Meena Kumari", email="meena.kumari@bsphcl.gov.in",
             mobile="9431100002", role="complaint_officer", department="Consumer Grievance Cell"),
        dict(name="Sudhir Prasad", email="sudhir.prasad@bsphcl.gov.in",
             mobile="9431100003", role="complaint_officer", department="Technical Division"),
        dict(name="Arvind Singh", email="arvind.singh@bsphcl.gov.in",
             mobile="9431100004", role="field_staff", department="Field Operations"),
    ]
    staff_objs = []
    for s in staff_data:
        existing = User.query.filter_by(email=s["email"]).first()
        if not existing:
            u = User(
                name=s["name"], email=s["email"], mobile=s["mobile"],
                role=s["role"], department=s["department"],
                is_admin=True, district="Patna", state="Bihar",
                consumer_number=generate_consumer_number()
            )
            u.set_password("Staff@2024")
            db.session.add(u)
            db.session.flush()
            staff_objs.append(u)
            print(f"  ✅ Staff: {s['name']} ({s['role']})")
        else:
            staff_objs.append(existing)
    db.session.commit()

    # ── 2. Consumer accounts ──────────────────────────────────────────────────
    consumers = []
    mobile_used = set(m[0] for m in db.session.query(User.mobile).all())
    email_used = set(e[0] for e in db.session.query(User.email).all())

    for i in range(30):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        district = random.choice(DISTRICTS)
        base_mobile = 7000000000 + i * 13 + random.randint(1, 9)
        mobile = str(base_mobile)
        while mobile in mobile_used:
            base_mobile += 1
            mobile = str(base_mobile)
        mobile_used.add(mobile)

        email_base = f"{first.lower()}.{last.lower()}{i}"
        email = f"{email_base}@gmail.com"
        while email in email_used:
            email = f"{email_base}{random.randint(1,99)}@gmail.com"
        email_used.add(email)

        created_at = random_date(180, 30)
        u = User(
            name=name, email=email, mobile=mobile,
            role="consumer", district=district, state="Bihar",
            address=f"{random.choice(AREAS)}, {district}, Bihar",
            consumer_number=generate_consumer_number(),
            created_at=created_at,
        )
        u.set_password("Consumer@2024")
        db.session.add(u)
        consumers.append(u)

    db.session.commit()
    print(f"  ✅ Created {len(consumers)} consumer accounts")

    # ── 3. Complaints ─────────────────────────────────────────────────────────
    categories = list(COMPLAINT_TEMPLATES.keys())
    # Weight categories to match real-world distribution
    cat_weights = {
        "power_outage": 0.22, "billing": 0.20, "meter_fault": 0.14,
        "transformer": 0.12, "low_voltage": 0.10, "new_connection": 0.08,
        "streetlight": 0.06, "safety": 0.04, "service_request": 0.02, "other": 0.02,
    }
    # Status distribution — makes dashboard look realistic
    status_pool = (
        ["pending"] * 25 +
        ["under_review"] * 20 +
        ["in_progress"] * 20 +
        ["resolved"] * 45 +
        ["closed"] * 30 +
        ["rejected"] * 8 +
        ["escalated"] * 7
    )

    seq = Complaint.query.count() + 1
    complaint_objs = []

    for _ in range(160):
        consumer = random.choice(consumers)
        category = weighted_choice(cat_weights)
        tmpl = random.choice(COMPLAINT_TEMPLATES[category])

        subject_tmpl = random.choice(tmpl["subjects"])
        desc_tmpl = random.choice(tmpl["descriptions"])
        priority = weighted_choice(tmpl["priority_weights"])
        area = random.choice(AREAS)
        district = consumer.district

        subject = fill_template(subject_tmpl, area=area, district=district)
        description = fill_template(desc_tmpl, area=area, district=district,
                                    consumer_no=consumer.consumer_number)

        created_at = random_date(170, 1)
        status = random.choice(status_pool)

        # Resolved/closed must be older
        if status in ("resolved", "closed"):
            created_at = random_date(170, 20)

        priority_eta = {"urgent": 1, "high": 2, "medium": 4, "low": 7}
        eta = created_at + timedelta(days=priority_eta[priority])
        resolved_at = None
        if status in ("resolved", "closed"):
            resolved_at = created_at + timedelta(days=random.randint(1, priority_eta[priority] + 3))

        assignee = random.choice(staff_objs) if status not in ("pending",) else None

        c = Complaint(
            complaint_id=make_complaint_id(seq),
            user_id=consumer.id,
            subject=subject[:200],
            description=description,
            category=category,
            sub_category=None,
            priority=priority,
            status=status,
            district=district,
            address=f"{area}, {district}, Bihar",
            consumer_number=consumer.consumer_number,
            meter_number=f"MTR{random.randint(100000,999999)}",
            assigned_to=assignee.id if assignee else None,
            department=assignee.department if assignee else None,
            expected_resolution_date=eta,
            created_at=created_at,
            updated_at=created_at + timedelta(hours=random.randint(1, 48)),
            resolved_at=resolved_at,
            first_review_at=created_at + timedelta(hours=random.randint(2, 12)) if status != "pending" else None,
            resolution_summary=(
                f"Issue has been resolved by field team. {category.replace('_',' ').title()} "
                f"in {area}, {district} has been rectified."
                if status in ("resolved", "closed") else None
            ),
        )
        db.session.add(c)
        db.session.flush()
        complaint_objs.append((c, consumer, assignee))
        seq += 1

    db.session.commit()
    print(f"  ✅ Created {len(complaint_objs)} complaints")

    # ── 4. Complaint logs (activity timeline) ─────────────────────────────────
    log_count = 0
    for c, consumer, assignee in complaint_objs:
        # Filed log
        db.session.add(ComplaintLog(
            complaint_id=c.id, user_id=consumer.id,
            action="complaint_filed",
            message=f"Complaint {c.complaint_id} filed by consumer.",
            created_at=c.created_at,
        ))
        log_count += 1

        if c.status != "pending":
            db.session.add(ComplaintLog(
                complaint_id=c.id, user_id=assignee.id if assignee else consumer.id,
                action="status_changed",
                message=f"Complaint taken up for review.",
                created_at=c.created_at + timedelta(hours=random.randint(2, 10)),
            ))
            log_count += 1

        if c.status in ("in_progress", "resolved", "closed", "escalated"):
            staff = assignee or random.choice(staff_objs)
            db.session.add(ComplaintLog(
                complaint_id=c.id, user_id=staff.id,
                action="assigned",
                message=f"Complaint assigned to {staff.name} ({staff.department}).",
                created_at=c.created_at + timedelta(hours=random.randint(10, 24)),
            ))
            log_count += 1

        if c.status in ("resolved", "closed"):
            staff = assignee or random.choice(staff_objs)
            db.session.add(ComplaintLog(
                complaint_id=c.id, user_id=staff.id,
                action="resolved",
                message=c.resolution_summary or "Complaint resolved by field team.",
                created_at=c.resolved_at or (c.created_at + timedelta(days=2)),
            ))
            log_count += 1

        if c.status == "closed":
            db.session.add(ComplaintLog(
                complaint_id=c.id, user_id=consumer.id,
                action="closed",
                message="Complaint closed by consumer after resolution.",
                created_at=(c.resolved_at or c.created_at) + timedelta(days=random.randint(1, 3)),
            ))
            log_count += 1

    db.session.commit()
    print(f"  ✅ Created {log_count} activity log entries")

    # ── 5. Staff replies ──────────────────────────────────────────────────────
    reply_count = 0
    for c, consumer, assignee in complaint_objs:
        staff = assignee or random.choice(staff_objs)
        area = c.address.split(",")[0] if c.address else "your area"

        if c.status == "under_review":
            msg = fill_template(random.choice(STAFF_REPLIES["under_review"]), area=area)
            db.session.add(Reply(
                complaint_id=c.id, user_id=staff.id,
                message=msg, is_admin_reply=True,
                created_at=c.created_at + timedelta(hours=random.randint(4, 14)),
            ))
            reply_count += 1

        elif c.status in ("in_progress", "escalated"):
            msg = fill_template(random.choice(STAFF_REPLIES["in_progress"]),
                                area=area, staff_name=staff.name, district=c.district or "")
            db.session.add(Reply(
                complaint_id=c.id, user_id=staff.id,
                message=msg, is_admin_reply=True,
                created_at=c.created_at + timedelta(hours=random.randint(8, 24)),
            ))
            reply_count += 1

        elif c.status in ("resolved", "closed"):
            # First a progress update
            msg1 = fill_template(random.choice(STAFF_REPLIES["in_progress"]),
                                 area=area, staff_name=staff.name, district=c.district or "")
            db.session.add(Reply(
                complaint_id=c.id, user_id=staff.id,
                message=msg1, is_admin_reply=True,
                created_at=c.created_at + timedelta(hours=random.randint(8, 18)),
            ))
            # Then resolution
            issue_map = {
                "power_outage": "power supply", "billing": "billing error",
                "meter_fault": "meter fault", "transformer": "transformer fault",
                "low_voltage": "low voltage", "new_connection": "connection",
                "streetlight": "street light", "safety": "safety hazard",
                "service_request": "service request", "other": "reported issue",
            }
            msg2 = fill_template(random.choice(STAFF_REPLIES["resolved"]),
                                 issue=issue_map.get(c.category, "reported issue"))
            db.session.add(Reply(
                complaint_id=c.id, user_id=staff.id,
                message=msg2, is_admin_reply=True,
                created_at=(c.resolved_at or c.created_at + timedelta(days=2)),
            ))
            reply_count += 2

            # Consumer follow-up on ~30% closed
            if c.status == "closed" and random.random() < 0.30:
                consumer_msgs = [
                    "Thank you for resolving the issue. Power supply has been restored.",
                    "Issue has been resolved. Bill has been corrected. Thank you.",
                    "The lineman visited and fixed the problem. Satisfied with the resolution.",
                ]
                db.session.add(Reply(
                    complaint_id=c.id, user_id=consumer.id,
                    message=random.choice(consumer_msgs), is_admin_reply=False,
                    created_at=(c.resolved_at or c.created_at + timedelta(days=2)) + timedelta(hours=random.randint(2, 12)),
                ))
                reply_count += 1

    db.session.commit()
    print(f"  ✅ Created {reply_count} complaint replies")

    # ── 6. Satisfaction ratings ───────────────────────────────────────────────
    rating_count = 0
    closed_complaints = [(c, consumer) for c, consumer, _ in complaint_objs if c.status == "closed"]
    for c, consumer in random.sample(closed_complaints, min(len(closed_complaints), int(len(closed_complaints) * 0.65))):
        # Skew towards positive ratings (realistic for resolved complaints)
        rating_weights = [0.05, 0.08, 0.15, 0.35, 0.37]
        rating_val = random.choices([1, 2, 3, 4, 5], weights=rating_weights)[0]
        feedbacks = {
            5: ["Excellent service. Issue resolved quickly.", "Very satisfied. Lineman was professional.",
                "Quick response and resolution. Thank you BSPHCL."],
            4: ["Good service. Took a bit long but issue resolved.", "Satisfied with the outcome.",
                "Problem fixed. Could have been faster."],
            3: ["Average experience. Issue resolved but took too long.", "Okay response. Expected faster action."],
            2: ["Took too many days but finally resolved.", "Not happy with the delay in resolution."],
            1: ["Very poor service. Too many follow-ups needed.", "Completely unsatisfied with the response time."],
        }
        if not SatisfactionRating.query.filter_by(complaint_id=c.id).first():
            db.session.add(SatisfactionRating(
                complaint_id=c.id, user_id=consumer.id,
                rating=rating_val,
                feedback=random.choice(feedbacks[rating_val]),
                created_at=(c.resolved_at or c.created_at + timedelta(days=3)) + timedelta(hours=random.randint(1, 24)),
            ))
            rating_count += 1

    db.session.commit()
    print(f"  ✅ Created {rating_count} satisfaction ratings")

    # ── 7. Notifications ──────────────────────────────────────────────────────
    notif_count = 0
    for c, consumer, _ in complaint_objs:
        if c.status != "pending":
            db.session.add(Notification(
                user_id=consumer.id,
                title=f"Complaint {c.complaint_id} — Status Update",
                message=f"Your complaint regarding '{c.subject[:60]}' has been updated to: {c.get_status_label()}.",
                is_read=random.random() > 0.4,
                notif_type="info",
                related_complaint=c.complaint_id,
                created_at=c.created_at + timedelta(hours=random.randint(4, 24)),
            ))
            notif_count += 1

        if c.status in ("resolved", "closed"):
            db.session.add(Notification(
                user_id=consumer.id,
                title=f"Complaint {c.complaint_id} — Resolved",
                message=f"Your complaint has been resolved by our field team. Please rate your experience.",
                is_read=random.random() > 0.3,
                notif_type="success",
                related_complaint=c.complaint_id,
                created_at=(c.resolved_at or c.created_at + timedelta(days=2)),
            ))
            notif_count += 1

    db.session.commit()
    print(f"  ✅ Created {notif_count} notifications")

    # ── Summary ───────────────────────────────────────────────────────────────
    total_complaints = Complaint.query.count()
    status_summary = db.session.execute(
        db.text("SELECT status, COUNT(*) FROM complaints GROUP BY status ORDER BY COUNT(*) DESC")
    ).fetchall()

    print("\n" + "="*55)
    print("🎉 BSPHCL Demo Dataset Seeded Successfully!")
    print("="*55)
    print(f"  Staff accounts  : {len(staff_objs)}")
    print(f"  Consumer accounts: {len(consumers)}")
    print(f"  Total complaints : {total_complaints}")
    print(f"\n  Complaint status breakdown:")
    for status, count in status_summary:
        print(f"    {status:<20} {count}")
    print("\n  Login credentials:")
    print("  Admin    : admin@bsphcl.gov.in  / Admin@2024")
    print("  Staff    : rajiv.ranjan@bsphcl.gov.in / Staff@2024")
    print("  Consumer : (any from seeded list) / Consumer@2024")
    print("="*55)


if __name__ == "__main__":
    with app.app_context():
        seed()
