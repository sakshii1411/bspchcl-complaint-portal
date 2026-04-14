from app import app
from extensions import db
from models import User, Complaint
from utils import generate_consumer_number, generate_complaint_id, log_complaint_action
from datetime import datetime, timedelta


def seed_staff():
    staff_accounts = [
        ('Super Admin', 'admin@bsphcl.gov.in', '9000000001', 'super_admin', 'Central Control'),
        ('Complaint Officer', 'officer@bsphcl.gov.in', '9000000002', 'complaint_officer', 'Complaint Desk'),
        ('Operator', 'operator@bsphcl.gov.in', '9000000003', 'operator', 'Call Center'),
        ('Field Staff', 'field@bsphcl.gov.in', '9000000004', 'field_staff', 'Field Unit'),
    ]
    for name, email, mobile, role, department in staff_accounts:
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(name=name, email=email, mobile=mobile, consumer_number=generate_consumer_number(), is_admin=True, role=role, department=department)
            user.set_password('Admin@2024')
            db.session.add(user)
    db.session.commit()


def seed_demo_consumer_and_complaints():
    consumer = User.query.filter_by(email='consumer@example.com').first()
    if not consumer:
        consumer = User(name='Demo Consumer', email='consumer@example.com', mobile='9123456789', district='Patna', address='Demo Address, Patna', consumer_number='BSPHCL-1000000001', role='consumer')
        consumer.set_password('Consumer@2024')
        db.session.add(consumer)
        db.session.commit()

    if Complaint.query.count() == 0:
        for idx, data in enumerate([
            ('Power outage in locality', 'Extended outage since morning in the local distribution line.', 'power_outage', 'high', 'pending'),
            ('High bill amount', 'Bill amount appears higher than average for the last two months.', 'billing', 'medium', 'under_review'),
            ('Meter not recording properly', 'Meter display is unstable and readings are inconsistent.', 'meter_fault', 'medium', 'resolved'),
        ], start=1):
            complaint = Complaint(
                complaint_id=generate_complaint_id(), user_id=consumer.id, subject=data[0], description=data[1],
                category=data[2], priority=data[3], status=data[4], district='Patna',
                consumer_number=consumer.consumer_number, expected_resolution_date=datetime.utcnow() + timedelta(days=idx+1), department='Complaint Desk'
            )
            if data[4] == 'resolved':
                complaint.resolved_at = datetime.utcnow() - timedelta(hours=4)
                complaint.resolution_summary = 'Meter inspection completed and faulty display module replaced.'
            db.session.add(complaint)
            db.session.commit()
            log_complaint_action(complaint, 'seeded', 'Demo complaint inserted for local testing.', None, True)


with app.app_context():
    db.create_all()
    seed_staff()
    seed_demo_consumer_and_complaints()
    print('✅ Database tables created.')
    print('✅ Staff accounts seeded with password: Admin@2024')
    print('✅ Demo consumer created: consumer@example.com / Consumer@2024')
