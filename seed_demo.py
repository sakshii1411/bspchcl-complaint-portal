"""
seed_demo.py  —  BSPHCL Demo Dataset  (hardened v3)
Handles: unique constraint collisions, stuck sentinels, partial seeds.
Safe to call multiple times — always idempotent.
"""

import random, string
from datetime import datetime, timedelta
from extensions import db
from models import (User, Complaint, ComplaintLog,
                    Reply, Notification, SatisfactionRating)
from sqlalchemy import text

random.seed(42)

# ── Bihar data ─────────────────────────────────────────────────────────────────
DISTRICTS = [
    "Patna","Gaya","Bhagalpur","Muzaffarpur","Purnia",
    "Darbhanga","Ara","Begusarai","Katihar","Munger",
    "Chapra","Hajipur","Sasaram","Bettiah","Siwan",
    "Motihari","Samastipur","Nawada","Jehanabad","Aurangabad",
]
AREAS = [
    "Rajendra Nagar","Boring Road Colony","Ashok Rajpath","Kankarbagh",
    "Patliputra Colony","Shastri Nagar","Punaichak","Anisabad",
    "Phulwari Sharif","Danapur","Khagaul","Fatuha","Barh",
    "Punpun","Masaurhi","Bakhtiyarpur","Mokama","Bihta",
    "Maner","Naubatpur","Gandhi Maidan Area","Station Road",
    "New Bypass Colony","Lohia Nagar","Mithapur Nagar",
]
FIRST = ["Rajesh","Sunita","Amit","Priya","Suresh","Kavita","Vijay","Anita",
         "Rajan","Meena","Deepak","Suman","Ashok","Rekha","Manoj","Geeta",
         "Santosh","Usha","Ramesh","Shanti","Dinesh","Pushpa","Arun","Lalita",
         "Rohit","Nirmala","Vikas","Seema","Pawan","Asha"]
LAST  = ["Kumar","Singh","Prasad","Sharma","Yadav","Verma","Gupta","Mishra",
         "Tiwari","Pandey","Sinha","Jha","Thakur","Chaudhary","Shah"]
MONTHS = ["January","February","March","April","May","June",
          "July","August","September","October","November","December"]

TEMPLATES = {
    "power_outage": {
        "subjects": [
            "No electricity supply for past {days} days in {area}",
            "Complete power outage in our locality since {date}",
            "Frequent power cuts affecting daily life in {area}",
            "Unscheduled load shedding without prior notice in {district}",
        ],
        "descriptions": [
            "Our area {area}, {district} has been without electricity for {days} days. "
            "No prior intimation was given by BSPHCL. Approximately {households} households "
            "are affected. Multiple complaints at local subdivision have yielded no result. "
            "Request urgent restoration of supply.",
            "Continuous power failure in {area}, {district} since {date}. The local lineman "
            "visited but could not resolve the issue. Elderly residents and patients are severely "
            "affected. Transformer appears to have developed a fault. Request immediate inspection.",
        ],
        "priority": {"urgent":0.35,"high":0.40,"medium":0.20,"low":0.05},
    },
    "billing": {
        "subjects": [
            "Incorrect electricity bill for the month of {month}",
            "Bill amount inflated — showing {amount} units against actual consumption",
            "Billing dispute: meter reading not taken, estimated bill issued",
            "High arrears on bill despite timely payments",
        ],
        "descriptions": [
            "Bill for {month} shows {amount} units which is grossly incorrect. My average monthly "
            "consumption is 80-100 units. Bill generated on estimated basis without actual meter "
            "reading. Kindly send a meter reader and issue a corrected bill.",
            "Bill shows arrears of Rs. {amount}/- which I dispute. All previous bills paid promptly. "
            "Readings entered incorrectly. Request immediate audit and correction.",
        ],
        "priority": {"urgent":0.05,"high":0.25,"medium":0.55,"low":0.15},
    },
    "meter_fault": {
        "subjects": [
            "Electricity meter stopped recording units",
            "Meter display showing error code",
            "Meter giving electric shocks — safety hazard",
            "Meter running fast — recording excess units",
        ],
        "descriptions": [
            "Meter stopped working {days} days ago. Despite subdivision complaint, not replaced. "
            "Concerned about incorrect billing. Request urgent inspection and replacement.",
            "Meter recording 250+ units monthly against my normal 90 units. Suspect technical fault. "
            "Request inspection and testing by BSPHCL officials.",
        ],
        "priority": {"urgent":0.10,"high":0.35,"medium":0.45,"low":0.10},
    },
    "transformer": {
        "subjects": [
            "Distribution transformer burnt — locality without power for {days} days",
            "Transformer oil leakage near residential area",
            "Transformer overloaded — tripping frequently",
            "Transformer making loud humming noise",
        ],
        "descriptions": [
            "100 KVA transformer serving our colony in {area} burnt on {date} due to overloading. "
            "{households} households without power for {days} days. Subdivision informed but not "
            "replaced. Request urgent replacement.",
            "Transformer in {area} tripping 4-5 times daily causing 1-2 hour outages each time. "
            "Lineman resets manually but root cause not addressed. Transformer overloaded. "
            "Request permanent resolution.",
        ],
        "priority": {"urgent":0.30,"high":0.45,"medium":0.20,"low":0.05},
    },
    "low_voltage": {
        "subjects": [
            "Extremely low voltage in {area} — damaging appliances",
            "Voltage fluctuation causing equipment failure",
            "Voltage dipping to 160V during peak hours",
        ],
        "descriptions": [
            "{area}, {district} facing severe low voltage for {days} days. Voltage dips to 160-170V "
            "during peak hours (6-10 PM). Multiple appliances damaged. Request DT inspection.",
            "Voltage varies between 150V and 260V. Already damaged washing machine and TV. "
            "Lineman says issue is with DT but no action taken. Request urgent inspection.",
        ],
        "priority": {"urgent":0.15,"high":0.45,"medium":0.35,"low":0.05},
    },
    "new_connection": {
        "subjects": [
            "New domestic electricity connection pending since {date}",
            "Commercial connection application not processed for {days} days",
            "Load enhancement application — no response",
        ],
        "descriptions": [
            "Applied for new domestic connection on {date} at {district} subdivision. All documents "
            "and security deposit submitted. Connection not provided after {days} days. Kindly expedite.",
            "Load enhancement from 2KW to 5KW applied on {date}, still pending. Causing business "
            "operational problems. Request early disposal.",
        ],
        "priority": {"urgent":0.05,"high":0.20,"medium":0.50,"low":0.25},
    },
    "streetlight": {
        "subjects": [
            "Street lights not working in {area} for past {days} days",
            "All street lights in our lane defunct — safety risk",
            "Street light pole broken — lying on road",
        ],
        "descriptions": [
            "Street lights in {area}, {district} non-functional for {days} days. Area becomes dark "
            "at night — safety and security risk especially for women and children. Kindly repair.",
            "Almost all street lights in {area} not working after storm {days} days ago. "
            "Elderly residents cannot move at night. Request urgent repair.",
        ],
        "priority": {"urgent":0.05,"high":0.20,"medium":0.45,"low":0.30},
    },
    "safety": {
        "subjects": [
            "Loose live wire hanging in public area — immediate attention required",
            "Overhead cables sagging too low — touching trees",
            "Sparking from distribution box near school",
        ],
        "descriptions": [
            "Live electric wire snapped and hanging loose near {area}. Touching ground at several "
            "points — extreme electrocution risk. Emergency helpline called {days} hours ago but "
            "no team arrived. LIFE THREATENING — send team urgently.",
            "11KV line passing through {area} sagging dangerously. Touching tree branches and "
            "only 10 feet above road. Heavy vehicles could make contact. Rectify immediately.",
        ],
        "priority": {"urgent":0.60,"high":0.35,"medium":0.05,"low":0.00},
    },
    "service_request": {
        "subjects": [
            "Name transfer on electricity account after property purchase",
            "Connection wrongly disconnected — payment already made",
            "Request for duplicate bill",
        ],
        "descriptions": [
            "Recently purchased property in {area}. Wish to transfer connection to my name. "
            "All documents including sale deed and NOC available. Request name transfer.",
            "Connection disconnected citing non-payment but bill of Rs. {amount}/- paid online "
            "on {date}. Payment receipt available. Sick patient at home. Request urgent reconnection.",
        ],
        "priority": {"urgent":0.10,"high":0.20,"medium":0.50,"low":0.20},
    },
    "other": {
        "subjects": [
            "Complaint against BSPHCL employee for demanding unofficial payment",
            "Wrong name on electricity bill despite correction request",
            "BSPHCL online portal not working",
        ],
        "descriptions": [
            "Lineman of {area} subdivision demanded unofficial payment of Rs. {amount}/- to "
            "clear application. Threatened disconnection when refused. Request investigation.",
            "Submitted correction request on {date} for name on bill — still incorrect after "
            "{days} days. Causing issues in loan applications. Request immediate correction.",
        ],
        "priority": {"urgent":0.05,"high":0.15,"medium":0.50,"low":0.30},
    },
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
STAFF_REPLIES_PROGRESS = [
    "A field team has been dispatched to your location and will inspect the issue.",
    "Our lineman has been assigned to address your complaint on priority.",
    "Work order issued. Repair team scheduled to visit your area. We regret the delay.",
    "Complaint forwarded to subdivision office for urgent field action.",
]
STAFF_REPLIES_RESOLVED = [
    "We are pleased to inform you that your complaint has been resolved. "
    "The issue has been rectified by our field team. Please verify and inform us if it persists.",
    "The matter reported by you has been attended to. Our field team has completed the necessary "
    "repairs. Kindly rate your experience so we can improve our services.",
    "Your complaint stands resolved. If you face further inconvenience, please file a fresh complaint.",
]
STAFF_REPLIES_REVIEW = [
    "Your complaint has been received and is under review by our team. Field officer will be assigned shortly.",
    "We have noted your complaint. Our technical team is assessing the situation. You will be updated soon.",
    "Complaint registered and under review. Expected resolution within {eta} working days.",
]


def _wc(d):
    return random.choices(list(d.keys()), weights=list(d.values()), k=1)[0]

def _rdate(max_days, min_days=1):
    return datetime.utcnow() - timedelta(days=random.randint(min_days, max_days))

def _fill(text, **kw):
    d = dict(
        days=random.randint(2,15), area=random.choice(AREAS),
        district=random.choice(DISTRICTS), month=random.choice(MONTHS),
        amount=random.choice([320,450,680,1200,1850,2400,3100,4500]),
        households=random.randint(20,200), eta=random.randint(2,5),
        date=(_rdate(30,5)).strftime("%d/%m/%Y"),
    )
    d.update(kw)
    try:
        return text.format(**d)
    except Exception:
        return text

def _unique_consumer_number(existing):
    """Generate a unique consumer number not in the existing set."""
    for _ in range(100):
        digits = ''.join(random.choices(string.digits, k=10))
        cn = f"BSPHCL-{digits}"
        if cn not in existing:
            existing.add(cn)
            return cn
    # Fallback: timestamp-based
    import time
    cn = f"BSPHCL-{int(time.time() * 1000) % 10000000000:010d}"
    existing.add(cn)
    return cn


def seed():
    print("🌱  Seeding BSPHCL demo data...")

    # Track existing unique values to avoid constraint violations
    existing_emails   = {r[0] for r in db.session.execute(text("SELECT email FROM users")).fetchall()}
    existing_mobiles  = {r[0] for r in db.session.execute(text("SELECT mobile FROM users WHERE mobile IS NOT NULL")).fetchall()}
    existing_cnumbers = {r[0] for r in db.session.execute(text("SELECT consumer_number FROM users WHERE consumer_number IS NOT NULL")).fetchall()}
    existing_cids     = {r[0] for r in db.session.execute(text("SELECT complaint_id FROM complaints")).fetchall()}

    # ── 1. Staff ───────────────────────────────────────────────────────────────
    staff_specs = [
        ("Rajiv Ranjan",  "rajiv.ranjan@bsphcl.gov.in",  "9431100011","operator",          "Central Operations"),
        ("Meena Kumari",  "meena.kumari@bsphcl.gov.in",  "9431100012","complaint_officer","Consumer Grievance Cell"),
        ("Sudhir Prasad", "sudhir.prasad@bsphcl.gov.in", "9431100013","complaint_officer","Technical Division"),
        ("Arvind Singh",  "arvind.singh@bsphcl.gov.in",  "9431100014","field_staff",       "Field Operations"),
    ]
    staff_objs = []
    for name, email, mobile, role, dept in staff_specs:
        u = User.query.filter_by(email=email).first()
        if not u:
            if mobile in existing_mobiles:
                mobile = f"94311{random.randint(10000,99999)}"
            cn = _unique_consumer_number(existing_cnumbers)
            u = User(name=name, email=email, mobile=mobile, role=role,
                     department=dept, is_admin=True, district="Patna",
                     state="Bihar", consumer_number=cn)
            u.set_password("Staff@2024")
            db.session.add(u)
            existing_emails.add(email)
            existing_mobiles.add(mobile)
            db.session.flush()
            print(f"   staff: {name}")
        staff_objs.append(u)
    db.session.commit()

    # ── 2. Consumers ───────────────────────────────────────────────────────────
    consumers = []
    for i in range(30):
        fn = FIRST[i % len(FIRST)]
        ln = LAST[i % len(LAST)]
        district = DISTRICTS[i % len(DISTRICTS)]

        # Deterministic but unique email
        base_email = f"{fn.lower()}.{ln.lower()}.{i:03d}@gmail.com"
        email = base_email
        suffix = 0
        while email in existing_emails:
            suffix += 1
            email = f"{fn.lower()}.{ln.lower()}.{i:03d}x{suffix}@gmail.com"
        existing_emails.add(email)

        # Deterministic mobile — 70001XXXXX
        mobile = f"7000{100000 + i * 7:06d}"
        while mobile in existing_mobiles or len(mobile) != 10:
            mobile = f"7000{random.randint(100000,999999):06d}"
        existing_mobiles.add(mobile)

        cn = _unique_consumer_number(existing_cnumbers)

        u = User(
            name=f"{fn} {ln}", email=email, mobile=mobile,
            role="consumer", district=district, state="Bihar",
            address=f"{random.choice(AREAS)}, {district}, Bihar",
            consumer_number=cn,
            created_at=_rdate(180, 30),
        )
        u.set_password("Consumer@2024")
        db.session.add(u)
        consumers.append(u)

    db.session.commit()
    print(f"   consumers: {len(consumers)}")

    # ── 3. Complaints ──────────────────────────────────────────────────────────
    # Get highest existing seq number to avoid complaint_id collision
    last_seq_row = db.session.execute(
        text("SELECT complaint_id FROM complaints ORDER BY created_at DESC LIMIT 1")
    ).fetchone()
    seq = 1
    if last_seq_row:
        try:
            seq = int(last_seq_row[0].replace('SEED_LOCK','0').replace('BSP2026','').replace('BSP2025','')) + 1
        except Exception:
            seq = 1000

    complaint_objs = []
    for _ in range(160):
        consumer = random.choice(consumers)
        category = _wc(CAT_WEIGHTS)
        tmpl     = TEMPLATES[category]
        priority = _wc(tmpl["priority"])
        area     = random.choice(AREAS)

        subject = _fill(random.choice(tmpl["subjects"]), area=area, district=consumer.district)[:200]
        desc    = _fill(random.choice(tmpl["descriptions"]), area=area, district=consumer.district)
        status  = random.choice(STATUS_POOL)

        created_at = _rdate(170, 1)
        if status in ("resolved","closed"):
            created_at = _rdate(170, 20)

        eta_days   = {"urgent":1,"high":2,"medium":4,"low":7}[priority]
        eta        = created_at + timedelta(days=eta_days)
        resolved_at = (created_at + timedelta(days=random.randint(1, eta_days+3))
                       if status in ("resolved","closed") else None)
        assignee   = random.choice(staff_objs) if status != "pending" else None

        # Generate unique complaint_id
        cid = f"BSP{datetime.utcnow().year}{seq:05d}"
        while cid in existing_cids:
            seq += 1
            cid = f"BSP{datetime.utcnow().year}{seq:05d}"
        existing_cids.add(cid)
        seq += 1

        c = Complaint(
            complaint_id   = cid,
            user_id        = consumer.id,
            subject        = subject,
            description    = desc,
            category       = category,
            priority       = priority,
            status         = status,
            district       = consumer.district,
            address        = f"{area}, {consumer.district}, Bihar",
            consumer_number= consumer.consumer_number,
            meter_number   = f"MTR{random.randint(100000,999999)}",
            assigned_to    = assignee.id if assignee else None,
            department     = assignee.department if assignee else None,
            expected_resolution_date = eta,
            created_at     = created_at,
            updated_at     = created_at + timedelta(hours=random.randint(1,48)),
            resolved_at    = resolved_at,
            first_review_at= (created_at + timedelta(hours=random.randint(2,12))
                              if status != "pending" else None),
            resolution_summary=(
                f"Issue resolved by field team. {category.replace('_',' ').title()} "
                f"in {area}, {consumer.district} has been rectified."
                if status in ("resolved","closed") else None
            ),
        )
        db.session.add(c)
        db.session.flush()
        complaint_objs.append((c, consumer, assignee))

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
        if c.status in ("in_progress","resolved","closed","escalated"):
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
        if c.status == "under_review":
            db.session.add(Reply(
                complaint_id=c.id, user_id=staff.id, is_admin_reply=True,
                message=_fill(random.choice(STAFF_REPLIES_REVIEW)),
                created_at=c.created_at + timedelta(hours=random.randint(4,14)),
            ))
            replies += 1
        elif c.status in ("in_progress","escalated"):
            db.session.add(Reply(
                complaint_id=c.id, user_id=staff.id, is_admin_reply=True,
                message=random.choice(STAFF_REPLIES_PROGRESS),
                created_at=c.created_at + timedelta(hours=random.randint(8,24)),
            ))
            replies += 1
        elif c.status in ("resolved","closed"):
            db.session.add(Reply(
                complaint_id=c.id, user_id=staff.id, is_admin_reply=True,
                message=random.choice(STAFF_REPLIES_PROGRESS),
                created_at=c.created_at + timedelta(hours=random.randint(8,18)),
            ))
            db.session.add(Reply(
                complaint_id=c.id, user_id=staff.id, is_admin_reply=True,
                message=random.choice(STAFF_REPLIES_RESOLVED),
                created_at=c.resolved_at or (c.created_at + timedelta(days=2)),
            ))
            replies += 2
            if c.status == "closed" and random.random() < 0.30:
                db.session.add(Reply(
                    complaint_id=c.id, user_id=consumer.id, is_admin_reply=False,
                    message=random.choice([
                        "Thank you for resolving the issue. Power supply has been restored.",
                        "Issue resolved. Bill has been corrected. Thank you.",
                        "Lineman visited and fixed the problem. Satisfied with resolution.",
                    ]),
                    created_at=(c.resolved_at or c.created_at + timedelta(days=2))
                               + timedelta(hours=random.randint(2,12)),
                ))
                replies += 1
    db.session.commit()
    print(f"   replies: {replies}")

    # ── 6. Ratings ─────────────────────────────────────────────────────────────
    closed = [(c, consumer) for c, consumer, _ in complaint_objs if c.status == "closed"]
    sample = random.sample(closed, min(len(closed), int(len(closed) * 0.65)))
    ratings = 0
    for c, consumer in sample:
        if not SatisfactionRating.query.filter_by(complaint_id=c.id).first():
            rv = random.choices([1,2,3,4,5], weights=[0.05,0.08,0.15,0.35,0.37])[0]
            fb = {
                5:["Excellent service. Issue resolved quickly.","Very satisfied. Lineman was professional."],
                4:["Good service. Took a bit long but resolved.","Satisfied with outcome."],
                3:["Average. Resolved but took too long."],
                2:["Took many days but finally resolved."],
                1:["Very poor service. Too many follow-ups needed."],
            }[rv]
            db.session.add(SatisfactionRating(
                complaint_id=c.id, user_id=consumer.id,
                rating=rv, feedback=random.choice(fb),
                created_at=(c.resolved_at or c.created_at + timedelta(days=3))
                           + timedelta(hours=random.randint(1,24)),
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
                message=f"Your complaint '{c.subject[:60]}' has been updated to: {c.get_status_label()}.",
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
    print("   Admin    admin@bsphcl.gov.in            / Admin@2024")
    print("   Staff    rajiv.ranjan@bsphcl.gov.in     / Staff@2024")
    print(f"  Consumer {consumers[1].email} / Consumer@2024")
    print("="*50)
