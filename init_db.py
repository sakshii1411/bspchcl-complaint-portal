from app import app
from extensions import db
from models import User
from utils import generate_consumer_number

ADMIN_EMAIL = 'admin@bsphcl.gov.in'
ADMIN_PASSWORD = 'Admin@2024'

def seed_admin():
    admin = User.query.filter_by(email=ADMIN_EMAIL).first()

    if not admin:
        admin = User(
            name='Super Admin',
            email=ADMIN_EMAIL,
            mobile='9000000001',
            consumer_number=generate_consumer_number(),
            is_admin=True,
            role='super_admin',
            department='Central Control'
        )
        admin.set_password(ADMIN_PASSWORD)
        db.session.add(admin)
    else:
        admin.is_admin = True
        admin.role = 'super_admin'
        admin.department = 'Central Control'

    db.session.commit()

with app.app_context():
    db.create_all()
    seed_admin()
    print('✅ Database tables created.')
    print(f'✅ Admin account ready: {ADMIN_EMAIL} / {ADMIN_PASSWORD}')
    print('✅ Consumers can register themselves from the website.')
