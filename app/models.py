from . import db # Impor db dari __init__.py di package app
import datetime

class AppSetting(db.Model):
    __tablename__ = 'app_settings'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'<AppSetting {self.key}={self.value}>'

class DeviceLogFile(db.Model):
    __tablename__ = 'device_log_files'
    id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(db.String(150), nullable=False, index=True) # ID Paket Aplikasi
    device_id = db.Column(db.String(100), nullable=False, index=True)
    server_filename = db.Column(db.String(300), nullable=False) # Hanya nama file (misal, device_id.log)
    last_processed_entry_timestamp = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Constraint unik untuk kombinasi package_id dan device_id
    __table_args__ = (db.UniqueConstraint('package_id', 'device_id', name='uq_package_device'),)

    def __repr__(self):
        return f'<DeviceLogFile package:{self.package_id} device:{self.device_id} file:{self.server_filename}>'