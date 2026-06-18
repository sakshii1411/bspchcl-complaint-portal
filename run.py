from app import create_app
import os

app = create_app()

# ── Auto-seed on first deploy (runs once when DB is empty) ─────────────────────
def _auto_seed():
    try:
        from extensions import db
        with app.app_context():
            count = db.session.execute(
                db.text("SELECT COUNT(*) FROM complaints")
            ).scalar()
            if count and count > 5:
                print(f"[seed] DB already has {count} complaints — skipping.")
                return
            print("[seed] Empty DB detected — running demo seed...")
            import seed_demo
            seed_demo.seed()
    except Exception as e:
        print(f"[seed] Seed skipped: {e}")

_auto_seed()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=False)
