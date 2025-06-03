import os
from flask import current_app
from ..models import AppSetting, db # Impor model dan db

def get_log_retention_days_from_db():
    """Mengambil durasi retensi log dari database."""
    setting = AppSetting.query.filter_by(key='LOG_RETENTION_DAYS').first()
    if setting and setting.value.isdigit():
        return int(setting.value)
    # Fallback ke environment variable jika tidak ada di DB atau tidak valid
    env_val = current_app.config.get('DEFAULT_LOG_RETENTION_DAYS') # Ambil dari config yang sudah load env
    return int(env_val)


def set_log_retention_days_in_db(days):
    """Menyimpan durasi retensi log ke database."""
    if not isinstance(days, int) or days <= 0:
        raise ValueError("Retention days must be a positive integer.")
    
    setting = AppSetting.query.filter_by(key='LOG_RETENTION_DAYS').first()
    if setting:
        setting.value = str(days)
    else:
        setting = AppSetting(key='LOG_RETENTION_DAYS', value=str(days))
        db.session.add(setting)
    db.session.commit()
    current_app.logger.info(f"Log retention period updated in DB to {days} days.")
    # Update juga nilai di app.config agar konsisten untuk sesi saat ini
    current_app.config['CURRENT_LOG_RETENTION_DAYS'] = days


def initialize_app_settings_on_startup(app_instance):
    """Dipanggil saat aplikasi dimulai untuk memastikan pengaturan ada di DB."""
    with app_instance.app_context(): # Gunakan konteks dari app_instance yang di-pass
        # Inisialisasi LOG_RETENTION_DAYS jika belum ada di DB
        if not AppSetting.query.filter_by(key='LOG_RETENTION_DAYS').first():
            # Ambil dari config yang sudah memproses env var atau default
            initial_days = app_instance.config.get('DEFAULT_LOG_RETENTION_DAYS')
            
            # Cek juga env var LOG_API_KEY secara langsung jika ingin override default di config
            env_retention_days = os.environ.get('LOG_RETENTION_DAYS')
            if env_retention_days and env_retention_days.isdigit():
                 initial_days = int(env_retention_days)

            set_log_retention_days_in_db(int(initial_days)) # Pastikan int
            app_instance.logger.info(f"Initialized LOG_RETENTION_DAYS in DB to {initial_days} days.")
        
        # Simpan nilai terkini (dari DB atau default) ke app.config untuk akses mudah
        current_retention = get_log_retention_days_from_db()
        app_instance.config['CURRENT_LOG_RETENTION_DAYS'] = current_retention