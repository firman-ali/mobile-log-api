import os
import datetime
import re
import time
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# --- Konfigurasi Awal ---
UPLOAD_FOLDER = 'uploads'
# Default LOG_RETENTION_DAYS jika tidak ada di DB atau env var
DEFAULT_LOG_RETENTION_DAYS = 30

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///log_metadata.db' # DB yang sama
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db = SQLAlchemy(app)

# --- Model Database ---
# (Model DeviceLogFile tetap sama)
class DeviceLogFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    server_filename = db.Column(db.String(255), nullable=False)
    last_processed_entry_timestamp = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<DeviceLogFile {self.device_id} - {self.server_filename}>'

# Model baru untuk menyimpan pengaturan aplikasi
class AppSetting(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'<AppSetting {self.key}={self.value}>'

# ... (Regex, DATETIME_FORMAT, fungsi parse_timestamp_from_log_entry_str tetap sama) ...
LOG_ENTRY_REGEX = re.compile(
    r"--- API Error Log ---\s*Timestamp: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s*([\s\S]*?)--- End Log Entry ---"
)
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Fungsi Helper untuk Pengaturan ---
def get_log_retention_days():
    """Mengambil durasi retensi log dari database, fallback ke env var, lalu ke default."""
    with app.app_context(): # Pastikan kita dalam konteks aplikasi untuk akses DB
        setting = AppSetting.query.filter_by(key='LOG_RETENTION_DAYS').first()
        if setting and setting.value.isdigit():
            return int(setting.value)
        # Fallback ke environment variable jika tidak ada di DB atau tidak valid
        env_val = os.environ.get('LOG_RETENTION_DAYS')
        if env_val and env_val.isdigit():
            return int(env_val)
        return DEFAULT_LOG_RETENTION_DAYS

def set_log_retention_days(days):
    """Menyimpan durasi retensi log ke database."""
    with app.app_context():
        if not isinstance(days, int) or days <= 0:
            raise ValueError("Retention days must be a positive integer.")
        setting = AppSetting.query.filter_by(key='LOG_RETENTION_DAYS').first()
        if setting:
            setting.value = str(days)
        else:
            setting = AppSetting(key='LOG_RETENTION_DAYS', value=str(days))
            db.session.add(setting)
        db.session.commit()
        app.logger.info(f"Log retention period updated in DB to {days} days.")


# --- Inisialisasi Pengaturan Awal saat Aplikasi Start ---
def initialize_app_settings():
    with app.app_context():
        # Inisialisasi LOG_RETENTION_DAYS jika belum ada di DB
        if not AppSetting.query.filter_by(key='LOG_RETENTION_DAYS').first():
            initial_days = os.environ.get('LOG_RETENTION_DAYS')
            if initial_days and initial_days.isdigit():
                set_log_retention_days(int(initial_days))
                app.logger.info(f"Initialized LOG_RETENTION_DAYS from ENV var to {initial_days} days.")
            else:
                set_log_retention_days(DEFAULT_LOG_RETENTION_DAYS)
                app.logger.info(f"Initialized LOG_RETENTION_DAYS to default {DEFAULT_LOG_RETENTION_DAYS} days.")
        current_retention = get_log_retention_days()
        app.config['CURRENT_LOG_RETENTION_DAYS'] = current_retention # Simpan nilai terkini di app.config untuk referensi


# --- Fungsi Pembersihan Log Lama (Dimodifikasi) ---
def cleanup_old_logs():
    with app.app_context():
        app.logger.info("Starting scheduled log cleanup task...")
        # Ambil nilai terbaru dari DB setiap kali job berjalan
        retention_period_days = get_log_retention_days()
        app.config['CURRENT_LOG_RETENTION_DAYS'] = retention_period_days # Update juga di config jika perlu
        
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_period_days)
        
        app.logger.info(f"Current log retention period: {retention_period_days} days. Cutoff date for old files: {cutoff_date.strftime('%Y-%m-%d')}")

        device_log_files = DeviceLogFile.query.all()
        cleaned_count = 0

        for log_meta in device_log_files:
            server_filename = log_meta.server_filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], server_filename)

            if os.path.exists(filepath):
                try:
                    file_mod_timestamp = os.path.getmtime(filepath)
                    file_mod_date = datetime.datetime.fromtimestamp(file_mod_timestamp)

                    if file_mod_date < cutoff_date:
                        app.logger.info(f"Log file {server_filename} (last modified: {file_mod_date.strftime('%Y-%m-%d')}) is older than {retention_period_days} days. Resetting...")
                        os.remove(filepath)
                        log_meta.last_processed_entry_timestamp = None
                        db.session.add(log_meta)
                        app.logger.info(f"Successfully reset {server_filename}.")
                        cleaned_count += 1
                except Exception as e:
                    app.logger.error(f"Error processing or deleting log file {server_filename}: {e}", exc_info=True)

        if cleaned_count > 0:
            db.session.commit()
            app.logger.info(f"Log cleanup task finished. {cleaned_count} log files were reset.")
        else:
            app.logger.info("Log cleanup task finished. No log files needed resetting.")


# --- Inisialisasi dan Konfigurasi Scheduler (tetap sama) ---
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(cleanup_old_logs, 'cron', hour=2, minute=0)
# scheduler.add_job(cleanup_old_logs, 'interval', minutes=1) # Untuk testing

# --- Endpoint API ---
# (Endpoint /upload_log, /device_logs_metadata, /view_log/<device_id> tetap sama)
@app.route('/upload_log', methods=['POST'])
def upload_log_file():
    # ... (kode endpoint upload_log_file tidak berubah)
    if 'log_file' not in request.files:
        return jsonify({"error": "No log_file part in the request"}), 400
    
    file_from_client = request.files['log_file']
    device_id = request.form.get('device_id')

    if not device_id:
        return jsonify({"error": "Device ID is required"}), 400

    if file_from_client.filename == '':
        return jsonify({"error": "No selected file from client"}), 400

    server_filename = secure_filename(device_id) + ".log"
    server_filepath = os.path.join(app.config['UPLOAD_FOLDER'], server_filename)

    device_log_metadata = DeviceLogFile.query.filter_by(device_id=device_id).first()
    last_known_timestamp_obj = None
    if device_log_metadata and device_log_metadata.last_processed_entry_timestamp:
        last_known_timestamp_obj = device_log_metadata.last_processed_entry_timestamp
        app.logger.info(f"Device ID {device_id}: Last known timestamp is {last_known_timestamp_obj.strftime(DATETIME_FORMAT)}")
    else:
        app.logger.info(f"Device ID {device_id}: No previous log metadata found or no timestamp. Processing all entries.")

    new_entries_appended_count = 0
    current_max_timestamp_in_upload = last_known_timestamp_obj

    try:
        client_log_content = file_from_client.read().decode('utf-8')
        entries_to_append_str = []
        
        for match in LOG_ENTRY_REGEX.finditer(client_log_content):
            timestamp_str = match.group(1)
            full_entry_text = match.group(0) 
            entry_timestamp_obj = parse_timestamp_from_log_entry_str(timestamp_str)

            if not entry_timestamp_obj:
                app.logger.warning(f"Could not parse timestamp: {timestamp_str} for device {device_id}. Skipping entry.")
                continue

            if last_known_timestamp_obj is None or entry_timestamp_obj > last_known_timestamp_obj:
                entries_to_append_str.append(full_entry_text + "\n") 
                new_entries_appended_count += 1
                if current_max_timestamp_in_upload is None or entry_timestamp_obj > current_max_timestamp_in_upload:
                    current_max_timestamp_in_upload = entry_timestamp_obj

        if entries_to_append_str:
            with open(server_filepath, 'a', encoding='utf-8') as f_server:
                for entry_text in entries_to_append_str:
                    f_server.write(entry_text)
            app.logger.info(f"{new_entries_appended_count} new log entries appended for device {device_id} to {server_filename}")
        else:
            app.logger.info(f"No new log entries to append for device {device_id}.")

        if device_log_metadata is None:
            device_log_metadata = DeviceLogFile(
                device_id=device_id,
                server_filename=server_filename,
                last_processed_entry_timestamp=current_max_timestamp_in_upload
            )
            db.session.add(device_log_metadata)
            app.logger.info(f"Created new metadata entry for device {device_id}.")
        elif current_max_timestamp_in_upload and (last_known_timestamp_obj is None or current_max_timestamp_in_upload > last_known_timestamp_obj) :
            device_log_metadata.last_processed_entry_timestamp = current_max_timestamp_in_upload
            app.logger.info(f"Updated last_processed_entry_timestamp for device {device_id} to {current_max_timestamp_in_upload.strftime(DATETIME_FORMAT)}.")
        
        db.session.commit()

        return jsonify({
            "message": f"Log processed. {new_entries_appended_count} new entries appended.",
            "server_filename": server_filename,
            "device_id": device_id,
            "last_processed_timestamp_on_server": current_max_timestamp_in_upload.strftime(DATETIME_FORMAT) if current_max_timestamp_in_upload else (last_known_timestamp_obj.strftime(DATETIME_FORMAT) if last_known_timestamp_obj else None)
        }), 200

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error processing log for device {device_id}: {e}", exc_info=True)
        return jsonify({"error": f"Could not process log file: {str(e)}"}), 500

@app.route('/device_logs_metadata', methods=['GET'])
def get_device_logs_metadata():
    # ... (kode endpoint device_logs_metadata tidak berubah)
    try:
        entries = DeviceLogFile.query.all()
        results = [
            {
                "device_id": entry.device_id,
                "server_filename": entry.server_filename,
                "last_processed_entry_timestamp": entry.last_processed_entry_timestamp.strftime(DATETIME_FORMAT) if entry.last_processed_entry_timestamp else None
            } for entry in entries
        ]
        return jsonify(results), 200
    except Exception as e:
        app.logger.error(f"Error fetching device logs metadata: {e}", exc_info=True)
        return jsonify({"error": f"Could not fetch metadata: {str(e)}"}), 500


@app.route('/view_log/<string:device_id>', methods=['GET'])
def view_log_file(device_id): # <--- KEMBALIKAN NAMA PARAMETER KE device_id
    if not device_id: # Gunakan device_id
        return jsonify({"error": "Device ID is required"}), 400

    # Tentukan nama file di server berdasarkan device_id
    server_filename = secure_filename(device_id) + ".log" # Gunakan device_id
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], server_filename)

    app.logger.info(f"Attempting to view log file for Device ID: {device_id} at path: {filepath}") # Gunakan device_id

    if os.path.exists(filepath):
        try:
            return send_from_directory(
                app.config['UPLOAD_FOLDER'],
                server_filename,
                as_attachment=False, 
                mimetype='text/plain'
            )
        except Exception as e:
            app.logger.error(f"Error sending file {server_filename} for device {device_id}: {e}", exc_info=True) # Gunakan device_id
            return jsonify({"error": f"Could not send file: {str(e)}"}), 500
    else:
        app.logger.warning(f"Log file not found for Device ID: {device_id} at path: {filepath}") # Gunakan device_id
        return jsonify({"error": "Log file not found for this device ID"}), 404

def parse_timestamp_from_log_entry_str(timestamp_str):
    # ... (kode fungsi parse_timestamp_from_log_entry_str tidak berubah)
    try:
        return datetime.datetime.strptime(timestamp_str, DATETIME_FORMAT)
    except ValueError:
        try:
            return datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
# --- Endpoint API Baru untuk Mengatur Durasi Retensi Log ---
@app.route('/api/settings/log_retention', methods=['GET', 'POST'])
def manage_log_retention_settings():
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'days' not in data:
            return jsonify({"error": "Missing 'days' in request body"}), 400
        
        try:
            days = int(data['days'])
            set_log_retention_days(days)
            # Update juga nilai di app.config agar konsisten untuk sesi saat ini jika ada yang merujuk ke sana
            app.config['CURRENT_LOG_RETENTION_DAYS'] = days
            return jsonify({"message": f"Log retention period set to {days} days."}), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            app.logger.error(f"Error updating log retention setting: {e}", exc_info=True)
            return jsonify({"error": "Failed to update log retention setting"}), 500

    elif request.method == 'GET':
        try:
            days = get_log_retention_days()
            return jsonify({"log_retention_days": days}), 200
        except Exception as e:
            app.logger.error(f"Error fetching log retention setting: {e}", exc_info=True)
            return jsonify({"error": "Failed to fetch log retention setting"}), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Pastikan tabel AppSetting juga dibuat
        initialize_app_settings() # Inisialisasi pengaturan saat pertama kali jalan

    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        if not scheduler.running:
            scheduler.start()
            app.logger.info("APScheduler started for log cleanup.")
        else:
            app.logger.info("APScheduler already running.")
    else:
        app.logger.info("APScheduler not started in Flask debug reloader process or not main.")

    import logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO)
    
    current_retention_on_startup = app.config.get('CURRENT_LOG_RETENTION_DAYS', 'N/A')
    app.logger.info(f"Flask App Starting... Current log retention set to {current_retention_on_startup} days.")
    app.run(host='0.0.0.0', port=5000, debug=True)