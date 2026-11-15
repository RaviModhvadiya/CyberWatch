from . import admin, alerts, auth, logs, main, reports


def register_blueprints(app):
    # attach every blueprint to the app
    for module in (auth, main, logs, alerts, reports, admin):
        app.register_blueprint(module.bp)
