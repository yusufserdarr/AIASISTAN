# 🚗 Galeri AI Sesli Asistan Prototipi

Otomotiv ve RV galerileri için AI destekli sesli asistan prototipi. Bu sistem Twilio ile telefon görüşmesi yaparak OpenAI ChatGPT API ile doğal dil işleme kullanır.

## ✨ Özellikler

- 📞 **Twilio Entegrasyonu**: Gerçek telefon aramaları
- 🤖 **OpenAI ChatGPT**: Doğal dil anlama ve yanıt
- 📅 **Randevu Yönetimi**: Otomatik randevu alma
- 🎯 **Bilgi Toplama**: Müşteri adı, araç tipi, tarih/saat
- 🌐 **Web Arayüzü**: Modern ve kullanıcı dostu dashboard
- 💾 **JSON Veritabanı**: Basit dosya tabanlı veri saklama

## 🛠️ Kurulum

### 1. Gereksinimler

```bash
pip install -r requirements.txt
```

### 2. Çevre Değişkenlerini Ayarlama

⚠️ **ÖNEMLİ**: Bu proje artık hassas bilgileri güvenli şekilde saklamaktadır.

1. `.env.example` dosyasını kopyalayın ve `.env` olarak yeniden adlandırın:
```bash
cp .env.example .env
```

2. `.env` dosyasını açın ve kendi API anahtarlarınızı girin:

```env
# OpenRouter API Anahtarı (Zorunlu)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Twilio Credentials (Zorunlu)
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_PHONE_NUMBER=your_twilio_phone_number_here

# Flask Ayarları
SECRET_KEY=your_secret_key_here
FLASK_ENV=development
FLASK_DEBUG=True
```

**API Anahtarlarını Alma:**
- **OpenRouter**: https://openrouter.ai/ adresinden ücretsiz hesap açıp API anahtarı alabilirsiniz
- **Twilio**: https://www.twilio.com/ adresinden hesap açıp ücretsiz trial credits alabilirsiniz

### 3. Uygulamayı Başlatma

```bash
python app.py
```

Uygulama `http://localhost:5000` adresinde çalışacak.

## 🔧 Twilio Kurulumu

### 1. Ngrok ile Tunnel Oluşturma

```bash
# Ngrok kurulu değilse: https://ngrok.com/download
ngrok http 5000
```

### 2. Twilio Console Ayarları

1. [Twilio Console](https://console.twilio.com/)'a gidin
2. **Phone Numbers** > **Manage** > **Active numbers**
3. Telefon numaranızı seçin
4. **Webhook** bölümünde:
   - **A call comes in**: `https://your-ngrok-url.ngrok.io/voice`
   - **HTTP Method**: `POST`

## 📱 Kullanım

### Web Arayüzü

1. `http://localhost:5000` adresini açın
2. **AI Test Alanı** ile sistemi test edin
3. **Randevular** bölümünde gelen randevuları görün

### Telefon Görüşmesi

1. Twilio numaranızı arayın
2. Sistem sizi karşılayacak ve bilgilerinizi soracak:
   - İsminiz
   - Araç tipi tercihiniz
   - Randevu günü
   - Randevu saati
3. Bilgiler toplandıktan sonra randevu oluşturulacak

## 🎯 API Endpoints

### `POST /voice`
- **Açıklama**: Twilio webhook endpoint'i
- **Kullanım**: Twilio tarafından otomatik çağrılır

### `GET /`
- **Açıklama**: Ana dashboard sayfası
- **Döner**: HTML arayüzü

### `GET /appointments`
- **Açıklama**: Tüm randevuları JSON olarak döndürür
- **Döner**: 
```json
[
  {
    "id": 1,
    "customer_name": "Ahmet Yılmaz",
    "vehicle_type": "otomobil",
    "appointment_day": "pazartesi",
    "appointment_time": "14:00",
    "created_at": "2024-01-15T10:30:00"
  }
]
```

### `POST /test-ai`
- **Açıklama**: AI yanıtını test etmek için
- **Body**: 
```json
{
  "message": "Test mesajım"
}
```
- **Döner**:
```json
{
  "response": "AI yanıtı burada"
}
```

## 📂 Proje Yapısı

```
galeri-ai-asistan/
├── app.py              # Ana Flask uygulaması
├── requirements.txt    # Python dependencies
├── .env               # Çevre değişkenleri
├── appointments.json  # Randevu veritabanı
├── templates/
│   └── index.html     # Ana sayfa
├── static/
│   └── style.css      # CSS stilleri
└── README.md          # Bu dosya
```

## 🚀 Geliştirme Önerileri

### Production için:
- **Redis** session yönetimi için
- **PostgreSQL** kalıcı veri saklama için
- **Docker** containerization için
- **HTTPS** güvenlik için
- **Rate Limiting** API koruması için

### AI İyileştirmeleri:
- Daha gelişmiş NLP (spaCy, NLTK)
- Çok dilli destek
- Ses tanıma doğruluğu iyileştirme
- Contextual conversation memory

### Twilio İyileştirmeleri:
- SMS entegrasyonu
- Voicemail sistemi
- Call recording
- Conference calls

## ⚠️ Önemli Notlar

1. **OpenRouter API Anahtarı**: Mutlaka geçerli bir API anahtarı kullanın
2. **Twilio Credits**: Telefon görüşmeleri Twilio kredisi tüketir
3. **Ngrok**: Development için ücretsiz, production için ücretli
4. **🔒 GÜVENLİK**: 
   - `.env` dosyasını asla GitHub'a yüklemeyin
   - `.gitignore` dosyası zaten .env'i hariç tutuyor
   - Kendi API anahtarlarınızı mutlaka `.env` dosyasına girin
   - GitHub'a yüklemeden önce `git status` ile .env dosyasının dahil olmadığından emin olun

## 🐛 Sorun Giderme

### Common Issues:

**1. OpenAI API Hatası:**
```
OPENAI_API_KEY ortam değişkenini kontrol edin
```

**2. Twilio Webhook Hatası:**
```
Ngrok URL'inin doğru olduğundan emin olun
HTTPS gerekli (Ngrok otomatik sağlar)
```

**3. Sesli Yanıt Çalışmıyor:**
```
Twilio Console'da voice settings kontrol edin
Türkçe dil desteği aktif olmalı
```

## 📞 Test Senaryosu

1. **Sistemi başlatın**: `python app.py`
2. **Ngrok çalıştırın**: `ngrok http 5000`
3. **Test conversation**:
   - "Merhaba, ismim Ahmet"
   - "Otomobil almak istiyorum"
   - "Pazartesi uygun"
   - "Saat 14:00"

## 🤝 Katkıda Bulunma

1. Fork the project
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

---

**Geliştirici**: AI Asistan | **Versiyon**: 1.0.0 | **Tarih**: 2024 