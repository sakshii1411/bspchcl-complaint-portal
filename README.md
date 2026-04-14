# BSPHCL Consumer Complaint Portal

A Flask-based complaint management portal designed to look and behave more like a real public utility support system than a classroom demo.

## Included in this final version

- realistic consumer dashboard and staff dashboard
- complaint workflow with review, assignment, action, resolution, closure, reopen flow, and timeline logging
- complaint assignment to department and staff member
- expected resolution date and overdue tracking
- internal remarks for staff only
- consumer complaint tracking with progress steps
- editable complaints only before review starts
- multiple attachments
- downloadable acknowledgement slip and resolution report
- consumer satisfaction rating after closure
- search by complaint ID and consumer number
- staff roles: super admin, operator, complaint officer, field staff
- bulk status update and assignment
- Excel and PDF export
- district-wise and category-wise analytics with charts
- email-ready OTP and status notification hooks
- CSRF token protection for forms
- safer config using environment variables
- seed script for demo accounts and sample complaints

## Tech stack

- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-Mail
- Flask-Migrate
- SQLite by default
- Chart.js
- Bootstrap 5
- ReportLab
- OpenPyXL

## Project structure

```
app.py
run.py
models.py
main_routes.py
admin_routes.py
utils.py
config.py
init_db.py
static/
templates/
```

## Demo credentials

After running `python init_db.py`:

### Staff
- admin@bsphcl.gov.in / Admin@2024
- officer@bsphcl.gov.in / Admin@2024
- operator@bsphcl.gov.in / Admin@2024
- field@bsphcl.gov.in / Admin@2024

### Consumer
- consumer@example.com / Consumer@2024

## Run locally

```bash
pip install -r requirements.txt
python init_db.py
python run.py
```

Open:

```
http://127.0.0.1:5001
```

## Mail / OTP setup

1. copy `.env.example` to `.env`
2. add your SMTP email and app password
3. restart the app

If mail is not configured, OTP is still generated and printed in the server console for local testing.

## Deployment

This project can be deployed on Render or PythonAnywhere.

## Notes

- the included database is not required; `init_db.py` can recreate everything
- this project is structured for internship/demo/viva presentation and can be extended further with WhatsApp/SMS gateways, live OTP verification for mobile change, and automated escalation jobs
