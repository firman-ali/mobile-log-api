from flask import Blueprint, request, jsonify, current_app, send_from_directory
from ..utils.decorators import require_api_key
from ..services import log_service # Impor dari services package
from .. import limiter # Impor limiter yang sudah diinisialisasi di app/__init__.py

log_bp = Blueprint('logs', __name__)

@log_bp.route('/upload', methods=['POST'])
@require_api_key
@limiter.limit(lambda: current_app.config.get("RATELIMIT_UPLOAD_LOG", "30 per minute")) # Gunakan config untuk limit
def upload_log():
    package_id = request.form.get('package_id')
    device_id = request.form.get('device_id')
    
    if 'log_file' not in request.files:
        return jsonify({"error": "No log_file part in the request"}), 400
    client_log_file = request.files['log_file']
    
    response_data, status_code = log_service.process_log_upload(package_id, device_id, client_log_file)
    return jsonify(response_data), status_code

@log_bp.route('/metadata', methods=['GET'])
@require_api_key
def get_metadata_all():
    """Mengambil semua metadata log."""
    response_data, status_code = log_service.get_all_logs_metadata()
    return jsonify(response_data), status_code
    
@log_bp.route('/metadata/<string:package_id>', methods=['GET'])
@require_api_key
def get_metadata_by_package(package_id):
    """Mengambil metadata log untuk package_id tertentu."""
    response_data, status_code = log_service.get_logs_metadata_for_package(package_id)
    return jsonify(response_data), status_code

@log_bp.route('/view/<string:package_id>/<string:device_id>', methods=['GET'])
@require_api_key
def view_specific_log(package_id, device_id):
    result = log_service.get_log_file_content(package_id, device_id)
    if isinstance(result, tuple) and len(result) == 2: # Sukses, dapat path dan filename
        directory, filename = result
        try:
            return send_from_directory(
                directory,
                filename,
                as_attachment=False,
                mimetype='text/plain'
            )
        except Exception as e:
            current_app.logger.error(f"Error sending file {filename} from {directory}: {e}", exc_info=True)
            return jsonify({"error": f"Could not send file: {str(e)}"}), 500
    else: # Error, result adalah dict
        return jsonify(result), result.get("status_code", 404) # Asumsi error dict punya status_code