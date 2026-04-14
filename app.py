from flask import Flask, render_template, request
from config import Config
from extensions import db, migrate, mail, login_manager
from models import User
from datetime import datetime
import os

from utils import get_csrf_token, validate_csrf_token


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from main_routes import main as main_blueprint
    app.register_blueprint(main_blueprint)
    from admin_routes import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'complaints'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profiles'), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)

    # Routes that are public-facing and must work without a pre-established session
    CSRF_EXEMPT = {'/track', '/help'}

    @app.before_request
    def csrf_protect():
        if request.method == 'POST' and request.path not in CSRF_EXEMPT:
            validate_csrf_token()

    @app.context_processor
    def inject_globals():
        return {'current_year': datetime.utcnow().year, 'csrf_token': get_csrf_token}

    @app.errorhandler(400)
    def bad_request(e):
        desc = getattr(e, 'description', None) or 'The request could not be understood by the server.'
        return render_template('errors/500.html', error_code=400, error_title='Bad Request', custom_message=desc), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        import logging
        logging.exception('Internal server error: %s', e)
        return render_template('errors/500.html', error_code=500, error_title='Something Went Wrong',
                               custom_message='An unexpected server error occurred. Our team has been notified.'), 500

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=False)
