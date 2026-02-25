"""
STEP 1: Run this first to test if Flask works at all:
  python test_server.py

If you see "Connected" in your browser, Flask is fine.
If you still see "Disconnected", the problem is Flask/Python itself.
"""
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "message": "Test server working!"})

@app.route('/')
def index():
    return """
    <html><body style="background:#0b0f1f;color:white;font-family:sans-serif;padding:40px;text-align:center;">
    <h1 style="color:#8b6cff">VoiceNav Test Server</h1>
    <p style="color:#4ade80;font-size:1.5rem;">Flask is working!</p>
    <p>Now replace with your full app.py</p>
    </body></html>
    """

if __name__ == '__main__':
    print("="*50)
    print("Test server starting on http://localhost:8000")
    print("Open your browser - if Connected appears, Flask works!")
    print("="*50)
    app.run(debug=False, host='0.0.0.0', port=8000)