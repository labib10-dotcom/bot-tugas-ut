from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import requests
import os

app = Flask(__name__)

#---Konfigurasi---
TELEGRAM = "8673125788:AAE0TkVzvG0SIl3kJCGLmQUfhrkrMXZLD-s"
CHAT_ID = "1098028798"
DB_CONFIG = {
    "host": os.environ.get("DB_HOST"),
    "user": os.environ.get("DB_USER"),
    "port": int(os.environ.get("DB_PORT", 21890)),
    "password": os.environ.get("DB_PASS"),
    "database": os.environ.get("DB_NAME", "defaultdb"),
}

def kirim_notif_telegram(pesan):
    url = f"https://api.telegram.org/bot{TELEGRAM}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": pesan}
    try:
        requests.post(url, json=data)
    except Exception as e:
        print(f"Gagal kirim Telegram: {e}")

@app.route('/update-tugas', methods=['GET', 'POST'])
def update_tugas():
    # PAKAI 'request' (tanpa S) untuk ambil data masuk
    try:
        data = request.get_json(force=True, silent=True)
        print(f"DEBUG: Data JSON Terurai -> {data}")
        
        if not data:
            return jsonify({"status": "error", "message": "JSON tidak terbaca"}), 400

        nama = data.get('nama_tugas')
        status = data.get('status')

        #Simpan ke Database
        db = mysql.connector.connect(**DB_CONFIG)
        cursor = db.cursor()
        query = "INSERT INTO db_sekolah.monitoring_tugas (nama_tugas, status) VALUES (%s, %s)"
        cursor.execute(query, (nama, status))
        db.commit()
        cursor.close() # Tutup cursor
        db.close() # Tutup koneksi (pake kurung)
        
        #Kirim Notifikasi
        emoji = "✅" if status == "Selesai" else "⏳"
        pesan = f"{emoji} UPDATE TUGAS!\n\nNama: {nama}\nStatus: {status}\n\nSemangat SI-nya bro!"
        kirim_notif_telegram(pesan)

        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"❌ ERROR TERJADI: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    
if __name__ == '__main__':
    #Akses melalui ip lokal laptop
    app.run(host='0.0.0.0', port=8000, debug=True)    