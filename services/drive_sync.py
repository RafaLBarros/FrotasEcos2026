# arquivo: services/drive_sync.py
import os
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

def obter_servico_drive():
    creds_json_str = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if not creds_json_str:
        return None
    try:
        creds_data = json.loads(creds_json_str)
        scopes = ['https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_info(creds_data, scopes=scopes)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ Falha ao autenticar Conta de Serviço do Google: {e}")
        return None

def baixar_banco_mais_recente():
    service = obter_servico_drive()
    file_id = os.environ.get('GOOGLE_DRIVE_FILE_ID') # Agora usamos o ID do Arquivo
    
    if not service or not file_id:
        print("⚠️ Sincronização desativada: Credenciais ou FILE_ID ausentes.")
        return False

    try:
        print("🔄 Baixando o banco de dados do Drive Pessoal...")
        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        
        done = False
        while not done:
            _, done = downloader.next_chunk()

        with open('ecos_database.db', 'wb') as f:
            f.write(buffer.getvalue())
            
        print("✅ Banco de dados sincronizado com a nuvem com sucesso!")
        return True
    except Exception as e:
        print(f"❌ Erro ao baixar banco de dados do Drive: {e}")
        return False

def enviar_banco_para_o_drive():
    service = obter_servico_drive()
    file_id = os.environ.get('GOOGLE_DRIVE_FILE_ID')
    
    if not service or not file_id or not os.path.exists('ecos_database.db'):
        return False

    try:
        # Em vez de file_metadata e .create(), nós fazemos um update direto!
        media = MediaFileUpload('ecos_database.db', mimetype='application/x-sqlite3', resumable=True)
        
        service.files().update(
            fileId=file_id,
            media_body=media
        ).execute()
        
        print("☁️ Nuvem atualizada: Banco de dados sobrescrito com sucesso no Drive Pessoal.")
        return True
    except Exception as e:
        print(f"❌ Erro ao atualizar o Drive: {e}")
        return False