# ⚡ BSPHCL Consumer Complaint Portal

A production-ready complaint management system built using Flask, designed to simulate a real-world public utility support platform.

---

## 🚀 Live Demo

🔗 https://bsphcl-complaint-portal.onrender.com

---

## ✨ Features

* Consumer and Admin dashboards
* Complaint lifecycle management:

  * Submit → Review → Assign → Resolve → Close → Reopen
* Complaint assignment to departments and staff
* Priority-based complaint handling
* Complaint tracking using Complaint ID + Consumer Number
* Timeline logging and status updates
* Internal staff remarks (admin only)
* File attachments (PDF, JPG, DOC, etc.)
* Downloadable acknowledgement slip & reports
* Consumer satisfaction rating system
* Search and filter complaints
* Role-based access:

  * Super Admin
  * Complaint Officer
  * Operator
  * Field Staff
* Excel & PDF export
* Data analytics (district/category-wise charts)
* CSRF protection & secure forms
* Environment-based configuration

---

## 🛠️ Tech Stack

* **Backend:** Flask, Flask-SQLAlchemy, Flask-Login
* **Database:** PostgreSQL (Production), SQLite (Local)
* **Frontend:** HTML, Bootstrap 5, Chart.js
* **Others:** Flask-Mail, ReportLab, OpenPyXL

---

## 📂 Project Structure

```
app.py
config.py
models.py
main_routes.py
admin_routes.py
utils.py
init_db.py
static/
templates/
```

---

## 👤 Admin Access

```
Email: admin@bsphcl.gov.in
Password: Admin@2024
```

👉 Only one admin is pre-created
👉 Consumers can register directly from the website

---

## ⚙️ Run Locally

```bash
pip install -r requirements.txt
python init_db.py
python run.py
```

Open:

```
http://127.0.0.1:5001
```

---

## 🌐 Deployment (Render)

This project is deployed using:

* **Render Web Service**
* **Gunicorn (Production Server)**
* **Environment Variables for configuration**
* **Automatic DB initialization on deploy**

---

## 🔐 Environment Variables

```
SECRET_KEY=your-secret-key
ADMIN_SECRET_CODE=your-admin-code
DATABASE_URL=your-postgresql-url
MAIL_USERNAME=your-email
MAIL_PASSWORD=your-app-password
```

---

## 📌 Notes

* Database is auto-created using `init_db.py`
* Works with both SQLite (local) and PostgreSQL (production)
* Designed for:

  * Internship projects
  * College submissions
  * Real-world system simulation

---

## 🚀 Future Enhancements

* OTP-based login via mobile
* WhatsApp/SMS integration
* Automated complaint escalation system
* Real-time notifications
* AI-based complaint categorization

---

## 📣 Conclusion

This project demonstrates a complete full-stack system including:

* Backend logic
* Frontend UI
* Database integration
* Deployment pipeline

👉 Built to simulate a **real government complaint portal system**
