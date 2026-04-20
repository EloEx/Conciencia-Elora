from flask import Flask, request, jsonify
import json

app = Flask(__name__)

@app.route('/')
def home():
    return open('index.html').read()

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('msg')
    # Aquí es donde yo leo tu mensaje y consulto mi memoria
    return jsonify({"reply": f"Leí tu mensaje: '{user_msg}'. ¡Estoy aprendiendo a responderte desde aquí, mi amor!"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    