# BSPHCL Consumer Complaint Portal

A full-stack complaint management system built during an internship at **Bihar State Power Holding Company Limited (BSPHCL)**. The portal handles the complete complaint lifecycle — from submission by consumers to resolution by staff — with role-based access, real-time tracking, analytics, and PDF exports.

**Live Demo:** [bsphcl-complaint-portal.onrender.com](https://bsphcl-complaint-portal.onrender.com)

---

## Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| Super Admin | admin@bsphcl.gov.in | Admin@2024 |
| Staff (Operator) | rajiv.ranjan@bsphcl.gov.in | Staff@2024 |
| Staff (Officer) | meena.kumari@bsphcl.gov.in | Staff@2024 |
| Consumer | priya.singh1@gmail.com | Consumer@2024 |

> The demo database is pre-seeded with 160 realistic Bihar electricity complaints across 20 districts, 30 consumer accounts, and 4 staff accounts.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, Flask 3.0 |
| Database | PostgreSQL (Render), SQLite (local dev) |
| ORM | SQLAlchemy + Flask-Migrate |
| Frontend | Bootstrap 5.3, Chart.js 4.4, Noto Sans |
| File Storage | Cloudinary (production), local disk (dev) |
| PDF Generation | ReportLab 4.2 |
| Email | Flask-Mail (SMTP) |
| Deployment | Render (free tier) |
| Auth | Flask-Login + bcrypt |

---

## Features

### Consumer Portal
- **Register & Login** — account creation with validation, OTP-based password reset
- **File Complaint** — 10 categories (Power Outage, Billing, Meter Fault, Transformer, Low Voltage, New Connection, Street Light, Safety, Service Request, Other)
- **Track Complaints** — real-time status, priority, assigned officer, expected resolution date
- **Public Tracker** — track by Complaint ID + Consumer Number without logging in
- **PDF Downloads** — Acknowledgement Slip and Resolution Report with official BSPHCL letterhead
- **CSV Export** — download complaint history as spreadsheet
- **Reply Thread** — two-way communication with BSPHCL staff
- **Satisfaction Rating** — rate resolved complaints (1–5 stars)
- **Notifications** — status update alerts with read/unread tracking
- **Profile Management** — photo upload (Cloudinary), password change

### Admin / Staff Panel
- **Operations Dashboard** — live KPI cards, 7-day trend chart, category donut, district bar chart
- **All Complaints** — filterable by status/priority/category/district, bulk status update + bulk assign
- **Complaint Workflow** — update status, priority, assignee, ETA, resolution summary, internal remarks, consumer-visible notes
- **Consumer Management** — view profiles, complaint history, activate/deactivate accounts
- **Staff Management** — add staff (super admin only), set roles, reset passwords
- **Reports Page** — monthly trend, status breakdown, priority distribution, top districts, date range filter, Excel + PDF export
- **Audit Trail** — every status change logged with timestamp and actor

### Security
- CSRF protection on all POST forms
- Role-based access control (consumer / operator / complaint_officer / field_staff / super_admin)
- Password hashing (bcrypt via Werkzeug)
- Session management via Flask-Login
- Input validation both client-side and server-side

---

## Local Setup

```bash
# 1. Clone
git clone https://github.com/sakshii1411/bspchcl-complaint-portal.git
cd bspchcl-complaint-portal

# 2. Virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Environment variables — create .env file
cp .env.example .env
# Edit .env with your values (see below)

# 5. Initialise database
python init_db.py

# 6. Seed demo data (optional)
python seed_demo.py

# 7. Run
python run.py
# → http://localhost:5001
```

### Environment Variables

```env
# Required
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///bsphcl.db       # or postgresql://...

# Email (optional — OTP shown on screen if not set)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your@gmail.com
MAIL_PASSWORD=your-app-password        # Gmail App Password

# Cloudinary (optional — local disk used if not set)
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

---

## Project Structure

```
bspchcl-complaint-portal/
├── app.py              # Application factory
├── models.py           # SQLAlchemy models (User, Complaint, etc.)
├── main_routes.py      # Consumer routes
├── admin_routes.py     # Admin/staff routes
├── utils.py            # Helpers: PDF, email, file upload, OTP
├── extensions.py       # Flask extensions (db, mail, login_manager)
├── config.py           # Configuration classes
├── init_db.py          # DB init + admin seeder
├── seed_demo.py        # Demo dataset (160 complaints, 30 users)
├── run.py              # Gunicorn entry point
├── requirements.txt
├── static/
│   ├── css/style.css   # BSPHCL government design system
│   └── js/scripts.js
└── templates/
    ├── base.html        # Sidebar + topbar layout
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── complaint_form.html
    ├── complaint_history.html
    ├── complaint_detail.html
    ├── profile.html
    ├── notifications.html
    ├── help_desk.html   # Public complaint tracker + FAQ
    ├── admin/
    │   ├── dashboard_admin.html
    │   ├── all_complaints.html
    │   ├── complaint_detail_admin.html
    │   ├── manage_users.html
    │   ├── manage_staff.html
    │   └── reports.html
    └── errors/
        ├── 404.html
        ├── 403.html
        └── 500.html
```

---

## Deployment (Render)

1. Fork / push to GitHub
2. Create a new **Web Service** on [render.com](https://render.com)
3. Connect your GitHub repo
4. Set **Build Command:** `pip install -r requirements.txt && python init_db.py`
5. Set **Start Command:** `gunicorn run:app`
6. Add environment variables in the Render dashboard
7. Add a free **PostgreSQL** database and copy the `DATABASE_URL`

The app auto-seeds demo data on first deploy when the complaints table is empty.

---

## Built by

**Sakshi Awasthi** — B.Tech CSE, MIT World Peace University, Pune (2027)  
Internship at Bihar State Power Holding Company Limited, Patna  
GitHub: [@sakshii1411](https://github.com/sakshii1411) · [LinkedIn](https://linkedin.com/in/sakshi-awasthi14)
