import os
import datetime
import re
from flask import current_app, jsonify
from werkzeug.utils import secure_filename
from ..models import db, DeviceLogFile

# Regex dan format datetime bisa dipindah ke modul utilitas jika digunakan di banyak tempat
LOG_ENTRY_REGEX = re.compile(
    r"--- API Error Log ---\s*Timestamp: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s*([\s\S]*?)--- End Log Entry ---"
)
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f" # Format dari Flutter termasuk milidetik

def parse_timestamp_from_log_entry_str(timestamp_str):
    try:
        return datetime.datetime.strptime(timestamp_str, DATETIME_FORMAT)
    except ValueError:
        try: # Fallback jika milidetik tidak ada (seharusnya tidak terjadi jika Flutter konsisten)
            return datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

def process_log_upload(package_id, device_id, client_log_file):
    """Memproses unggahan file log dari klien."""
    if not package_id:
        return {"error": "Package ID is required"}, 400
    if not device_id:
        return {"error": "Device ID is required"}, 400
    if not client_log_file or client_log_file.filename == '':
        return {"error": "No log file part in the request or no selected file"}, 400

    # Struktur folder: uploads/<package_id>/<device_id>.log
    # Nama file di server hanya berdasarkan device_id karena sudah di dalam folder package_id
    server_filename_base = secure_filename(device_id) + ".log"
    
    package_upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(package_id))
    if not os.path.exists(package_upload_folder):
        try:
            os.makedirs(package_upload_folder)
            current_app.logger.info(f"Created upload directory for package: {package_upload_folder}")
        except OSError as e:
            current_app.logger.error(f"Could not create directory {package_upload_folder}: {e}", exc_info=True)
            return {"error": f"Server error: Could not create storage directory for package."}, 500
            
    server_filepath = os.path.join(package_upload_folder, server_filename_base)

    device_log_metadata = DeviceLogFile.query.filter_by(package_id=package_id, device_id=device_id).first()
    last_known_timestamp_obj = None
    if device_log_metadata and device_log_metadata.last_processed_entry_timestamp:
        last_known_timestamp_obj = device_log_metadata.last_processed_entry_timestamp
        current_app.logger.info(
            f"Package {package_id}, Device {device_id}: Last known timestamp is {last_known_timestamp_obj.strftime(DATETIME_FORMAT)}"
        )
    else:
        current_app.logger.info(
            f"Package {package_id}, Device {device_id}: No previous log metadata or no timestamp. Processing all entries."
        )

    new_entries_appended_count = 0
    current_max_timestamp_in_upload = last_known_timestamp_obj # Inisialisasi dengan timestamp terakhir yang diketahui

    try:
        client_log_content = client_log_file.read().decode('utf-8')
        entries_to_append_str = []
        
        for match in LOG_ENTRY_REGEX.finditer(client_log_content):
            timestamp_str = match.group(1)
            full_entry_text = match.group(0) 
            entry_timestamp_obj = parse_timestamp_from_log_entry_str(timestamp_str)

            if not entry_timestamp_obj:
                current_app.logger.warning(
                    f"Could not parse timestamp: {timestamp_str} for package {package_id}, device {device_id}. Skipping entry."
                )
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
            current_app.logger.info(
                f"{new_entries_appended_count} new log entries appended for package {package_id}, device {device_id} to {server_filepath}"
            )
        else:
            current_app.logger.info(f"No new log entries to append for package {package_id}, device {device_id}.")

        # Update atau buat metadata di DB
        if device_log_metadata is None:
            device_log_metadata = DeviceLogFile(
                package_id=package_id,
                device_id=device_id,
                server_filename=server_filename_base, # Simpan hanya nama file, bukan path lengkap
                last_processed_entry_timestamp=current_max_timestamp_in_upload
            )
            db.session.add(device_log_metadata)
            current_app.logger.info(f"Created new metadata entry for package {package_id}, device {device_id}.")
        elif current_max_timestamp_in_upload and \
             (last_known_timestamp_obj is None or current_max_timestamp_in_upload > last_known_timestamp_obj):
            device_log_metadata.last_processed_entry_timestamp = current_max_timestamp_in_upload
            device_log_metadata.updated_at = datetime.datetime.utcnow() # Update manual jika tidak otomatis
            current_app.logger.info(
                f"Updated last_processed_entry_timestamp for package {package_id}, device {device_id} to "
                f"{current_max_timestamp_in_upload.strftime(DATETIME_FORMAT)}."
            )
        
        db.session.commit()

        return {
            "message": f"Log processed. {new_entries_appended_count} new entries appended.",
            "package_id": package_id,
            "device_id": device_id,
            "server_filename_stored": server_filename_base,
            "last_processed_timestamp_on_server": current_max_timestamp_in_upload.strftime(DATETIME_FORMAT) if current_max_timestamp_in_upload else (last_known_timestamp_obj.strftime(DATETIME_FORMAT) if last_known_timestamp_obj else None)
        }, 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing log for package {package_id}, device {device_id}: {e}", exc_info=True)
        return {"error": f"Could not process log file: {str(e)}"}, 500


def get_logs_metadata_for_package(package_id):
    """Mengambil metadata log untuk package_id tertentu."""
    if not package_id:
        return {"error": "Package ID is required"}, 400
    
    entries = DeviceLogFile.query.filter_by(package_id=package_id).all()
    if not entries:
         return {"message": f"No log metadata found for package ID: {package_id}"}, 404
    
    results = [
        {
            "package_id": entry.package_id,
            "device_id": entry.device_id,
            "server_filename": entry.server_filename, # Ini hanya nama file, bukan path
            "last_processed_entry_timestamp": entry.last_processed_entry_timestamp.strftime(DATETIME_FORMAT) if entry.last_processed_entry_timestamp else None,
            "created_at": entry.created_at.isoformat() + "Z",
            "updated_at": entry.updated_at.isoformat() + "Z"
        } for entry in entries
    ]
    return results, 200

def get_all_logs_metadata():
    """Mengambil semua metadata log."""
    entries = DeviceLogFile.query.all()
    if not entries:
         return {"message": "No log metadata found."}, 404
    results = [
        {
            "package_id": entry.package_id,
            "device_id": entry.device_id,
            "server_filename": entry.server_filename,
            "last_processed_entry_timestamp": entry.last_processed_entry_timestamp.strftime(DATETIME_FORMAT) if entry.last_processed_entry_timestamp else None,
            "created_at": entry.created_at.isoformat() + "Z",
            "updated_at": entry.updated_at.isoformat() + "Z"
        } for entry in entries
    ]
    return results, 200

def get_log_file_content(package_id, device_id):
    """Mengambil konten file log tertentu."""
    if not package_id:
        return {"error": "Package ID is required"}, 400
    if not device_id:
        return {"error": "Device ID is required"}, 400

    # Cari metadata untuk mendapatkan nama file yang benar
    log_meta = DeviceLogFile.query.filter_by(package_id=package_id, device_id=device_id).first()
    if not log_meta:
        current_app.logger.warning(f"Log metadata not found for package {package_id}, device {device_id}")
        return {"error": "Log file metadata not found for this package and device ID"}, 404

    server_filename_base = log_meta.server_filename # Ini adalah device_id.log
    package_upload_folder_name = secure_filename(package_id) # Nama folder package
    
    # Path ke file log di server
    # filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], package_upload_folder_name, server_filename_base)
    # current_app.logger.info(f"Attempting to view log file for package {package_id}, device {device_id} at path: {filepath}")

    # send_from_directory memerlukan path relatif dari UPLOAD_FOLDER jika UPLOAD_FOLDER adalah root
    # Atau, kita bisa berikan path absolut ke direktori package.
    # Mari gunakan path absolut ke direktori package untuk send_from_directory

    package_specific_upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], package_upload_folder_name)

    if os.path.exists(os.path.join(package_specific_upload_dir, server_filename_base)):
        return package_specific_upload_dir, server_filename_base # Kembalikan dir dan nama file untuk send_from_directory
    else:
        current_app.logger.warning(f"Log file not found on disk: {os.path.join(package_specific_upload_dir, server_filename_base)}")
        return {"error": "Log file not found on disk for this package and device ID"}, 404