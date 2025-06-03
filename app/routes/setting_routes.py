from flask import Blueprint, request, jsonify, current_app
from ..utils.decorators import require_api_key
from ..services import setting_service # Impor dari services package

setting_bp = Blueprint('settings', __name__)

@setting_bp.route('/log_retention', methods=['GET', 'POST'])
@require_api_key
def manage_log_retention():
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'days' not in data:
            return jsonify({"error": "Missing 'days' in request body"}), 400
        
        try:
            days = int(data['days'])
            setting_service.set_log_retention_days_in_db(days)
            return jsonify({"message": f"Log retention period set to {days} days."}), 200
        except ValueError as e: # Tangkap error spesifik dari service
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            current_app.logger.error(f"Error updating log retention setting: {e}", exc_info=True)
            return jsonify({"error": "Failed to update log retention setting"}), 500

    elif request.method == 'GET':
        try:
            days = setting_service.get_log_retention_days_from_db()
            return jsonify({"log_retention_days": days}), 200
        except Exception as e:
            current_app.logger.error(f"Error fetching log retention setting: {e}", exc_info=True)
            return jsonify({"error": "Failed to fetch log retention setting"}), 500