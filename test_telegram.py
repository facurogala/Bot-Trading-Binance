import os
from dotenv import load_dotenv
import requests

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_test_message():
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    message = "🧪 Mensaje de prueba - Bot funcionando correctamente! ✅"
    payload = {"chat_id": CHAT_ID, "text": message}
    
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Mensaje enviado exitosamente!")
            print(f"📱 Chat ID: {CHAT_ID}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error al enviar: {e}")

if __name__ == "__main__":
    send_test_message()
