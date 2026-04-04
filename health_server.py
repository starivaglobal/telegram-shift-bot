from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
@app.route('/health')
@app.route('/healthcheck')
def health():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting health server on port {port}")
    app.run(host='0.0.0.0', port=port) 
