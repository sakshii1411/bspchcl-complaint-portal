from app import app
from extensions import db
from models import User
from utils import generate_consumer_number
from sqlalchemy import text

ADMIN_EMAIL    = 'admin@bsphcl.gov.in'
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
        admin.is_admin   = True
        admin.role       = 'super_admin'
        admin.department = 'Central Control'
    db.session.commit()
    return admin


def run_demo_seed():
    """Seed 160 demo complaints if DB is empty. Called once after init."""
    try:
        # Clean any stuck sentinel from previous failed attempt
        db.session.execute(
            text("DELETE FROM complaints WHERE complaint_id='SEED_LOCK'")
        )
        db.session.commit()

        count = db.session.execute(
            text("SELECT COUNT(*) FROM complaints")
        ).scalar() or 0

        if count > 5:
            print(f'ℹ️  Demo data already present ({count} complaints) — skipping seed.')
            return

        print('🌱 Seeding demo dataset...')
        import seed_demo
        seed_demo.seed()
        final = db.session.execute(text("SELECT COUNT(*) FROM complaints")).scalar()
        print(f'✅ Demo seed complete — {final} complaints created.')

    except Exception:
        import traceback
        db.session.rollback()
        print(f'⚠️  Demo seed failed (non-fatal):\n{traceback.format_exc()}')


with app.app_context():
    db.create_all()
    print('✅ Database tables created.')

    seed_admin()
    print(f'✅ Admin account ready: {ADMIN_EMAIL} / {ADMIN_PASSWORD}')

    run_demo_seed()

    print('✅ Consumers can register themselves from the website.')
