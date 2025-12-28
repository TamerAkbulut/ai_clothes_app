from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import requests
from urllib.parse import urlparse, parse_qs
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


class ProxyHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
    
    def do_GET(self):
        if self.path.startswith('/api/ai'):
            self.handle_weather_ai()
        elif self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/weather.html')
            self.end_headers()
        else:
            super().do_GET()
    
    def do_POST(self):
        """POST isteklerini işle - CHATBOT İÇİN GEREKLİ"""
        if self.path.startswith('/api/chat'):
            self.handle_chatbot()
        else:
            self.send_error(404, "Endpoint bulunamadı")
    
    def list_directory(self, path):
        self.send_error(403, "Dizin listeleme kapalı")
    
    def handle_chatbot(self):
        """💬 CHATBOT ENDPOINT"""
        try:
            # POST verisini oku
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            user_message = data.get('message', '')
            history = data.get('history', [])
            weather = data.get('weather', {})
            
            print(f"\n💬 Chatbot: {user_message[:50]}...")
            
            # Sistem mesajı
            system_msg = f"""Sen yardımsever bir kıyafet danışmanısın. Türkçe konuşuyorsun.

Mevcut hava durumu:
- Şehir: {weather.get('location', '?')}
- Sıcaklık: {weather.get('temp', '?')}°C
- Nem: {weather.get('humidity', '?')}%
- Rüzgar: {weather.get('wind', '?')} km/h
- Durum: {weather.get('description', '?')}

Görevin: Kullanıcıya kıyafet, moda ve hava durumuna göre pratik öneriler vermek.
Kısa, samimi ve emoji kullanarak yanıt ver."""

            # Mesajları hazırla
            messages = [{"role": "system", "content": system_msg}]
            for msg in history[-8:]:  # Son 8 mesaj
                messages.append({"role": msg["role"], "content": msg["content"]})
            
            # Groq API'ye istek
            response = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {GROQ_API_KEY}'
                },
                json={
                    'model': 'llama-3.3-70b-versatile',
                    'messages': messages,
                    'temperature': 0.8,
                    'max_tokens': 400
                },
                timeout=30
            )
            
            if response.status_code == 200:
                ai_data = response.json()
                ai_reply = ai_data['choices'][0]['message']['content']
                
                print(f"✅ Bot: {ai_reply[:60]}...")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'response': ai_reply
                }, ensure_ascii=False).encode('utf-8'))
            else:
                raise Exception(f"API hatası: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Chat hatası: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': str(e)
            }).encode('utf-8'))
    
    def handle_weather_ai(self):
        """🌤️ HAVA DURUMU ENDPOINT"""
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            
            temp = float(params.get('temp', [0])[0])
            humidity = float(params.get('humidity', [0])[0])
            wind = float(params.get('wind', [0])[0])
            precipitation = float(params.get('precipitation', [0])[0])
            description = params.get('description', [''])[0]
            
            print(f"\n🌤️  Hava: {temp}°C, {description}")
            
            prompt = f"""Hava durumu:
- Sıcaklık: {temp}°C
- Nem: {humidity}%
- Rüzgar: {wind} km/h
- Yağış: {precipitation} mm
- Durum: {description}

Sabah, öğlen ve akşam için kıyafet öner. JSON formatında:
{{
  "morning": {{"upper": "...", "lower": "...", "accessories": "...", "note": "..."}},
  "afternoon": {{"upper": "...", "lower": "...", "accessories": "...", "note": "..."}},
  "evening": {{"upper": "...", "lower": "...", "accessories": "...", "note": "..."}}
}}"""

            print("🤖 Groq AI'dan öneri alınıyor...")
            
            response = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {GROQ_API_KEY}'
                },
                json={
                    'model': 'llama-3.3-70b-versatile',
                    'messages': [
                        {'role': 'system', 'content': 'Türkçe kıyafet danışmanısın. Sadece JSON döndür.'},
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0.7,
                    'max_tokens': 1500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                ai_text = data['choices'][0]['message']['content']
                
                # JSON temizle
                clean = ai_text.strip()
                if '```' in clean:
                    lines = clean.split('\n')
                    clean = '\n'.join(line for line in lines if not line.strip().startswith('```'))
                clean = clean.strip()
                
                result = json.loads(clean)
                print("✅ Öneriler alındı!")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))
            else:
                raise Exception(f"API hatası: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Hata: {e}")
            self.send_error(500, str(e))

if __name__ == '__main__':
    PORT = 8000
    
    print("=" * 50)
    print("🚀 AI Kıyafet Asistanı (Groq AI)")
    print("=" * 50)
    print(f"\n✅ Sunucu: http://localhost:{PORT}")
    print(f"\n📱 Tarayıcıda açın:")
    print(f"   http://localhost:{PORT}")
    print(f"\n⏹️  Durdurmak için: Ctrl+C")
    print("=" * 50 + "\n")
    
    try:
        server = HTTPServer(('localhost', PORT), ProxyHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n✅ Sunucu kapatıldı!")