import os
from app import create_app # Impor factory create_app dari package app
import logging

# Muat environment variables dari .env jika ada (baik untuk development)
# from dotenv import load_dotenv
# load_dotenv()

# Gunakan environment variable untuk menentukan mode debug
# Atau set secara eksplisit di sini untuk development
is_debug = os.environ.get("FLASK_DEBUG", "True").lower() == "true"

app = create_app() # config_name akan diambil dari FLASK_CONFIG env var atau default

if __name__ == '__main__':
    # Konfigurasi logging dasar untuk root logger jika tidak dalam mode debug Flask
    # app.logger akan dikonfigurasi di Config.init_app
    if not app.debug: 
        logging.basicConfig(
            level=app.config.get('LOG_LEVEL', 'INFO'), 
            format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )
    
    app.logger.info(f"Flask App Starting in {'DEBUG' if app.debug else 'PRODUCTION'} mode...")
    app.logger.info(f"Log retention (on startup) currently set to {app.config.get('CURRENT_LOG_RETENTION_DAYS', 'N/A')} days.")
    
    # Port bisa juga dari environment variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=app.debug)