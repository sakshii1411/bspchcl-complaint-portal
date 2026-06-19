from app import create_app
import os

app = create_app()

# ── Auto-seed demo data on first deploy ────────────────────────────────────────
def _auto_seed():
    with app.app_context():
        try:
            from extensions import db
            from sqlalchemy import text, inspect

            # Make sure all tables exist first
            db.create_all()

            # Check if already seeded
            inspector = inspect(db.engine)
            if 'complaints' not in inspector.get_table_names():
                print("[seed] complaints table missing — skipping seed")
                return

            count = db.session.execute(text("SELECT COUNT(*) FROM complaints")).scalar() or 0
            if count > 5:
                print(f"[seed] Already seeded ({count} complaints) — skipping.")
                return

            print("[seed] Fresh DB detected — running demo seed...")
            import seed_demo
            seed_demo.seed()
            new_count = db.session.execute(text("SELECT COUNT(*) FROM complaints")).scalar()
            print(f"[seed] ✅ Done. {new_count} complaints in DB.")

        except Exception as e:
            import traceback
            print(f"[seed] ERROR:\n{traceback.format_exc()}")

_auto_seed()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=False)
