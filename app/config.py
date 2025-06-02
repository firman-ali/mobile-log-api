import os
import logging
from datetime import timedelta

# Path dasar proyek (log_api/)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'supersecretpassword'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'log_metadata.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Uploads
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Pengaturan Aplikasi
    DEFAULT_LOG_RETENTION_DAYS = int(os.environ.get('DEFAULT_LOG_RETENTION_DAYS', 30))
    EXPECTED_API_KEY = os.environ.get("LOG_API_KEY") or "ganti-dengan-api-key-rahasia-anda"
    
    # Flask-Limiter
    RATELIMIT_STORAGE_URL = os.environ.get("RATELIMIT_STORAGE_URL", "memory://") # Gunakan "redis://localhost:6379/0" untuk produksi
    RATELIMIT_STRATEGY = "fixed-window" # atau "moving-window"
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_DEFAULT = "200 per day;50 per hour;10 per minute" # Default limit untuk semua route
    RATELIMIT_UPLOAD_LOG = "30 per minute;500 per hour" # Limit khusus untuk upload

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

    @staticmethod
    def init_app(app):
        # Bagian A: Konfigurasi logger aplikasi (app.logger) terlebih dahulu
        app.logger.setLevel(app.config['LOG_LEVEL'])
        
        # Kondisi untuk menambahkan handler, hati-hati dengan reloader Flask
        # Hanya tambahkan handler jika kita berada di proses utama Werkzeug reloader atau tidak dalam mode debug
        if not app.logger.handlers or (os.environ.get("WERKZEUG_RUN_MAIN") == "true" and not app.logger.handlers):
            # Jika kita berada di proses utama reloader dan sudah ada handler (misalnya dari setup sebelumnya yang salah),
            # kita bisa memilih untuk membersihkannya atau tidak. Untuk sekarang, kita hanya tambahkan jika belum ada.
            if os.environ.get("WERKZEUG_RUN_MAIN") == "true" and app.logger.handlers:
                 app.logger.handlers.clear() # Bersihkan handler yang mungkin ada dari child process reloader

            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s %(levelname)s: %(name)s: %(message)s [in %(pathname)s:%(lineno)d]')
            handler.setFormatter(formatter)
            app.logger.addHandler(handler)
            # Catat pesan ini SETELAH handler ditambahkan
            app.logger.info(f"Custom logging handler configured for '{app.name}' by Config.init_app.")
        elif app.debug and app.logger.handlers:
            # Jika dalam mode debug dan handler sudah ada (kemungkinan dari Flask sendiri)
            app.logger.info(f"Using existing (likely Flask debug) logger handlers for '{app.name}'.")
        elif not app.logger.handlers and app.debug:
            # Jika dalam mode debug dan belum ada handler (Flask akan menambahkannya nanti)
            app.logger.info(f"No handlers on app.logger in debug mode yet; Flask will likely add its own. Log messages from init_app might not be visible until then.")
        else: # Mode non-debug dan handler sudah ada (mungkin dari propagasi root logger)
            app.logger.info(f"Logging for '{app.name}' seems already configured or will propagate.")

        # Bagian B: Lakukan operasi lain yang mungkin mencatat log, SEKARANG setelah logger dikonfigurasi
        # 1. Buat direktori UPLOAD_FOLDER jika belum ada
        upload_dir = app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_dir):
            try:
                os.makedirs(upload_dir)
                app.logger.info(f"Created upload folder: {upload_dir}") # Sekarang aman untuk log
            except OSError as e:
                app.logger.error(f"Failed to create upload folder {upload_dir}: {e}") # Sekarang aman untuk log
                raise 
        
        # 2. Untuk SQLite, pastikan direktori 'instance' standar di dalam BASE_DIR ada.
        if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite:///'):
            standard_instance_dir = os.path.join(BASE_DIR, 'instance')
            if not os.path.exists(standard_instance_dir):
                try:
                    os.makedirs(standard_instance_dir)
                    app.logger.info(f"Created standard instance directory: {standard_instance_dir}") # Sekarang aman untuk log
                except OSError as e:
                    app.logger.error(f"Failed to create standard instance directory {standard_instance_dir}: {e}") # Sekarang aman untuk log
                    raise

class DevelopmentConfig(Config):
    DEBUG = True
    # SQLALCHEMY_ECHO = True # Untuk melihat query SQL yang dijalankan

class ProductionConfig(Config):
    DEBUG = False
    # Pastikan RATELIMIT_STORAGE_URL menggunakan Redis atau backend persisten lainnya di produksi

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}