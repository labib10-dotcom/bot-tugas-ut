import os
import re
import json 
import requests
from google.oauth2 import service_account 
from googleapiclient.discovery import build
from datetime import datetime

drive_service = None
sheets_service = None

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def kirim_notif_telegram(pesan):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": pesan}
    try:
        requests.post(url, json=data)
    except Exception as e:
        print(f"Gagal kirim Telegram: {e}")

def init_google_services():
    global drive_service, sheets_service
    info = json.loads(os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON"))
    scopes = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
    creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    drive_service = build('drive', 'v3', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)

def scan_folder():
    init_google_services()
    folder_id = os.environ.get("GDRIVE_FOLDER_ID")

    query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.document' and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])

    if not items:
        print("Folder kosong atau tidak itemukan ")
        return
    
    for item in items:
        print(f"🔍 Scanning: {item['name']}")
        content = drive_service.files().export(fileId=item['id'],  mimeType='text/plain').execute().decode('utf-8')
        proses_teks(content, item['name'])
        
def proses_teks(text, matkul):
    lines = text.split('\n')
    for line in lines:
        clean_line = line.strip()
        if not clean_line: continue

        status = None
        lower_line = clean_line.lower()

        if '#onprogress' in lower_line:
            status = "Onprogress"
            # Hapus tag (case-insensitive)
            tugas = re.sub(r'#onprogress', '', clean_line, flags=re.IGNORECASE)
        elif '#selesai' in lower_line: 
            status = "Selesai"
            # Hapus tag (case-insensitive)
            tugas = re.sub(r'#selesai', '', clean_line, flags=re.IGNORECASE)

        if status:
            # Bersihkan teks tugas dari spasi berlebih dan dari bullet/number formatting (seperti "* ", "- ", "1. ")
            tugas = re.sub(r'^[\*\-\+]\s+|^[0-9]+[\.\)]\s+', '', tugas.strip()).strip()
            
            if tugas: # Pastikan teks tugas tidak kosong setelah dibersihkan
                print(f"🎯 Ketemu Tugas: {tugas} | Status: {status}")
                simpan_ke_gsheets(tugas, status, matkul)

def simpan_ke_gsheets(tugas, status, matkul):
    try:
        spreadsheet_id = os.environ.get("GSHEET_SPREADSHEET_ID")
        sheet_range = "Sheet1!A:D"
        
        # Ambil data yang ada di sheets
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=sheet_range).execute()
        rows = result.get('values', [])
        
        # Waktu saat ini
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        row_found_index = -1
        status_sekarang = None
        
        for i, row in enumerate(rows):
            # Asumsi kolom A = Nama Tugas, kolom B = Mata Kuliah, kolom C = Status
            if len(row) >= 2 and row[0].strip() == tugas and row[1].strip() == matkul:
                row_found_index = i
                status_sekarang = row[2] if len(row) > 2 else ""
                break
                
        emoji = "✅" if status == "Selesai" else "⏳"

        if row_found_index > -1:
            if status_sekarang != status:
                # Update status
                update_range = f"Sheet1!C{row_found_index + 1}:D{row_found_index + 1}"
                body = {'values': [[status, now]]}
                sheets_service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id, range=update_range,
                    valueInputOption="USER_ENTERED", body=body).execute()
                
                # Kirim Notif
                kirim_notif_telegram(f"{emoji} UPDATE: {matkul}\nLog: {tugas}\nStatus: {status}")
                print(f"✅ Terupdate: {tugas}")
        else:
            # Baris belum ada, tambah baru
            body = {'values': [[tugas, matkul, status, now]]}
            sheets_service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id, range=sheet_range,
                valueInputOption="USER_ENTERED", body=body).execute()
                
            # Kirim Notif
            kirim_notif_telegram(f"{emoji} TUGAS BARU: {matkul}\nLog: {tugas}\nStatus: {status}")
            print(f"✅ Tersimpan: {tugas}")

    except Exception as e:
        print(f"❌ Error GSheets: {e}")

if __name__ == "__main__":
    scan_folder()
