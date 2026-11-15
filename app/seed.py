import os

from config import DEFAULTS

from .extensions import db
from .models import DetectionRule, User


def seed_rules():
    # load the default detection rules on first run
    if DetectionRule.query.count():
        return
    for item in DEFAULTS["rules"]:
        db.session.add(DetectionRule(
            key=item["key"], name=item["name"], kind=item["kind"], severity=item["severity"],
            pattern="\n".join(item.get("patterns", [])), threshold=item["threshold"],
            window_seconds=item["window_seconds"], description=item.get("description"),
        ))
    db.session.commit()


def seed_admin():
    # create the first administrator from environment settings
    if User.query.filter_by(role="admin").first():
        return
    email, password = os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")
    if not (email and password):
        return
    admin = User(name=os.getenv("ADMIN_NAME") or "Administrator", email=email.strip().lower(), role="admin")
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(f"Created administrator {admin.email}")
