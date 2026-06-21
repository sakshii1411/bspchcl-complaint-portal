from app import create_app
import os

app = create_app()


def _auto_seed():
    """Seed demo data on first deploy. Idempotent and race-safe."""
    with app.app_context():
        try:
            from extensions import db
            from sqlalchemy import text, inspect as sa_inspect

            # Ensure all tables exist
            db.create_all()

            tables = sa_inspect(db.engine).get_table_names()
            if 'complaints' not in tables:
                print("[seed] complaints table not found — skipping")
                return

            # Clean up any stuck sentinel from a previous failed attempt
            db.session.execute(
                text("DELETE FROM complaints WHERE complaint_id='SEED_LOCK'")
            )
            db.session.commit()

            # Count real complaints (not sentinel)
            count = db.session.execute(
                text("SELECT COUNT(*) FROM complaints WHERE complaint_id != 'SEED_LOCK'")
            ).scalar() or 0

            if count > 5:
                print(f"[seed] DB has {count} complaints — skipping seed.")
                return

            # Try to grab the lock — insert sentinel atomically
            try:
                # Get admin user id for FK constraint
                admin_id = db.session.execute(
                    text("SELECT id FROM users WHERE role='super_admin' LIMIT 1")
                ).scalar()

                if not admin_id:
                    print("[seed] No admin user found yet — skipping (init_db may not have run)")
                    return

                db.session.execute(text(
                    "INSERT INTO complaints "
                    "(complaint_id, user_id, subject, description, category, priority, status, created_at, updated_at) "
                    "VALUES ('SEED_LOCK', :uid, 'seed', 'seed', 'other', 'low', 'pending', NOW(), NOW())"
                ), {"uid": admin_id})
                db.session.commit()
                print("[seed] Lock acquired. Starting seed...")
            except Exception as lock_err:
                db.session.rollback()
                print(f"[seed] Could not acquire lock (another worker seeding?): {lock_err}")
                return

            # Run the actual seed
            try:
                import seed_demo
                seed_demo.seed()
                final = db.session.execute(
                    text("SELECT COUNT(*) FROM complaints WHERE complaint_id != 'SEED_LOCK'")
                ).scalar()
                print(f"[seed] ✅ Seeded successfully — {final} complaints in DB.")
            finally:
                # Always release the lock sentinel
                db.session.execute(
                    text("DELETE FROM complaints WHERE complaint_id='SEED_LOCK'")
                )
                db.session.commit()

        except Exception:
            import traceback
            try:
                db.session.rollback()
            except Exception:
                pass
            print(f"[seed] ERROR:\n{traceback.format_exc()}")


_auto_seed()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5001)),
        debug=False
    )
