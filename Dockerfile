FROM python:3.9-slim-bullseye

# Set variabel environment untuk Python agar tidak buffer output dan untuk path
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH /app

# Set direktori kerja di dalam container
WORKDIR /app

# Buat user non-root untuk keamanan
# GID dan UID bisa disesuaikan jika perlu mencocokkan host untuk volume
RUN groupadd -r appgroup --gid=1001 && useradd --no-log-init -r -g appgroup --uid=1001 appuser

# Salin file requirements terlebih dahulu untuk memanfaatkan Docker cache
COPY requirements.txt .

# Install dependencies
# --no-cache-dir mengurangi ukuran image
# --compile mencegah pembuatan file .pyc yang tidak selalu diperlukan di container
RUN pip install --no-cache-dir --compile -r requirements.txt

# Salin seluruh kode aplikasi ke direktori kerja
COPY . .

# Buat direktori yang mungkin diperlukan oleh aplikasi jika belum ada
# dan pastikan user non-root memiliki izin
# uploads dan instance akan di-mount sebagai volume, tapi direktori di container harus ada
RUN mkdir -p /app/uploads /app/instance && \
    chown -R appuser:appgroup /app/uploads /app/instance /app

# Ganti ke user non-root
USER appuser

# Expose port yang digunakan oleh Flask (sesuai dengan yang di run.py)
EXPOSE 5000

# Perintah untuk menjalankan aplikasi saat container dimulai
# Menggunakan gunicorn direkomendasikan untuk produksi daripada server development Flask
# CMD ["gunicorn", "-b", "0.0.0.0:5000", "run:app"]
# Untuk development atau jika gunicorn belum disiapkan:
CMD ["python", "run.py"]