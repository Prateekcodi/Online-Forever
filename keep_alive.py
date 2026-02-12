from flask import Flask
import threading
import time

app = Flask(__name__)
@app.route('/health')
def health():
    return "OK", 200

@app.route('/')
def home():
    return "Alive", 200

def keep_alive_thread():
    while True:
        time.sleep(30)  # just keep thread alive

if __name__ == "__main__":
    threading.Thread(target=keep_alive_thread, daemon=True).start()
    app.run(host='0.0.0.0', port=8080)