# Gunakan base image Python
FROM python:3.13-slim

# Set direktori kerja
WORKDIR /app

# Salin file requirements dan install dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Salin seluruh kode aplikasi ke direktori kerja
COPY . .

# Buat direktori uploads di dalam container
RUN mkdir -p /app/uploads
# Direktori instance untuk SQLite akan dibuat oleh Flask/SQLAlchemy jika tidak ada,
# tapi jika Anda ingin memetakannya ke volume, pastikan ada.
RUN mkdir -p /app/instance 

# Expose port yang digunakan oleh Flask
EXPOSE 5000

# Perintah untuk menjalankan aplikasi
CMD ["python", "app.py"]