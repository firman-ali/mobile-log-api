import os
import datetime
from flask import current_app # Gunakan current_app jika fungsi dipanggil dalam konteks request atau app
from ..models import db, DeviceLogFile
from ..services.setting_service import get_log_retention_days_from_db # Impor fungsi dari service

def cleanup_old_logs_task(app_instance): # Terima app_instance
    """Tugas yang dijalankan oleh scheduler untuk membersihkan log lama."""
    with app_instance.app_context(): # Gunakan konteks dari app_instance
        current_app.logger.info("Starting scheduled log cleanup task...")
        retention_period_days = get_log_retention_days_from_db()
        
        # Update juga di config jika perlu untuk referensi lain
        current_app.config['CURRENT_LOG_RETENTION_DAYS'] = retention_period_days 
        
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=retention_period_days)
        
        current_app.logger.info(f"Current log retention period: {retention_period_days} days. Cutoff date for old files: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        # Ambil semua metadata file log
        # Kita akan cek tanggal modifikasi file, bukan last_processed_entry_timestamp,
        # karena file bisa saja tidak diupdate tapi masih dalam periode retensi.
        # Namun, jika file sangat besar dan hanya di-append, last_processed_entry_timestamp bisa jadi acuan kapan data terakhir masuk.
        # Untuk kesederhanaan, kita gunakan tanggal modifikasi file fisik.
        
        device_log_files_metadata = DeviceLogFile.query.all()
        cleaned_count = 0
        upload_folder = current_app.config['UPLOAD_FOLDER']

        for log_meta in device_log_files_metadata:
            # Pastikan path file log dibuat dengan benar, termasuk subdirektori package_id
            # Jika struktur folder: uploads/package_id/device_id.log
            # server_filename di DB seharusnya hanya device_id.log
            # atau server_filename di DB adalah path relatif: package_id/device_id.log
            # Mari kita asumsikan server_filename di DB adalah nama file unik (misal package_id_device_id.log)
            # dan disimpan langsung di UPLOAD_FOLDER.
            # Jika Anda membuat subfolder per package_id, logika path perlu disesuaikan.
            
            # Asumsi: server_filename di DB adalah nama file unik seperti "com.app.1_device123.log"
            # Jika Anda membuat struktur folder uploads/com.app.1/device123.log, maka:
            # filepath = os.path.join(upload_folder, log_meta.package_id, log_meta.server_filename)
            # Untuk saat ini, kita anggap server_filename sudah termasuk package_id jika diperlukan untuk keunikan,
            # atau kita buat subfolder. Mari buat subfolder.

            package_upload_folder = os.path.join(upload_folder, log_meta.package_id)
            filepath = os.path.join(package_upload_folder, log_meta.server_filename) # server_filename di DB adalah device_id.log

            if os.path.exists(filepath):
                try:
                    file_mod_timestamp = os.path.getmtime(filepath)
                    file_mod_date = datetime.datetime.utcfromtimestamp(file_mod_timestamp) # Gunakan UTC

                    if file_mod_date < cutoff_date:
                        current_app.logger.info(
                            f"Log file {filepath} (last modified: {file_mod_date.strftime('%Y-%m-%d %H:%M:%S UTC')}) "
                            f"is older than {retention_period_days} days. Resetting..."
                        )
                        
                        os.remove(filepath) # Hapus file fisik
                        
                        # Reset timestamp di database
                        log_meta.last_processed_entry_timestamp = None
                        # db.session.delete(log_meta) # Atau hapus entri metadata juga? Untuk saat ini reset timestamp.
                        db.session.add(log_meta) # Tandai untuk di-update
                        
                        current_app.logger.info(f"Successfully reset (deleted file and updated metadata for) {filepath}.")
                        cleaned_count += 1
                except Exception as e:
                    current_app.logger.error(f"Error processing or deleting log file {filepath}: {e}", exc_info=True)
            # else:
            #     current_app.logger.warning(f"Log file {filepath} for package {log_meta.package_id}, device {log_meta.device_id} not found on disk during cleanup.")

        if cleaned_count > 0:
            db.session.commit() # Commit semua perubahan DB sekaligus
            current_app.logger.info(f"Log cleanup task finished. {cleaned_count} log files were reset.")
        else:
            current_app.logger.info("Log cleanup task finished. No log files needed resetting.")


def schedule_cleanup_job(app_instance, scheduler_instance):
    """Menambahkan tugas pembersihan ke scheduler."""
    # Jalankan setiap hari jam 02:00 subuh server time (asumsi UTC jika server UTC)
    scheduler_instance.add_job(
        func=cleanup_old_logs_task,
        args=[app_instance], # Pass instance aplikasi ke tugas
        trigger='cron',
        hour=2,
        minute=0,
        id='cleanup_old_logs_daily', # ID unik untuk job
        replace_existing=True
    )
    app_instance.logger.info("Scheduled daily log cleanup job for 02:00 server time.")
    # Untuk testing:
    # scheduler_instance.add_job(func=cleanup_old_logs_task, args=[app_instance], trigger='interval', minutes=1, id='cleanup_old_logs_interval', replace_existing=True)
    # app_instance.logger.info("Scheduled interval log cleanup job for every 1 minute (for testing).")