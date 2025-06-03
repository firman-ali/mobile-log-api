import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from apscheduler.schedulers.background import BackgroundScheduler

from .config import config # Impor dictionary konfigurasi

# Inisialisasi ekstensi di luar factory agar bisa diimpor di modul lain
db = SQLAlchemy()
limiter = Limiter(
    key_func=get_remote_address,
    # default_limits akan diambil dari app.config nanti
)
scheduler = BackgroundScheduler(daemon=True)

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')

    app = Flask(__name__, instance_relative_config=False) 
    app.config.from_object(config[config_name])
    # Panggil init_app dari kelas Config SETELAH from_object
    # agar app.logger sudah ada dan bisa dikonfigurasi oleh init_app
    config[config_name].init_app(app) 

    db.init_app(app)
    # Set default limits untuk limiter dari config SETELAH app.config dimuat
    limiter.init_app(app)
    # Flask-Limiter akan membaca konfigurasinya (seperti RATELIMIT_STORAGE_URL) dari app.config
    # jadi tidak perlu diatur manual di sini jika sudah ada di Config.
    
    # Registrasi Blueprint
    from .routes.log_routes import log_bp
    from .routes.setting_routes import setting_bp
    
    app.register_blueprint(log_bp, url_prefix='/api/v1/logs') 
    app.register_blueprint(setting_bp, url_prefix='/api/v1/settings')

    with app.app_context():
        db.create_all() 
        
        from .services.setting_service import initialize_app_settings_on_startup
        initialize_app_settings_on_startup(app) 

        if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            if not scheduler.running:
                from .utils.scheduler_tasks import schedule_cleanup_job
                schedule_cleanup_job(app, scheduler) 
                try:
                    scheduler.start()
                    app.logger.info("APScheduler started for log cleanup.")
                except Exception as e: 
                    app.logger.warning(f"APScheduler already running or failed to start: {e}")
        else:
            app.logger.info("APScheduler not started in Flask debug reloader process (or not main process).")
            
    app.logger.info(f"Application '{app.name}' created with config '{config_name}'.") 
    return app