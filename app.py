from flask import Flask, request, render_template, jsonify
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import requests
import json
import os
from datetime import datetime
import re
from dotenv import load_dotenv

# Environment variables'ları yükle
load_dotenv()

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key')

# Environment variables'lardan hassas bilgileri al
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
MY_PHONE_NUMBER = os.getenv('MY_PHONE_NUMBER')

# Hassas bilgilerin varlığını kontrol et
if not all([OPENROUTER_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, MY_PHONE_NUMBER]):
    raise ValueError("Lütfen .env dosyasında tüm gerekli API anahtarlarını tanımlayın!")

# Veritabanı dosyaları
APPOINTMENTS_FILE = 'data/appointments.json'
VEHICLES_FILE = 'data/vehicles.json'
os.makedirs('data', exist_ok=True)

# Örnek araç veritabanı
SAMPLE_VEHICLES = {
    "otomobil": [
        {"marka": "Toyota", "model": "Corolla", "yil": 2023, "fiyat": 850000, "ozellikler": ["Otomatik", "Benzin", "Sedan"]},
        {"marka": "Honda", "model": "Civic", "yil": 2023, "fiyat": 950000, "ozellikler": ["Otomatik", "Benzin", "Sedan"]},
        {"marka": "Volkswagen", "model": "Golf", "yil": 2023, "fiyat": 1050000, "ozellikler": ["Otomatik", "Benzin", "Hatchback"]}
    ],
    "suv": [
        {"marka": "Toyota", "model": "RAV4", "yil": 2023, "fiyat": 1250000, "ozellikler": ["Otomatik", "Hibrit", "SUV"]},
        {"marka": "Honda", "model": "CR-V", "yil": 2023, "fiyat": 1350000, "ozellikler": ["Otomatik", "Benzin", "SUV"]}
    ],
    "karavan": [
        {"marka": "Volkswagen", "model": "California", "yil": 2023, "fiyat": 2500000, "ozellikler": ["Otomatik", "Dizel", "Karavan"]},
        {"marka": "Mercedes", "model": "Marco Polo", "yil": 2023, "fiyat": 2800000, "ozellikler": ["Otomatik", "Dizel", "Karavan"]}
    ]
}

def init_database():
    """Veritabanı dosyalarını oluştur"""
    if not os.path.exists(APPOINTMENTS_FILE):
        with open(APPOINTMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
    
    if not os.path.exists(VEHICLES_FILE):
        with open(VEHICLES_FILE, 'w', encoding='utf-8') as f:
            json.dump(SAMPLE_VEHICLES, f, ensure_ascii=False, indent=2)

def load_vehicles():
    """Araç veritabanını yükle"""
    try:
        with open(VEHICLES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return SAMPLE_VEHICLES

def load_appointments():
    """Randevuları yükle"""
    try:
        with open(APPOINTMENTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_appointment(appointment_data):
    """Yeni randevu kaydet"""
    appointments = load_appointments()
    
    appointment = {
        'id': len(appointments) + 1,
        'created_at': datetime.now().isoformat(),
        'status': 'active',
        **appointment_data
    }
    
    appointments.append(appointment)
    
    with open(APPOINTMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(appointments, f, ensure_ascii=False, indent=2)
    
    return appointment

# Konuşma geçmişini saklamak için
conversations = {}

# Sesli asistan session yönetimi için
voice_sessions = {}

def extract_appointment_from_conversation(conversation_history):
    """Konuşma geçmişinden randevu bilgilerini çıkar"""
    try:
        import re
        from datetime import datetime, timedelta
        
        appointment_info = {
            'name': None,
            'phone': None,
            'vehicle_type': None,
            'date': None,
            'time': None
        }
        
        # SADECE kullanıcı mesajlarını al - AI mesajlarını filtrele
        user_messages = []
        all_user_text = ""
        
        for msg in conversation_history:
            if msg.get('role') == 'user':
                user_messages.append(msg['content'])
                all_user_text += " " + msg['content'].lower()
        
        print(f"🔍 DEBUG - Kullanıcı mesajları: {user_messages}")
        print(f"🔍 DEBUG - Analiz edilen kullanıcı metni: '{all_user_text[:200]}...'")
        
        # İSİM TESPİTİ 
        name_patterns = [
            r'([A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)',
            r'([a-zA-ZçğıöşüÇĞİÖŞÜ]+\s+[a-zA-ZçğıöşüÇĞİÖŞÜ]+)',
            r'isim.*?([a-zA-ZçğıöşüÇĞİÖŞÜ\s]+)',
            r'ben\s+([a-zA-ZçğıöşüÇĞİÖŞÜ\s]+)',
        ]
        
        # Önce mesajın başındaki kelimelerden isim arama
        words = all_user_text.split()
        if len(words) >= 2:
            first_two_words = f"{words[0]} {words[1]}"
            car_words = ['toyota', 'honda', 'volkswagen', 'mercedes', 'civic', 'corolla', 'golf', 'otomobil', 'suv', 'karavan', 'randevu', 'telefon', 'saat', 'yarın', 'pazartesi', 'salı', 'çarşamba', 'perşembe', 'cuma', 'cumartesi', 'pazar']
            
            # İlk iki kelime araba kelimesi değilse ve sadece harfse isim olabilir
            if (not any(car in first_two_words.lower() for car in car_words) and 
                re.match(r'^[a-zA-ZçğıöşüÇĞİÖŞÜ]+\s+[a-zA-ZçğıöşüÇĞİÖŞÜ]+$', first_two_words) and
                len(first_two_words) > 4):
                appointment_info['name'] = first_two_words.title()
                print(f"👤 DEBUG - İsim bulundu (başta): {appointment_info['name']}")
        
        # Eğer bulunamadıysa pattern'lerle ara
        if not appointment_info['name']:
            for pattern in name_patterns:
                matches = re.findall(pattern, all_user_text)
                for match in matches:
                    name = str(match).strip()
                    car_words = ['toyota', 'honda', 'volkswagen', 'mercedes', 'civic', 'corolla', 'golf', 'otomobil', 'suv', 'karavan', 'randevu', 'telefon']
                    
                    if name and len(name) > 2 and len(name) < 30 and not any(car in name.lower() for car in car_words):
                        if re.match(r'^[a-zA-ZçğıöşüÇĞİÖŞÜ\s]+$', name):
                            appointment_info['name'] = name.title()
                            print(f"👤 DEBUG - İsim bulundu (pattern): {appointment_info['name']}")
                            break
                if appointment_info['name']:
                    break
        
        # TELEFON TESPİTİ - Kullanıcı mesajlarından
        phone_patterns = [
            r'\b(05\d{9})\b',
            r'\b(5\d{9})\b',
            r'\b(0\d{10})\b', 
            r'(\d{11})',
            r'(\d{10})',
            r'telefon.*?(\d{10,11})',
            r'numara.*?(\d{10,11})',
            r'(\d{3})\s*(\d{3})\s*(\d{4})',
            r'(\d{3})\s*(\d{3})\s*(\d{2})\s*(\d{2})',
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, all_user_text)
            for match in matches:
                if isinstance(match, tuple):
                    # Tuple ise birleştir
                    phone = ''.join(match).strip()
                else:
                    phone = str(match).strip()
                
                # Sadece rakamları al
                phone = re.sub(r'[^\d]', '', phone)
                
                if phone and phone.isdigit() and len(phone) >= 10:
                    # 0 ile başlıyorsa 05 kontrolü
                    if len(phone) == 11 and phone.startswith('0') and not phone.startswith('05'):
                        continue
                    # 10 haneli ise 5 ile başlamalı  
                    if len(phone) == 10 and not phone.startswith('5'):
                        continue
                        
                    appointment_info['phone'] = phone
                    print(f"📞 DEBUG - Telefon bulundu: {appointment_info['phone']}")
                    break
            if appointment_info['phone']:
                break
        
        # ARAÇ TİPİ TESPİTİ - Kullanıcı mesajlarından
        vehicle_keywords = {
            'otomobil': ['otomobil', 'sedan', 'corolla', 'civic', 'golf', 'araba', 'binek'],
            'suv': ['suv', 'rav4', 'crv', 'cr-v', 'es u vi'],
            'karavan': ['karavan', 'california', 'marco polo', 'kamper', 'marco', 'polo']
        }
        
        for vehicle_type, keywords in vehicle_keywords.items():
            for keyword in keywords:
                if keyword in all_user_text:
                    appointment_info['vehicle_type'] = vehicle_type
                    print(f"🚗 DEBUG - Araç tipi bulundu: {keyword} -> {vehicle_type}")
                    break
            if appointment_info['vehicle_type']:
                break
        
        # TARİH TESPİTİ - Kullanıcı mesajlarından
        date_patterns = [
            r'\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b',
            r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, all_user_text)
            for match in matches:
                try:
                    if len(str(match[2])) == 4:
                        day, month, year = match
                    else:
                        year, month, day = match
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    appointment_info['date'] = date_obj.strftime('%Y-%m-%d')
                    print(f"📅 DEBUG - Tarih bulundu: {appointment_info['date']}")
                    break
                except ValueError:
                    continue
            if appointment_info['date']:
                break
        
        # Gün isimleri - Kullanıcı mesajlarından
        if not appointment_info['date']:
            days = {
                'pazartesi': 0, 'salı': 1, 'çarşamba': 2, 'perşembe': 3, 
                'cuma': 4, 'cumartesi': 5, 'pazar': 6, 'yarın': 1
            }
            
            for day_name, day_num in days.items():
                if day_name in all_user_text:
                    today = datetime.now()
                    if day_name == 'yarın':
                        target_date = today + timedelta(days=1)
                    else:
                        current_weekday = today.weekday()
                        days_ahead = (day_num - current_weekday) % 7
                        if days_ahead == 0:
                            days_ahead = 7
                        target_date = today + timedelta(days=days_ahead)
                    
                    appointment_info['date'] = target_date.strftime('%Y-%m-%d')
                    print(f"📅 DEBUG - Gün ismi ile tarih: {day_name} -> {appointment_info['date']}")
                    break
        
        # SAAT TESPİTİ - Kullanıcı mesajlarından
        time_patterns = [
            r'\b(\d{1,2})[:.,-](\d{2})\b',
            r'saat\s*(\d{1,2})\b',
            r'\b(\d{1,2})\s*(?:saat|saatte)\b'
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, all_user_text)
            for match in matches:
                try:
                    if isinstance(match, tuple) and len(match) >= 2:
                        hour = int(match[0])
                        minute = int(match[1])
                    else:
                        hour = int(match)
                        minute = 0
                    
                    if 8 <= hour <= 18:
                        appointment_info['time'] = f"{hour:02d}:{minute:02d}"
                        print(f"🕐 DEBUG - Saat bulundu: {appointment_info['time']}")
                        break
                except (ValueError, IndexError):
                    continue
            if appointment_info['time']:
                break
        
        print(f"📋 DEBUG - FINAL Çıkarılan randevu bilgileri: {appointment_info}")
        return appointment_info
        
    except Exception as e:
        print(f"❌ DEBUG - Randevu bilgisi çıkarma hatası: {e}")
        return None

def check_appointment_completeness(appointment_info, conversation_history):
    """Randevu bilgilerinin yeterli olup olmadığını kontrol et"""
    try:
        if not appointment_info:
            return False
            
        has_name = appointment_info.get('name') and len(str(appointment_info.get('name', '')).strip()) >= 3
        has_phone = appointment_info.get('phone') and len(str(appointment_info.get('phone', '')).strip()) >= 10
        has_vehicle = appointment_info.get('vehicle_type') and appointment_info.get('vehicle_type') in ['otomobil', 'suv', 'karavan']
        has_date = appointment_info.get('date') and appointment_info.get('date') != None
        has_time = appointment_info.get('time') and appointment_info.get('time') != None
        
        print(f"📊 DEBUG - Kontrol sonuçları:")
        print(f"  👤 İsim: {has_name} ({appointment_info.get('name')})")
        print(f"  📞 Telefon: {has_phone} ({appointment_info.get('phone')})")
        print(f"  🚗 Araç: {has_vehicle} ({appointment_info.get('vehicle_type')})")
        print(f"  📅 Tarih: {has_date} ({appointment_info.get('date')})")
        print(f"  🕐 Saat: {has_time} ({appointment_info.get('time')})")
        
        return has_name and has_phone and has_vehicle and has_date and has_time
            
    except Exception as e:
        print(f"❌ DEBUG - Tamamlanma kontrol hatası: {e}")
        return False

@app.route('/')
def home():
    vehicles = load_vehicles()
    appointments = load_appointments()
    return render_template('index.html', vehicles=vehicles, appointments=appointments)

@app.route('/api/vehicles')
def get_vehicles():
    vehicles = load_vehicles()
    return jsonify(vehicles)

@app.route('/api/vehicles/<category>')
def get_vehicles_by_category(category):
    vehicles = load_vehicles()
    if category in vehicles:
        return jsonify(vehicles[category])
    return jsonify({'error': 'Kategori bulunamadı'}), 404

@app.route('/api/appointments', methods=['GET', 'POST'])
def handle_appointments():
    if request.method == 'GET':
        appointments = load_appointments()
        return jsonify(appointments)
    
    elif request.method == 'POST':
        data = request.get_json()
        
        required_fields = ['name', 'phone', 'vehicle_type', 'date', 'time']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Eksik bilgi'}), 400
        
        appointment = save_appointment(data)
        return jsonify(appointment), 201

@app.route('/api/appointments/<int:appointment_id>', methods=['PUT', 'DELETE'])
def handle_appointment(appointment_id):
    appointments = load_appointments()
    
    appointment = next((a for a in appointments if a['id'] == appointment_id), None)
    if not appointment:
        return jsonify({'error': 'Randevu bulunamadı'}), 404
    
    if request.method == 'PUT':
        data = request.get_json()
        appointment.update(data)
    elif request.method == 'DELETE':
        appointments.remove(appointment)
    
    with open(APPOINTMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(appointments, f, ensure_ascii=False, indent=2)
    
    return jsonify(appointment)

@app.route('/test-ai', methods=['POST'])
def test_ai():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Mesaj bulunamadı'}), 400

        user_id = request.remote_addr + request.headers.get('User-Agent', '')
        
        if user_id not in conversations:
            conversations[user_id] = []
        
        # Sistem mesajını ekle
        if not conversations[user_id]:
            vehicles = load_vehicles()
            
            vehicle_info = "Galerindeki mevcut araçlar:\n\n"
            
            for category, vehicle_list in vehicles.items():
                vehicle_info += f"🚗 {category.upper()} KATEGORİSİ:\n"
                for vehicle in vehicle_list:
                    vehicle_info += f"- {vehicle['marka']} {vehicle['model']} ({vehicle['yil']}) - ₺{vehicle['fiyat']:,} TL\n"
                    vehicle_info += f"  Özellikler: {', '.join(vehicle['ozellikler'])}\n"
                vehicle_info += "\n"
            
            system_content = f"""Sen bir otomotiv galerisinin Türkçe konuşan AI asistanısın.

{vehicle_info}

Görevlerin:
1. Müşterilere yukarıdaki araçlar hakkında detaylı bilgi ver
2. Fiyat karşılaştırmaları yap
3. Müşterinin ihtiyacına göre araç öner
4. Araç özelliklerini açıkla
5. Randevu alma konusunda yönlendir

RANDEVU ALMA SÜRECİ - ÇOK ÖNEMLİ:
Müşteri randevu istediğinde tüm bilgileri birden iste:

"Randevu için şu bilgileri verebilir misiniz?
- İsim soyisim
- Telefon numaranız  
- Hangi araç için (otomobil/suv/karavan)
- Hangi gün
- Saat kaçta"

Müşteri tüm bilgileri verince direkt "RANDEVU_OLUSTUR" yaz.
Eksik bilgi varsa eksik olanı belirt.

KRITIK KURAL - MUTLAKA UYGULANACAK:
- Randevu konuşmasında MUTLAKA "RANDEVU_OLUSTUR" kelimesini kullan
- Bu kelime olmadan randevu oluşmaz
- Bilgiler tam olunca: "Bilgilerinizi aldım! RANDEVU_OLUSTUR"
- Kesinlikle bu kelimeyi yaz!

Örnek:
Müşteri: "Ahmet Yılmaz, 05321234567, otomobil için randevu istiyorum, pazartesi saat 14:00"
Sen: "Tüm bilgilerinizi aldım! RANDEVU_OLUSTUR"

Kurallar:
- Samimi ve profesyonel ol
- Fiyatları doğru ver  
- Müşterinin bütçesine uygun öner"""
            conversations[user_id].append({
                "role": "system",
                "content": system_content
            })

        conversations[user_id].append({
            "role": "user",
            "content": data['message']
        })

        if not OPENROUTER_API_KEY:
            return jsonify({'error': 'AI servisi şu anda kullanılamıyor.'}), 500

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "Galeri AI Asistan"
        }
        
        payload = {
            "model": "openai/gpt-3.5-turbo",
            "messages": conversations[user_id],
            "max_tokens": 500,
            "temperature": 0.7
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and result['choices']:
                ai_response = result['choices'][0]['message']['content']
                
                conversations[user_id].append({
                    "role": "assistant",
                    "content": ai_response
                })
                
                print(f"\n🤖 DEBUG - AI YANITI: '{ai_response}'")
                print(f"🔍 DEBUG - Konuşma geçmişi uzunluğu: {len(conversations[user_id])}")
                
                # Randevu oluşturma kontrolü - Temizlenmiş sistem
                appointment_created = None
                
                # Ana trigger kelimesi kontrolü
                if "RANDEVU_OLUSTUR" in ai_response:
                    print("🎯 DEBUG - RANDEVU_OLUSTUR tetikleyicisi bulundu!")
                    
                    # SADECE SON KULLANICI MESAJINI KULLAN - ESKİ BİLGİLERİ UNUTT
                    last_user_message = ""
                    for msg in reversed(conversations[user_id]):
                        if msg.get('role') == 'user':
                            last_user_message = msg['content']
                            break
                    
                    print(f"🔍 DEBUG - Sadece son mesaj analiz ediliyor: '{last_user_message}'")
                    
                    # Sadece son mesajdan bilgi çıkar
                    appointment_info = extract_appointment_from_single_message(last_user_message)
                    print(f"📋 DEBUG - Son mesajdan çıkarılan bilgiler: {appointment_info}")
                    
                    if appointment_info and check_single_message_completeness(appointment_info):
                        try:
                            appointment_created = save_appointment(appointment_info)
                            print(f"✅ DEBUG - Randevu BAŞARIYLA oluşturuldu: ID {appointment_created['id']}")
                            
                            # AI yanıtından trigger kelimesini kaldır ve başarı mesajı ekle
                            ai_response = ai_response.replace("RANDEVU_OLUSTUR", "")
                            success_msg = f"\n\n✅ Mükemmel! Randevunuz başarıyla kaydedildi!\nRandevu Numaranız: #{appointment_created['id']}\nGaleri ekibimiz size ulaşacak."
                            ai_response += success_msg
                            conversations[user_id][-1]['content'] = ai_response
                            
                            # Randevu oluştu, konuşma geçmişini temizle
                            conversations[user_id] = [conversations[user_id][0]]  # Sadece sistem mesajını tut
                            
                        except Exception as e:
                            print(f"❌ DEBUG - Randevu oluşturma hatası: {e}")
                            ai_response = ai_response.replace("RANDEVU_OLUSTUR", "")
                            ai_response += "\n\n❌ Üzgünüm, randevu oluşturulurken bir hata oluştu. Lütfen tekrar deneyin."
                    else:
                        print("ℹ️ DEBUG - Son mesajda randevu için yeterli bilgi YOK")
                        ai_response = ai_response.replace("RANDEVU_OLUSTUR", "")
                        ai_response += "\n\n⚠️ Lütfen tüm bilgileri tek mesajda verin: İsim, telefon, araç tipi, tarih, saat"
                
                # Geçmiş çok uzunsa temizle
                if len(conversations[user_id]) > 12:
                    conversations[user_id] = [conversations[user_id][0]] + conversations[user_id][-10:]
                
                response_data = {'response': ai_response}
                if appointment_created:
                    response_data['appointment_created'] = appointment_created
                
                return jsonify(response_data)
            else:
                return jsonify({'error': 'AI yanıt alınamadı.'}), 500
        else:
            return jsonify({'error': 'AI servisi hatası.'}), 500

    except requests.exceptions.Timeout:
        return jsonify({'error': 'AI servisi yanıt vermiyor.'}), 500
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'AI servisine bağlanılamıyor.'}), 500
    except Exception as e:
        print(f"❌ DEBUG - Genel hata: {e}")
        return jsonify({'error': 'Bir hata oluştu.'}), 500

@app.route('/voice', methods=['POST'])
def voice():
    """Twilio webhook endpoint'i - Randevu Alma Sistemi"""
    try:
        caller_number = request.values.get('From', 'Bilinmeyen')
        speech_result = request.values.get('SpeechResult', '')
        call_sid = request.values.get('CallSid', '')
        
        if call_sid not in voice_sessions:
            voice_sessions[call_sid] = {
                'conversation_history': [],
                'collected_info': {},
                'step': 'greeting',
                'caller': caller_number
            }
        
        session = voice_sessions[call_sid]
        response = VoiceResponse()
        
        if not speech_result:
            ai_response = "Hoşgeldiniz! Randevu almak için isim soyisminizi söyleyebilir misiniz?"
            session['step'] = 'waiting_name'
        else:
            session['conversation_history'].append(speech_result)
            
            try:
                extracted_info = extract_voice_info(speech_result, session['collected_info'])
                if extracted_info:
                    session['collected_info'].update(extracted_info)
                
                print(f"🔄 DEBUG - Güncel toplam bilgiler: {session['collected_info']}")
                
                ai_response = get_next_question(session['collected_info'])
                print(f"🤖 DEBUG - AI sorusu: '{ai_response}'")
                
                appointment_complete = is_voice_appointment_complete(session['collected_info'])
                print(f"✅ DEBUG - Randevu tamamlandı mı? {appointment_complete}")
                
                if appointment_complete:
                    if 'phone' not in session['collected_info']:
                        clean_phone = caller_number.replace('+90', '').replace('+', '')
                        session['collected_info']['phone'] = clean_phone
                    
                    appointment = save_appointment(session['collected_info'].copy())
                    ai_response = f"Harika! Randevunuz başarıyla oluşturuldu. Randevu numaranız: {appointment['id']}. Galeri ekibimiz size ulaşacak. İyi günler!"
                    
                    del voice_sessions[call_sid]
                    
                    response.say(ai_response, voice='Polly.Filiz', language='tr-TR')
                    return str(response)
            
            except Exception as e:
                ai_response = "Özür dilerim, sizi anlayamadım. Tekrar söyleyebilir misiniz?"
        
        response.say(ai_response, voice='Polly.Filiz', language='tr-TR')
        
        if call_sid in voice_sessions:
            gather = Gather(
                input='speech',
                timeout=8,
                speechTimeout=4,
                language='tr-TR',
                action='/voice',
                method='POST'
            )
            gather.say("Dinliyorum...", voice='Polly.Filiz', language='tr-TR')
            response.append(gather)
            
            response.say(
                "Sizi duymadım. Aramayı sonlandırıyorum. İyi günler!",
                voice='Polly.Filiz',
                language='tr-TR'
            )
        
        return str(response)
        
    except Exception as e:
        response = VoiceResponse()
        response.say(
            "Bir hata oluştu. Tekrar arayabilirsiniz.",
            voice='Polly.Filiz',
            language='tr-TR'
        )
        return str(response)

def extract_voice_info(speech_text, existing_info):
    """Sesli konuşmadan randevu bilgilerini çıkar - İYİLEŞTİRİLMİŞ"""
    info = {}
    speech_lower = speech_text.lower()
    
    print(f"🎤 DEBUG - Sesli giriş: '{speech_text}'")
    print(f"📊 DEBUG - Mevcut bilgiler: {existing_info}")
    
    try:
        # İSİM KONTROLÜ - BASIT VE ETKİLİ
        if 'name' not in existing_info:
            speech_clean = speech_text.strip()
            words = speech_clean.split()
            
            # 2 veya 3 kelimeli isim - direkt al 
            if 2 <= len(words) <= 3:
                # Hepsi harf mi kontrol et
                if all(word.replace("'", "").replace("ğ", "g").replace("ı", "i").replace("ş", "s").replace("ç", "c").replace("ö", "o").replace("ü", "u").isalpha() for word in words):
                    # Her kelime en az 2 harf olsun
                    if all(len(word) >= 2 for word in words):
                        info['name'] = " ".join(word.title() for word in words)
                        print(f"👤 DEBUG - İsim bulundu: {info['name']}")
                        
            # Tek kelime ama "ben mehmet" gibi pattern
            elif len(words) > 3:
                name_patterns = [
                    r"(?:ben|ismim|adım)\s+([a-zA-ZçğıöşüÇĞİÖŞÜ\s]+)",
                ]
                for pattern in name_patterns:
                    match = re.search(pattern, speech_text, re.IGNORECASE) 
                    if match:
                        name_part = match.group(1).strip().split()[:3] # max 3 kelime
                        if len(name_part) >= 2:
                            info['name'] = " ".join(word.title() for word in name_part)
                            print(f"👤 DEBUG - Pattern ile isim: {info['name']}")
                            break
        
        # Araç tipi kontrolü
        if 'vehicle_type' not in existing_info:
            try:
                vehicle_keywords = {
                    'otomobil': ['otomobil', 'araba', 'sedan', 'hatchback', 'binek'],
                    'suv': ['suv', 'es u vi', 'esuvi', 's u v', 'sav', 'jeep', 'crossover'],
                    'karavan': ['karavan', 'kamper', 'rv', 'motorhome']
                }
                
                for vehicle_type, keywords in vehicle_keywords.items():
                    for keyword in keywords:
                        if keyword in speech_lower:
                            info['vehicle_type'] = vehicle_type
                            break
                    if 'vehicle_type' in info:
                        break
            except Exception as e:
                pass
        
        # TARİH KONTROLÜ - SADECE GÜN İSİMLERİ VE NET TARİH FORMATLARI
        if 'date' not in existing_info:
            try:
                # Önce gün isimlerine bak (güvenli)
                days = {
                    'pazartesi': 0, 'salı': 1, 'çarşamba': 2, 'perşembe': 3, 
                    'cuma': 4, 'cumartesi': 5, 'pazar': 6, 'yarın': -1
                }
                
                for day_name, day_num in days.items():
                    if day_name in speech_lower:
                        from datetime import datetime, timedelta
                        today = datetime.now()
                        
                        if day_name == 'yarın':
                            target_date = today + timedelta(days=1)
                        else:
                            current_weekday = today.weekday()
                            days_ahead = (day_num - current_weekday) % 7
                            if days_ahead == 0:
                                days_ahead = 7
                            target_date = today + timedelta(days=days_ahead)
                        
                        info['date'] = target_date.strftime('%Y-%m-%d')
                        print(f"📅 DEBUG - Gün ismi ile tarih: {day_name} -> {info['date']}")
                        break
                
                # Sadece net tarih formatları (çok spesifik)
                if 'date' not in info:
                    date_patterns = [
                        r"(\d{1,2})[./](\d{1,2})[./](\d{4})",  # 15/06/2025
                        r"(\d{4})[./](\d{1,2})[./](\d{1,2})",  # 2025/06/15
                        r"(\d{1,2})[./](\d{1,2})",  # 15/06 (bu yıl)
                        r"(\d{1,2})\s+(\d{1,2})\s+(\d{4})",  # 8 06 2025 (sesli)
                        r"(\d{1,2})\s+(\d{1,2})",  # 8 06 (bu yıl, sesli)
                    ]
                
                    # Net tarih formatları
                    for pattern in date_patterns:
                        match = re.search(pattern, speech_text)
                        if match:
                            groups = match.groups()
                            
                            try:
                                from datetime import datetime
                                
                                if len(groups) == 3:
                                    # Yıl var
                                    if len(groups[2]) == 4:  # Son grup yıl
                                        day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                                    else:  # İlk grup yıl
                                        year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                                else:
                                    # Yıl yok - bu yılı kullan
                                    day, month = int(groups[0]), int(groups[1])
                                    year = datetime.now().year
                                
                                # Tarih geçerli mi kontrol et
                                if 1 <= month <= 12 and 1 <= day <= 31:
                                    date_obj = datetime(year, month, day)
                                    info['date'] = date_obj.strftime('%Y-%m-%d')
                                    print(f"📅 DEBUG - Slash formatı tarih bulundu: {info['date']}")
                                    break
                                    
                            except (ValueError, IndexError):
                                continue
                            
            except Exception as e:
                pass
        
        # SAAT KONTROLÜ - BASIT VE ETKİLİ
        if 'time' not in existing_info:
            try:
                time_patterns = [
                    r"(\d{4})",  # 1400, 1430 gibi
                    r"(\d{1,2}):(\d{2})",  # 14:30
                    r"saat\s*(\d{1,2})",  # saat 14, saat 2
                    r"(\d{1,2})\s*saat",  # 14 saat
                    r"(\d{1,2})\s*buçuk",  # 14 buçuk
                ]
                
                for pattern in time_patterns:
                    match = re.search(pattern, speech_text)
                    if match:
                        try:
                            groups = match.groups()
                            
                            # 4 haneli saat formatı (1400, 1430)
                            if len(groups) == 1 and len(str(groups[0])) == 4:
                                time_str = str(groups[0])
                                hour = int(time_str[:2])
                                minute = int(time_str[2:])
                            # 2 gruplı format (14:30)
                            elif len(groups) >= 2 and groups[1]:
                                hour = int(groups[0])
                                minute = int(groups[1])
                            # Buçuk
                            elif 'buçuk' in pattern:
                                hour = int(groups[0])
                                minute = 30
                            # Tek saat (saat 14)
                            else:
                                hour = int(groups[0])
                                minute = 0
                            
                            # Saat geçerli mi kontrol et (8-18 arası)
                            if 8 <= hour <= 18 and 0 <= minute <= 59:
                                info['time'] = f"{hour:02d}:{minute:02d}"
                                print(f"🕐 DEBUG - Saat bulundu: {info['time']} (input: {speech_text})")
                                break
                        except (ValueError, IndexError):
                            continue
            except Exception as e:
                pass
    
    except Exception as e:
        speech_clean = speech_text.strip()
        if len(speech_clean) > 1 and len(speech_clean) < 20:
            if all(c.isalpha() or c.isspace() for c in speech_clean):
                info['name'] = speech_clean.title()
    
    print(f"📤 DEBUG - Çıkarılan bilgiler: {info}")
    return info

def get_next_question(collected_info):
    """Kısa net sorular"""
    
    try:
        if 'name' not in collected_info or not collected_info.get('name'):
            return "İsim soyisminizi tekrar söyleyebilir misiniz?"
        
        elif 'vehicle_type' not in collected_info or not collected_info.get('vehicle_type'):
            return "Hangi araç için randevu istiyorsunuz? Otomobil, SUV, Karavan?"
        
        elif 'date' not in collected_info or not collected_info.get('date'):
            return "Hangi gün geleceksiniz? Pazartesi, Salı gibi gün söyleyin."
        
        elif 'time' not in collected_info or not collected_info.get('time'):
            return "Saat kaçta? Örneğin saat 14 veya saat 15 gibi."
        
        else:
            return "Randevu oluşturuluyor."
    
    except Exception as e:
        return "Tekrar söyleyin."

def is_voice_appointment_complete(collected_info):
    """Sesli randevu tamamlanmış mı kontrolü"""
    required_fields = ['name', 'vehicle_type', 'date', 'time']
    return all(field in collected_info and collected_info[field] for field in required_fields)

@app.route('/make-call', methods=['GET'])
def make_call():
    """Twilio üzerinden arama başlat"""
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        call = client.calls.create(
            url="https://4a82-159-146-96-133.ngrok-free.app/voice",
            to=MY_PHONE_NUMBER,
            from_=TWILIO_PHONE_NUMBER,
            timeout=30
        )
        
        return jsonify({
            "message": "Arama başlatıldı",
            "call_sid": call.sid,
            "status": call.status
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/request-callback', methods=['POST'])
def request_callback():
    """Geri arama talebi al ve müşteriyi ara"""
    try:
        data = request.get_json()
        
        required_fields = ['phone', 'vehicle_type']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Eksik bilgi', 'success': False}), 400
        
        phone_number = data['phone'].replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        if phone_number.startswith('0'):
            phone_number = '90' + phone_number[1:]
        elif phone_number.startswith('5'):
            phone_number = '90' + phone_number
        elif not phone_number.startswith('90'):
            phone_number = '90' + phone_number
        
        callback_data = {
            'name': data.get('name', 'Callback Talebi'),
            'phone': phone_number,
            'vehicle_type': data['vehicle_type'],
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M'),
            'vehicle_price': data.get('vehicle_price', 0),
            'callback_requested': True
        }
        
        saved_callback = save_appointment(callback_data)
        
        try:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            
            call = client.calls.create(
                url="https://4a82-159-146-96-133.ngrok-free.app/voice",
                to=phone_number,
                from_=TWILIO_PHONE_NUMBER,
                timeout=30
            )
            
            return jsonify({
                'success': True,
                'message': 'Geri arama talebi alındı ve arama başlatıldı',
                'callback_id': saved_callback['id'],
                'call_sid': call.sid
            })
            
        except Exception as call_error:
            return jsonify({
                'success': True,
                'message': 'Geri arama talebi alındı, manuel arama yapılacak',
                'callback_id': saved_callback['id'],
                'note': 'Otomatik arama başlatılamadı'
            })
        
    except Exception as e:
        return jsonify({'error': 'Sistem hatası', 'success': False}), 500

def extract_appointment_from_single_message(message):
    """Tek mesajdan randevu bilgilerini çıkar - ESKİ BİLGİLERİ KULLANMA"""
    try:
        import re
        from datetime import datetime, timedelta
        
        appointment_info = {
            'name': None,
            'phone': None,
            'vehicle_type': None,
            'date': None,
            'time': None
        }
        
        message_lower = message.lower()
        print(f"🔍 DEBUG - Tek mesaj analizi: '{message}'")
        
        # İSİM TESPİTİ 
        name_patterns = [
            r'([A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)',
            r'([a-zA-ZçğıöşüÇĞİÖŞÜ]+\s+[a-zA-ZçğıöşüÇĞİÖŞÜ]+)',
            r'isim.*?([a-zA-ZçğıöşüÇĞİÖŞÜ\s]+)',
            r'ben\s+([a-zA-ZçğıöşüÇĞİÖŞÜ\s]+)',
        ]
        
        # Önce mesajın başındaki kelimelerden isim arama
        words = message.split()
        if len(words) >= 2:
            first_two_words = f"{words[0]} {words[1]}"
            car_words = ['toyota', 'honda', 'volkswagen', 'mercedes', 'civic', 'corolla', 'golf', 'otomobil', 'suv', 'karavan', 'randevu', 'telefon', 'saat', 'yarın', 'pazartesi', 'salı', 'çarşamba', 'perşembe', 'cuma', 'cumartesi', 'pazar']
            
            # İlk iki kelime araba kelimesi değilse ve sadece harfse isim olabilir
            if (not any(car in first_two_words.lower() for car in car_words) and 
                re.match(r'^[a-zA-ZçğıöşüÇĞİÖŞÜ]+\s+[a-zA-ZçğıöşüÇĞİÖŞÜ]+$', first_two_words) and
                len(first_two_words) > 4):
                appointment_info['name'] = first_two_words.title()
                print(f"👤 DEBUG - İsim bulundu (başta): {appointment_info['name']}")
        
        # Eğer bulunamadıysa pattern'lerle ara
        if not appointment_info['name']:
            for pattern in name_patterns:
                matches = re.findall(pattern, message)
                for match in matches:
                    name = str(match).strip()
                    car_words = ['toyota', 'honda', 'volkswagen', 'mercedes', 'civic', 'corolla', 'golf', 'otomobil', 'suv', 'karavan', 'randevu', 'telefon']
                    
                    if name and len(name) > 2 and len(name) < 30 and not any(car in name.lower() for car in car_words):
                        if re.match(r'^[a-zA-ZçğıöşüÇĞİÖŞÜ\s]+$', name):
                            appointment_info['name'] = name.title()
                            print(f"👤 DEBUG - İsim bulundu (pattern): {appointment_info['name']}")
                            break
                if appointment_info['name']:
                    break
        
        # TELEFON TESPİTİ
        phone_patterns = [
            r'(05\d{9})',
            r'(5\d{9})',
            r'(\d{11})',
            r'(\d{10})',
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, message)
            for match in matches:
                phone = str(match).strip()
                if phone.isdigit() and len(phone) >= 10:
                    appointment_info['phone'] = phone
                    print(f"📞 DEBUG - Telefon bulundu: {appointment_info['phone']}")
                    break
            if appointment_info['phone']:
                break
        
        # ARAÇ TİPİ TESPİTİ
        vehicle_keywords = {
            'otomobil': ['otomobil', 'sedan', 'araba'],
            'suv': ['suv'],
            'karavan': ['karavan', 'kamper']
        }
        
        for vehicle_type, keywords in vehicle_keywords.items():
            for keyword in keywords:
                if keyword in message_lower:
                    appointment_info['vehicle_type'] = vehicle_type
                    print(f"🚗 DEBUG - Araç tipi bulundu: {vehicle_type}")
                    break
            if appointment_info['vehicle_type']:
                break
        
        # TARİH TESPİTİ
        if 'yarın' in message_lower:
            tomorrow = datetime.now() + timedelta(days=1)
            appointment_info['date'] = tomorrow.strftime('%Y-%m-%d')
            print(f"📅 DEBUG - Yarın tarihi: {appointment_info['date']}")
        else:
            days = {
                'pazartesi': 0, 'salı': 1, 'çarşamba': 2, 'perşembe': 3, 
                'cuma': 4, 'cumartesi': 5, 'pazar': 6
            }
            
            for day_name, day_num in days.items():
                if day_name in message_lower:
                    today = datetime.now()
                    current_weekday = today.weekday()
                    days_ahead = (day_num - current_weekday) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    target_date = today + timedelta(days=days_ahead)
                    appointment_info['date'] = target_date.strftime('%Y-%m-%d')
                    print(f"📅 DEBUG - Gün ismi ile tarih: {day_name} -> {appointment_info['date']}")
                    break
        
        # SAAT TESPİTİ
        time_patterns = [
            r'(\d{1,2}):(\d{2})',
            r'saat\s*(\d{1,2})',
            r'(\d{1,2})\s*saat'
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, message)
            for match in matches:
                try:
                    if isinstance(match, tuple) and len(match) >= 2:
                        hour = int(match[0])
                        minute = int(match[1])
                    else:
                        hour = int(match)
                        minute = 0
                    
                    if 8 <= hour <= 18:
                        appointment_info['time'] = f"{hour:02d}:{minute:02d}"
                        print(f"🕐 DEBUG - Saat bulundu: {appointment_info['time']}")
                        break
                except (ValueError, IndexError):
                    continue
            if appointment_info['time']:
                break
        
        print(f"📋 DEBUG - FINAL tek mesaj bilgileri: {appointment_info}")
        return appointment_info
        
    except Exception as e:
        print(f"❌ DEBUG - Tek mesaj analiz hatası: {e}")
        return None

def check_single_message_completeness(appointment_info):
    """Tek mesajdaki randevu bilgilerinin yeterli olup olmadığını kontrol et"""
    if not appointment_info:
        return False
    
    has_name = appointment_info.get('name') and len(str(appointment_info.get('name', '')).strip()) >= 3
    has_phone = appointment_info.get('phone') and len(str(appointment_info.get('phone', '')).strip()) >= 10
    has_vehicle = appointment_info.get('vehicle_type') and appointment_info.get('vehicle_type') in ['otomobil', 'suv', 'karavan']
    has_date = appointment_info.get('date') and appointment_info.get('date') != None
    has_time = appointment_info.get('time') and appointment_info.get('time') != None
    
    print(f"📊 DEBUG - Tek mesaj kontrol:")
    print(f"  👤 İsim: {has_name} ({appointment_info.get('name')})")
    print(f"  📞 Telefon: {has_phone} ({appointment_info.get('phone')})")
    print(f"  🚗 Araç: {has_vehicle} ({appointment_info.get('vehicle_type')})")
    print(f"  📅 Tarih: {has_date} ({appointment_info.get('date')})")
    print(f"  🕐 Saat: {has_time} ({appointment_info.get('time')})")
    
    return has_name and has_phone and has_vehicle and has_date and has_time

if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', debug=True) 