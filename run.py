from app import create_app
import os

app = create_app()

def _auto_seed():
    """Seed demo data on first deploy. Uses a DB flag to prevent double-seeding across workers."""
    with app.app_context():
        try:
            from extensions import db
            from sqlalchemy import text, inspect as sa_inspect

            db.create_all()

            tables = sa_inspect(db.engine).get_table_names()
            if 'complaints' not in tables:
                print("[seed] complaints table missing — skipping")
                return

            count = db.session.execute(text("SELECT COUNT(*) FROM complaints")).scalar() or 0
            if count > 5:
                print(f"[seed] Already seeded ({count} complaints) — skipping.")
                return

            # Use advisory lock via users table to prevent race between workers
            user_count = db.session.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
            # If users exist (admin was created by init_db) but complaints = 0, seed safely
            # Insert a sentinel complaint first to block other workers
            try:
                db.session.execute(text(
                    "INSERT INTO complaints (complaint_id, user_id, subject, description, "
                    "category, priority, status, created_at, updated_at) "
                    "SELECT 'SEED_LOCK', id, 'seed', 'seed', 'other', 'low', 'pending', NOW(), NOW() "
                    "FROM users WHERE role='super_admin' LIMIT 1"
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()
                print("[seed] Another worker is seeding — skipping.")
                return

            print(f"[seed] Starting seed (users={user_count}, complaints=0)...")
            import seed_demo
            seed_demo.seed()

            # Remove sentinel
            db.session.execute(text("DELETE FROM complaints WHERE complaint_id='SEED_LOCK'"))
            db.session.commit()

            final = db.session.execute(text("SELECT COUNT(*) FROM complaints")).scalar()
            print(f"[seed] ✅ Complete — {final} complaints in DB.")

        except Exception:
            import traceback
            db.session.rollback()
            print(f"[seed] ERROR:\n{traceback.format_exc()}")

_auto_seed()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=False)
