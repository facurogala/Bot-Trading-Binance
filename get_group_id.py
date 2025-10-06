import os
from dotenv import load_dotenv
import requests
import json

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

def get_chat_ids():
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            if data['ok'] and len(data['result']) > 0:
                print("📋 Lista de chats detectados:\n")
                print("="*60)
                
                seen_chats = set()
                
                for update in data['result']:
                    if 'message' in update:
                        msg = update['message']
                        chat = msg['chat']
                        chat_id = chat['id']
                        
                        if chat_id not in seen_chats:
                            seen_chats.add(chat_id)
                            
                            chat_type = chat['type']
                            
                            if chat_type == 'private':
                                name = chat.get('first_name', 'Sin nombre')
                                username = chat.get('username', 'Sin username')
                                print(f"👤 Chat Privado:")
                                print(f"   Nombre: {name}")
                                print(f"   Username: @{username}" if username != 'Sin username' else f"   Sin username")
                                print(f"   Chat ID: {chat_id}")
                                
                            elif chat_type in ['group', 'supergroup']:
                                group_name = chat.get('title', 'Sin título')
                                print(f"👥 Grupo:")
                                print(f"   Nombre: {group_name}")
                                print(f"   Chat ID: {chat_id}")
                                print(f"   ⚠️ Usa este ID para el grupo!")
                            
                            print("-"*60)
                
                if not seen_chats:
                    print("❌ No se encontraron chats.")
                    print("💡 Envía un mensaje al bot o agrégalo a un grupo primero.")
            else:
                print("❌ No hay mensajes disponibles.")
                print("💡 Envía /start al bot o agrégalo a un grupo y escribe algo.")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🔍 Buscando chats del bot...\n")
    get_chat_ids()
    print("\n📝 Para actualizar el .env con el grupo, usa:")
    print("   TELEGRAM_CHAT_ID=<ID_DEL_GRUPO>")
