import os
import json 
import mysql.connector
import requests
from google.oauth2 import service_account 
from googleapiclient.discovery import build

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def kirim_notif_telegram(pesan):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": pesan}
    try:
        requests.post(url, json=data)
    except Exception as e:
        print(f"Gagal kirim Telegram: {e}")

def get_gdrive_service():
    info = json.loads(os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON"))
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def scan_folder():
    service = get_gdrive_service()
    folder_id = os.environ.get("GDRIVE_FOLDER_ID")

    query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.document' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])

    if not items:
        print("Folder kosong atau tidak itemukan ")
        return
    
    for item in items:
        print(f"🔍 Scanning: {item['name']}")
        content = service.files().export(fileId=item['id'],  mimeType='text/plain').execute().decode('utf-8')
        proses_teks(content, item['name'])
        
def proses_teks(text, matkul):
    lines = text.split('\n')
    for line in lines:
        status = None

        if '#Onprogress' in line:
            status = "Onprogress"
            tugas = line.replace("#Onprogress", "").strip()
        elif '#SelesaiJuga' in line: 
            status = "Selesai"
            tugas = line.replace("#Onprogress", "").strip()

        if status:
            simpan_ke_aiven(tugas, status, matkul)

def simpan_ke_aiven(tugas, status, matkul):
    try:
        db_config = {
            "host": os.environ.get("DB_HOST"),
            "user": os.environ.get("DB_USER"),
            "password": os.environ.get("DB_PASS"),
            "port": int(os.environ.get("DB_PORT", 21890)),
            "database": os.environ.get("DB_NAME")
        }

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        query = """
        INSERT INTO monitoring_tugas (nama_tugas, status, mata_kuliah) 
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE status = %s
        """
        cursor.execute(query, (tugas, status, matkul, status))

        if cursor.rowcount > 0:
            conn.commit()
            emoji = "✅" if status == "Selesai" else "⏳"
            kirim_notif_telegram(f"{emoji} {matkul}\nLog: {tugas}\nStatus: {status}")
            print(f"✅ Tersimpan: {tugas}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ Error DB: {e}")

if __name__ == "__main__":
    scan_folder()
