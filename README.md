<div align="center">

<h1>⚡ BSPHCL Consumer Complaint Portal</h1>

<p>A production-ready complaint management system built for Bihar State Power Holding Company Ltd.</p>

[![Live Demo](https://img.shields.io/badge/LIVE%20DEMO-Visit%20Portal-brightgreen?style=for-the-badge&logo=render&logoColor=white)](https://bsphcl-complaint-portal.onrender.com)

![Flask](https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat-square&logo=postgresql&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap%205-7952B3?style=flat-square&logo=bootstrap&logoColor=white)
![Render](https://img.shields.io/badge/Deployed%20on-Render-46E3B7?style=flat-square&logo=render&logoColor=white)

</div>

---

## About

A full-stack complaint management portal built during an internship at **Bihar State Power Holding Company Ltd. (BSPHCL)**. The system handles the complete complaint lifecycle — from submission by consumers to resolution by staff — with role-based access, analytics, and PDF/Excel exports.

---

## Live Demo

**URL:** https://bsphcl-complaint-portal.onrender.com

| Role | Email | Password |
|---|---|---|
| Admin | admin@bsphcl.gov.in | Admin@2024 |
| Consumer | Register directly on the website | — |

---

## Features

**Consumer Side**
- Register and submit complaints with file attachments
- Track complaint status using Complaint ID + Consumer Number
- Download acknowledgement slip
- Rate satisfaction after resolution

**Admin Side**
- Role-based access: Super Admin, Complaint Officer, Operator, Field Staff
- Full complaint lifecycle: Submit → Review → Assign → Resolve → Close → Reopen
- Priority-based handling and department assignment
- Internal staff remarks and timeline logging
- Search, filter, and export complaints to Excel and PDF
- Analytics dashboard with district/category-wise charts (Chart.js)

**Security**
- OTP-based authentication
- CSRF protection
- Secure environment-based configuration

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask, Flask-SQLAlchemy, Flask-Login, Flask-Mail |
| Database | PostgreSQL (Production), SQLite (Local) |
| Frontend | HTML5, Bootstrap 5, Chart.js |
| Exports | ReportLab (PDF), OpenPyXL (Excel) |
| Deployment | Render, Gunicorn |

---

## Project Structure

```
app.py              # App factory
config.py           # Environment configuration
models.py           # Database models (6+ tables)
main_routes.py      # Consumer routes
admin_routes.py     # Admin routes
utils.py            # Helper functions
init_db.py          # DB initialization
static/             # CSS, JS, images
templates/          # HTML templates
```

---

## Run Locally

```bash
# Clone the repo
git clone https://github.com/sakshii1411/bspchcl-complaint-portal.git
cd bspchcl-complaint-portal

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your values

# Initialize database
python init_db.py

# Run the app
python run.py
```

Open: http://127.0.0.1:5001

---

## Environment Variables

```
SECRET_KEY=your-secret-key
ADMIN_SECRET_CODE=your-admin-code
DATABASE_URL=your-postgresql-url
MAIL_USERNAME=your-email
MAIL_PASSWORD=your-app-password
```

---

## Deployment

Deployed on **Render** using:
- Render Web Service
- Gunicorn as production server
- PostgreSQL add-on for database
- Environment variables for secrets
- Automatic DB initialization on deploy

---

## Future Enhancements

- OTP-based login via mobile number
- WhatsApp/SMS integration for status updates
- Automated complaint escalation system
- Real-time notifications
- AI-based complaint categorization

---

<div align="center">

Built by [Sakshi Awasthi](https://github.com/sakshii1411) during internship at BSPHCL, Jun–Jul 2025

</div>
