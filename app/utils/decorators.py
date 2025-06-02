from functools import wraps
from flask import request, jsonify, current_app

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        expected_key = current_app.config.get('EXPECTED_API_KEY')
        
        if not api_key or api_key != expected_key:
            current_app.logger.warning(
                f"Unauthorized API access attempt. Remote IP: {request.remote_addr}, Provided key: '{api_key}'"
            )
            return jsonify({"error": "Unauthorized: Invalid or missing API Key"}), 401
        return f(*args, **kwargs)
    return decorated_function