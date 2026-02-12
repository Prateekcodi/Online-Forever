from flask import Flask
import threading
import time
import os

app = Flask(__name__)

@app.route('/health')
def health():
    return "OK", 200

@app.route('/')
def home():
    return "Alive", 200

def keep_alive_thread():
    while True:
        time.sleep(30)

def keep_alive():
    """Start the Flask server in a thread to keep the bot alive"""
    threading.Thread(target=keep_alive_thread, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    keep_alive()
