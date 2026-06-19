"""
seed_demo.py  —  BSPHCL Demo Dataset
Run automatically from run.py on first deploy when DB is empty.
Populates: 4 staff, 30 consumers, 160 complaints, logs, replies, ratings, notifications.
"""

import random
from datetime import datetime, timedelta
from extensions import db
from models import (User, Complaint, ComplaintLog,
                    Reply, Notification, SatisfactionRating)
from utils import generate_consumer_number

random.seed(42)

# ── Bihar districts ────────────────────────────────────────────────────────────
DISTRICTS = [
    "Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Purnia",
    "Darbhanga", "Ara", "Begusarai", "Katihar", "Munger",
    "Chapra", "Hajipur", "Sasaram", "Bettiah", "Siwan",
    "Motihari", "Samastipur", "Nawada", "Jehanabad", "Aurangabad",
]

AREAS = [
    "Rajendra Nagar", "Boring Road Colony", "Ashok Rajpath", "Kankarbagh",
    "Patliputra Colony", "Shastri Nagar", "Punaichak", "Anisabad",
    "Phulwari Sharif", "Danapur", "Khagaul", "Fatuha", "Barh",
    "Punpun", "Masaurhi", "Bakhtiyarpur", "Mokama", "Bihta",
    "Maner", "Naubatpur", "Gandhi Maidan Area", "Station Road",
    "New Bypass Colony", "Lohia Nagar", "Mithapur Nagar",
]

FIRST_NAMES = [
    "Rajesh","Sunita","Amit","Priya","Suresh","Kavita","Vijay","Anita",
    "Rajan","Meena","Deepak","Suman","Ashok","Rekha","Manoj","Geeta",
    "Santosh","Usha","Ramesh","Shanti","Dinesh","Pushpa","Arun","Lalita",
    "Rohit","Nirmala","Vikas","Seema","Pawan","Asha","Naresh","Savita",
    "Sanjay","Radha","Ajay","Kiran","Ravi","Mamta","Binod","Sarita",
]
LAST_NAMES = [
    "Kumar","Singh","Prasad","Sharma","Yadav","Verma","Gupta","Mishra",
    "Tiwari","Pandey","Sinha","Jha","Thakur","Chaudhary","Shah",
]

# ── Complaint templates ────────────────────────────────────────────────────────
TEMPLATES = {
    "power_outage": {
        "subjects": [
            "No electricity supply for past {days} days in {area}",
            "Complete power outage in our locality since {date}",
            "Frequent power cuts affecting daily life in {area}",
            "Unscheduled load shedding without prior notice in {district}",
            "Power supply disrupted — urgent restoration needed",
        ],
        "descriptions": [
            "Our area {area}, {district} has been without electricity supply for the past {days} days. "
            "There has been no prior intimation from BSPHCL regarding any scheduled maintenance. "
            "The outage is affecting approximately {households} households. "
            "Multiple complaints have been lodged at the local subdivision office but no action has been taken. "
            "Request urgent restoration of power supply.",

            "I wish to bring to your kind attention that our colony in {area}, {district} is experiencing "
            "continuous power failure since {date}. The local lineman visited once but could not resolve the issue. "
            "The transformer in our area seems to have developed a fault. Elderly residents and patients are "
            "severely affected. Request immediate inspection and restoration of supply.",

            "There has been no electricity in our area for {days} consecutive days. "
            "The SDO office has not responded to our requests. "
            "We are forced to use generators at great expense. Kindly expedite restoration.",
        ],
        "priority_weights": {"urgent":0.35,"high":0.40,"medium":0.20,"low":0.05},
    },
    "billing": {
        "subjects": [
            "Incorrect electricity bill for the month of {month}",
            "Bill amount inflated — showing {amount} units against actual consumption",
            "Billing dispute: meter reading not taken, estimated bill issued",
            "Duplicate bill received for same period",
            "High arrears on bill despite timely payments — request correction",
        ],
        "descriptions": [
            "I have received my electricity bill for {month} showing a consumption of {amount} units "
            "which is grossly incorrect. My average monthly consumption is around 80-100 units. "
            "The bill has been generated on estimated basis without actual meter reading. "
            "Kindly send a meter reader to verify and issue a corrected bill.",

            "My bill for the period {month} shows arrears of Rs. {amount}/- which I dispute completely. "
            "All my previous bills have been paid promptly. "
            "I suspect the readings have been entered incorrectly. "
            "Request an immediate audit of my account and correction of the outstanding amount.",

            "Despite submitting meter reading through the mobile app, my bill for {month} has been "
            "generated on estimated basis showing {amount} units. The estimated reading is 3x my "
            "normal consumption. Kindly correct the bill and ensure actual reading is taken going forward.",
        ],
        "priority_weights": {"urgent":0.05,"high":0.25,"medium":0.55,"low":0.15},
    },
    "meter_fault": {
        "subjects": [
            "Electricity meter stopped recording units — not working",
            "Meter display showing error code — possible fault",
            "Meter giving electric shocks — safety hazard at premises",
            "New digital meter installed but not yet activated",
            "Meter running fast — recording excess units",
        ],
        "descriptions": [
            "My electricity meter has stopped working. The display shows "
            "no reading and has been in this condition for the past {days} days. "
            "Despite lodging a complaint at the subdivision office, the meter has not been replaced. "
            "I am concerned that I may be billed incorrectly during this period. "
            "Kindly depute a technician to inspect and replace the faulty meter.",

            "The electricity meter at my premises is running unusually fast. "
            "My previous average consumption was around 90 units per month but the meter is now "
            "recording over 250 units monthly without any change in appliance usage. "
            "I suspect the meter has developed a technical fault. Request inspection and testing.",

            "The meter at my premises is showing error code on the digital display. "
            "The local lineman said it requires replacement but it has been {days} days. "
            "Meanwhile I am receiving estimated bills. Request urgent replacement of faulty meter.",
        ],
        "priority_weights": {"urgent":0.10,"high":0.35,"medium":0.45,"low":0.10},
    },
    "new_connection": {
        "subjects": [
            "New domestic electricity connection pending since {date}",
            "Commercial connection application not processed for {days} days",
            "Agricultural pump connection — status enquiry",
            "Load enhancement application — no response from SDO",
            "Temporary connection for construction site not issued",
        ],
        "descriptions": [
            "I applied for a new domestic electricity connection on {date} at the {district} subdivision office. "
            "Despite completing all required documentation including payment of security deposit, "
            "the connection has not been provided even after {days} days. "
            "Multiple visits to the SDO office have not yielded any result. Kindly expedite.",

            "My application for enhancement of sanctioned load from 2KW to 5KW submitted on {date} "
            "is still pending. All documents including load sanction fee have been submitted. "
            "The delay is causing operational problems for my small business. "
            "Request early disposal of my application.",
        ],
        "priority_weights": {"urgent":0.05,"high":0.20,"medium":0.50,"low":0.25},
    },
    "low_voltage": {
        "subjects": [
            "Extremely low voltage in {area} — damaging appliances",
            "Voltage fluctuation causing frequent equipment failure",
            "Low voltage issue persisting for {days} days in our area",
            "Voltage dipping to 160V during peak hours in {area}",
        ],
        "descriptions": [
            "Our area {area}, {district} has been facing severe low voltage problem for the past {days} days. "
            "The voltage frequently dips to 160-170V during peak hours (6 PM to 10 PM), "
            "causing damage to electrical appliances including refrigerators, water pumps, and fans. "
            "Multiple residents have suffered appliance damage. "
            "Kindly inspect the distribution transformer and feeder cables and take corrective action.",

            "I am experiencing voltage fluctuation at my premises. "
            "The voltage varies between 150V and 260V throughout the day. "
            "This has already damaged my washing machine and television. "
            "The local lineman says the issue is with the Distribution Transformer "
            "but no corrective action has been taken. Request urgent inspection.",
        ],
        "priority_weights": {"urgent":0.15,"high":0.45,"medium":0.35,"low":0.05},
    },
    "transformer": {
        "subjects": [
            "Distribution transformer burnt — locality without power for {days} days",
            "Transformer oil leakage near residential area — safety concern",
            "Transformer overloaded — tripping frequently every day",
            "Request for new transformer — existing one insufficient for locality",
            "Transformer making loud humming noise — inspection required",
        ],
        "descriptions": [
            "The 100 KVA distribution transformer serving our colony in {area}, {district} was burnt "
            "on {date} due to overloading. Since then approximately {households} households are "
            "without electricity supply. The subdivision office has been informed but the transformer "
            "has not been replaced despite {days} days. Kindly arrange urgent replacement.",

            "The transformer located near {area} has been tripping repeatedly every day. "
            "It trips 4-5 times daily, each time causing a power outage of 1-2 hours. "
            "The lineman resets it manually but does not address the root cause. "
            "The transformer appears to be overloaded as new connections have been added "
            "without capacity augmentation. Request permanent resolution.",
        ],
        "priority_weights": {"urgent":0.30,"high":0.45,"medium":0.20,"low":0.05},
    },
    "streetlight": {
        "subjects": [
            "Street lights not working in {area} for past {days} days",
            "All street lights in our lane defunct — safety risk at night",
            "Street light pole broken — lying on road, dangerous condition",
            "Request for new street lights in newly developed colony",
        ],
        "descriptions": [
            "The street lights in {area}, {district} have been non-functional for the past {days} days. "
            "The area becomes very dark at night creating safety and security concerns, "
            "especially for women and children. "
            "The local body has requested BSPHCL to repair the lights but no action has been taken. "
            "Kindly depute a lineman to repair/replace the faulty street lights at the earliest.",

            "Almost all street lights in our locality {area} are not working. "
            "The issue started after a storm {days} days ago when several poles and lights were damaged. "
            "The area has elderly residents who find it difficult to move at night. "
            "Request urgent repair of the street lighting system.",
        ],
        "priority_weights": {"urgent":0.05,"high":0.20,"medium":0.45,"low":0.30},
    },
    "safety": {
        "subjects": [
            "Loose live wire hanging in public area — immediate attention required",
            "Electric pole leaning dangerously close to road",
            "Overhead cables sagging too low — touching trees and rooftops",
            "Sparking from distribution box near school compound",
            "Electric shock from street light pole — urgent action needed",
        ],
        "descriptions": [
            "A live electric wire has snapped and is hanging loose near {area}, {district}. "
            "It is touching the ground at several points and poses an extreme electrocution risk "
            "to pedestrians, especially children. Despite calling the emergency helpline {days} "
            "hours ago, no team has arrived. This is a LIFE THREATENING situation requiring "
            "IMMEDIATE attention. Kindly send a team urgently.",

            "The overhead 11KV line passing through {area} is sagging dangerously low. "
            "It is touching tree branches and in one location is only about 10 feet above the road. "
            "Heavy vehicles passing through could make contact with the wire. "
            "Kindly inspect and rectify this dangerous condition immediately.",
        ],
        "priority_weights": {"urgent":0.60,"high":0.35,"medium":0.05,"low":0.00},
    },
    "service_request": {
        "subjects": [
            "Request for shifting of electricity meter to new location",
            "Name transfer on electricity account after property purchase",
            "Request for duplicate bill for past months",
            "Disconnection notice received — payment already made, request reconnection",
        ],
        "descriptions": [
            "I have recently purchased a property in {area}, {district} and wish to transfer the "
            "electricity connection to my name. All property documents including sale deed and NOC "
            "from previous owner are available. Kindly initiate the name transfer at the earliest.",

            "My electricity connection was disconnected citing non-payment. However, I had paid the "
            "outstanding bill amount of Rs. {amount}/- through the BSPHCL online portal on {date}. "
            "I am attaching the payment receipt. "
            "Kindly restore the connection immediately as there is a sick patient at home.",
        ],
        "priority_weights": {"urgent":0.10,"high":0.20,"medium":0.50,"low":0.20},
    },
    "other": {
        "subjects": [
            "Complaint against BSPHCL employee for demanding unofficial payment",
            "Wrong name on electricity bill despite correction request submitted",
            "BSPHCL online portal not working — unable to pay bill",
            "Request for energy audit of commercial premises",
        ],
        "descriptions": [
            "I wish to register a complaint against the lineman of {area} subdivision who visited "
            "my premises on {date} and demanded an unofficial payment of Rs. {amount}/- "
            "to clear my application. When I refused, he threatened to disconnect my supply. "
            "I am filing this complaint under the grievance redressal mechanism. "
            "Kindly investigate and take strict action.",

            "Despite submitting a written application on {date} for correction of name on my "
            "electricity bill, my name continues to appear incorrectly on the bill. "
            "This is causing issues in loan applications and government document submissions. "
            "Kindly make the correction at the earliest.",
        ],
        "priority_weights": {"urgent":0.05,"high":0.15,"medium":0.50,"low":0.30},
    },
}

STAFF_REPLIES = {
    "under_review": [
        "Your complaint has been received and is under review by our team. We will assign a field officer shortly.",
        "We have noted your complaint. Our technical team is assessing the issue. You will be updated soon.",
        "Complaint registered and being reviewed. Expected resolution within {eta} working days.",
    ],
    "in_progress": [
        "A field team has been dispatched to your location. They will inspect and resolve the issue.",
        "Our lineman has been assigned to address your complaint on priority.",
        "Work order has been issued. Repair team is scheduled to visit your area. We regret the inconvenience.",
        "Your complaint has been forwarded to the {district} subdivision office for urgent action.",
    ],
    "resolved": [
        "We are pleased to inform you that your complaint has been resolved. The issue has been rectified by our team. Please verify and let us know if the issue persists.",
        "The matter reported by you has been attended to. Our field team has completed the necessary repairs. Please rate your experience.",
        "Your complaint stands resolved. If you face any further inconvenience, please register a fresh complaint.",
    ],
}

CAT_WEIGHTS = {
    "power_outage":0.22,"billing":0.20,"meter_fault":0.14,
    "transformer":0.12,"low_voltage":0.10,"new_connection":0.08,
    "streetlight":0.06,"safety":0.04,"service_request":0.02,"other":0.02,
}

STATUS_POOL = (
    ["pending"]*25 + ["under_review"]*20 + ["in_progress"]*20 +
    ["resolved"]*45 + ["closed"]*30 + ["rejected"]*8 + ["escalated"]*7
)

MONTHS = ["January","February","March","April","May","June",
          "July","August","September","October","November","December"]


def _wc(d):
    return random.choices(list(d.keys()), weights=list(d.values()), k=1)[0]


def _rdate(days_ago_max, days_ago_min=1):
    return datetime.utcnow() - timedelta(days=random.randint(days_ago_min, days_ago_max))


def _fill(text, **kw):
    defaults = dict(
        days=random.randint(2,15),
        date=(_rdate(30,5)).strftime("%d/%m/%Y"),
        month=random.choice(MONTHS),
        amount=random.choice([320,450,680,1200,1850,2400,3100,4500]),
        households=random.randint(20,200),
        area=random.choice(AREAS),
        district=random.choice(DISTRICTS),
        eta=random.randint(2,5),
        consumer_no=f"BR{random.randint(100000,999999)}",
    )
    defaults.update(kw)
    try:
        return text.format(**defaults)
    except Exception:
        return text


def seed():
    print("🌱  Seeding BSPHCL demo data...")

    # ── 1. Staff ───────────────────────────────────────────────────────────────
    staff_specs = [
        dict(name="Rajiv Ranjan",   email="rajiv.ranjan@bsphcl.gov.in",
             mobile="9431100011", role="operator",          department="Central Operations"),
        dict(name="Meena Kumari",   email="meena.kumari@bsphcl.gov.in",
             mobile="9431100012", role="complaint_officer", department="Consumer Grievance Cell"),
        dict(name="Sudhir Prasad",  email="sudhir.prasad@bsphcl.gov.in",
             mobile="9431100013", role="complaint_officer", department="Technical Division"),
        dict(name="Arvind Singh",   email="arvind.singh@bsphcl.gov.in",
             mobile="9431100014", role="field_staff",       department="Field Operations"),
    ]
    staff_objs = []
    for s in staff_specs:
        u = User.query.filter_by(email=s["email"]).first()
        if not u:
            u = User(
                name=s["name"], email=s["email"], mobile=s["mobile"],
                role=s["role"], department=s["department"],
                is_admin=True, district="Patna", state="Bihar",
                consumer_number=generate_consumer_number(),
            )
            u.set_password("Staff@2024")
            db.session.add(u)
            db.session.flush()
            print(f"   staff: {s['name']}")
        staff_objs.append(u)
    db.session.commit()

    # ── 2. Consumers ───────────────────────────────────────────────────────────
    existing_mobiles = {m[0] for m in db.session.query(User.mobile).all()}
    existing_emails  = {e[0] for e in db.session.query(User.email).all()}
    consumers = []

    for i in range(30):
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        district = random.choice(DISTRICTS)

        mobile = str(7000100000 + i * 7 + random.randint(1,6))
        while mobile in existing_mobiles:
            mobile = str(int(mobile) + 1)
        existing_mobiles.add(mobile)

        email = f"{fn.lower()}.{ln.lower()}{i}@gmail.com"
        while email in existing_emails:
            email = f"{fn.lower()}.{ln.lower()}{i}{random.randint(1,99)}@gmail.com"
        existing_emails.add(email)

        u = User(
            name=f"{fn} {ln}", email=email, mobile=mobile,
            role="consumer", district=district, state="Bihar",
            address=f"{random.choice(AREAS)}, {district}, Bihar",
            consumer_number=generate_consumer_number(),
            created_at=_rdate(180, 30),
        )
        u.set_password("Consumer@2024")
        db.session.add(u)
        consumers.append(u)

    db.session.commit()
    print(f"   consumers: {len(consumers)}")

    # ── 3. Complaints ──────────────────────────────────────────────────────────
    seq = Complaint.query.count() + 1
    complaint_objs = []

    for _ in range(160):
        consumer  = random.choice(consumers)
        category  = _wc(CAT_WEIGHTS)
        tmpl      = TEMPLATES[category]
        priority  = _wc(tmpl["priority_weights"])
        area      = random.choice(AREAS)
        district  = consumer.district

        subject = _fill(random.choice(tmpl["subjects"]), area=area, district=district)[:200]
        desc    = _fill(random.choice(tmpl["descriptions"]), area=area, district=district)
        status  = random.choice(STATUS_POOL)

        created_at = _rdate(170, 1)
        if status in ("resolved","closed"):
            created_at = _rdate(170, 20)

        eta_days = {"urgent":1,"high":2,"medium":4,"low":7}[priority]
        eta = created_at + timedelta(days=eta_days)

        resolved_at = None
        if status in ("resolved","closed"):
            resolved_at = created_at + timedelta(days=random.randint(1, eta_days+3))

        assignee = random.choice(staff_objs) if status != "pending" else None

        c = Complaint(
            complaint_id      = f"BSP{datetime.utcnow().year}{seq:05d}",
            user_id           = consumer.id,
            subject           = subject,
            description       = desc,
            category          = category,
            priority          = priority,
            status            = status,
            district          = district,
            address           = f"{area}, {district}, Bihar",
            consumer_number   = consumer.consumer_number,
            meter_number      = f"MTR{random.randint(100000,999999)}",
            assigned_to       = assignee.id if assignee else None,
            department        = assignee.department if assignee else None,
            expected_resolution_date = eta,
            created_at        = created_at,
            updated_at        = created_at + timedelta(hours=random.randint(1,48)),
            resolved_at       = resolved_at,
            first_review_at   = (created_at + timedelta(hours=random.randint(2,12))
                                 if status != "pending" else None),
            resolution_summary = (
                f"Issue resolved by field team. {category.replace('_',' ').title()} "
                f"in {area}, {district} has been rectified."
                if status in ("resolved","closed") else None
            ),
        )
        db.session.add(c)
        db.session.flush()
        complaint_objs.append((c, consumer, assignee))
        seq += 1

    db.session.commit()
    print(f"   complaints: {len(complaint_objs)}")

    # ── 4. Logs ────────────────────────────────────────────────────────────────
    logs = 0
    for c, consumer, assignee in complaint_objs:
        db.session.add(ComplaintLog(
            complaint_id=c.id, user_id=consumer.id,
            action="complaint_filed",
            message=f"Complaint {c.complaint_id} filed by consumer.",
            created_at=c.created_at,
        ))
        logs += 1
        if c.status != "pending":
            staff = assignee or random.choice(staff_objs)
            db.session.add(ComplaintLog(
                complaint_id=c.id, user_id=staff.id,
                action="status_changed",
                message="Complaint taken up for review.",
                created_at=c.created_at + timedelta(hours=random.randint(2,10)),
            ))
            logs += 1
        if c.status in ("in_progress","resolved","closed","escalated","assigned"):
            staff = assignee or random.choice(staff_objs)
            db.session.add(ComplaintLog(
                complaint_id=c.id, user_id=staff.id,
                action="assigned",
                message=f"Assigned to {staff.name} ({staff.department}).",
                created_at=c.created_at + timedelta(hours=random.randint(10,24)),
            ))
            logs += 1
        if c.status in ("resolved","closed"):
            staff = assignee or random.choice(staff_objs)
            db.session.add(ComplaintLog(
                complaint_id=c.id, user_id=staff.id,
                action="resolved",
                message=c.resolution_summary or "Complaint resolved by field team.",
                created_at=c.resolved_at or (c.created_at + timedelta(days=2)),
            ))
            logs += 1

    db.session.commit()
    print(f"   logs: {logs}")

    # ── 5. Replies ─────────────────────────────────────────────────────────────
    replies = 0
    for c, consumer, assignee in complaint_objs:
        staff = assignee or random.choice(staff_objs)
        area  = (c.address or "").split(",")[0]

        if c.status == "under_review":
            db.session.add(Reply(
                complaint_id=c.id, user_id=staff.id, is_admin_reply=True,
                message=_fill(random.choice(STAFF_REPLIES["under_review"])),
                created_at=c.created_at + timedelta(hours=random.randint(4,14)),
            ))
            replies += 1
        elif c.status in ("in_progress","escalated","assigned"):
            db.session.add(Reply(
                complaint_id=c.id, user_id=staff.id, is_admin_reply=True,
                message=_fill(random.choice(STAFF_REPLIES["in_progress"]), district=c.district or ""),
                created_at=c.created_at + timedelta(hours=random.randint(8,24)),
            ))
            replies += 1
        elif c.status in ("resolved","closed"):
            db.session.add(Reply(
                complaint_id=c.id, user_id=staff.id, is_admin_reply=True,
                message=_fill(random.choice(STAFF_REPLIES["in_progress"]), district=c.district or ""),
                created_at=c.created_at + timedelta(hours=random.randint(8,18)),
            ))
            db.session.add(Reply(
                complaint_id=c.id, user_id=staff.id, is_admin_reply=True,
                message=random.choice(STAFF_REPLIES["resolved"]),
                created_at=c.resolved_at or (c.created_at + timedelta(days=2)),
            ))
            replies += 2
            if c.status == "closed" and random.random() < 0.30:
                db.session.add(Reply(
                    complaint_id=c.id, user_id=consumer.id, is_admin_reply=False,
                    message=random.choice([
                        "Thank you for resolving the issue. Power supply has been restored.",
                        "Issue has been resolved. Bill has been corrected. Thank you.",
                        "The lineman visited and fixed the problem. Satisfied with the resolution.",
                    ]),
                    created_at=(c.resolved_at or c.created_at + timedelta(days=2)) + timedelta(hours=random.randint(2,12)),
                ))
                replies += 1

    db.session.commit()
    print(f"   replies: {replies}")

    # ── 6. Ratings ─────────────────────────────────────────────────────────────
    closed = [(c,consumer) for c,consumer,_ in complaint_objs if c.status=="closed"]
    sample = random.sample(closed, min(len(closed), int(len(closed)*0.65)))
    ratings = 0
    for c, consumer in sample:
        if not SatisfactionRating.query.filter_by(complaint_id=c.id).first():
            rv = random.choices([1,2,3,4,5], weights=[0.05,0.08,0.15,0.35,0.37])[0]
            fb = {
                5:["Excellent service. Issue resolved quickly.","Very satisfied. Lineman was professional."],
                4:["Good service. Took a bit long but resolved.","Satisfied with the outcome."],
                3:["Average experience. Issue resolved but took too long."],
                2:["Took too many days but finally resolved."],
                1:["Very poor service. Too many follow-ups needed."],
            }[rv]
            db.session.add(SatisfactionRating(
                complaint_id=c.id, user_id=consumer.id,
                rating=rv, feedback=random.choice(fb),
                created_at=(c.resolved_at or c.created_at + timedelta(days=3)) + timedelta(hours=random.randint(1,24)),
            ))
            ratings += 1

    db.session.commit()
    print(f"   ratings: {ratings}")

    # ── 7. Notifications ───────────────────────────────────────────────────────
    notifs = 0
    for c, consumer, _ in complaint_objs:
        if c.status != "pending":
            db.session.add(Notification(
                user_id=consumer.id,
                title=f"Complaint {c.complaint_id} — Status Update",
                message=f"Your complaint '{c.subject[:60]}' status: {c.get_status_label()}.",
                is_read=random.random() > 0.4,
                notif_type="info",
                related_complaint=c.complaint_id,
                created_at=c.created_at + timedelta(hours=random.randint(4,24)),
            ))
            notifs += 1
        if c.status in ("resolved","closed"):
            db.session.add(Notification(
                user_id=consumer.id,
                title=f"Complaint {c.complaint_id} — Resolved",
                message="Your complaint has been resolved by our field team. Please rate your experience.",
                is_read=random.random() > 0.3,
                notif_type="success",
                related_complaint=c.complaint_id,
                created_at=c.resolved_at or (c.created_at + timedelta(days=2)),
            ))
            notifs += 1

    db.session.commit()
    print(f"   notifications: {notifs}")

    # ── Summary ────────────────────────────────────────────────────────────────
    from sqlalchemy import text
    rows = db.session.execute(
        text("SELECT status, COUNT(*) as n FROM complaints GROUP BY status ORDER BY n DESC")
    ).fetchall()
    print("\n" + "="*50)
    print("✅  BSPHCL demo data seeded successfully!")
    print(f"   Staff: {len(staff_objs)}  |  Consumers: {len(consumers)}  |  Complaints: {len(complaint_objs)}")
    print("   Status breakdown:")
    for row in rows:
        print(f"     {row[0]:<20} {row[1]}")
    print("\n   Credentials:")
    print("   Admin    admin@bsphcl.gov.in     / Admin@2024")
    print("   Staff    rajiv.ranjan@bsphcl.gov.in / Staff@2024")
    print("   Consumer (any seeded)           / Consumer@2024")
    print("="*50)
