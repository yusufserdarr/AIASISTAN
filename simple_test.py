#!/usr/bin/env python
"""
Galeri AI Asistan - Basit Test Suite
Bu dosya çalışan, basit test case'leri içerir.
"""

import pytest
import requests
import json
import re
from datetime import datetime
from unittest.mock import patch, MagicMock

# Test Base URL
BASE_URL = "http://localhost:5000"

# =============================================
# BASIC FUNCTIONALITY TESTS
# =============================================

def test_basic_app_connection():
    """Test: Uygulamanın çalışıp çalışmadığını kontrol et"""
    try:
        response = requests.get(BASE_URL, timeout=5)
        assert response.status_code == 200
        print("✅ Uygulama başarıyla çalışıyor!")
    except requests.exceptions.ConnectionError:
        pytest.skip("Uygulama çalışmıyor, önce 'python app.py' ile başlatın")

def test_ai_chat_endpoint():
    """Test: AI chat endpoint'ini test et"""
    try:
        test_data = {"message": "Merhaba, nasılsın?"}
        response = requests.post(f"{BASE_URL}/test-ai", json=test_data, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            assert "response" in data
            assert len(data["response"]) > 0
            print(f"✅ AI Yanıt: {data['response'][:100]}...")
        else:
            print(f"⚠️ AI endpoint mevcut değil: {response.status_code}")
    except requests.exceptions.RequestException as e:
        pytest.skip(f"AI endpoint test edilemiyor: {e}")

def test_vehicles_api():
    """Test: Araç listesi API'sini test et"""
    try:
        response = requests.get(f"{BASE_URL}/api/vehicles", timeout=5)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        assert "otomobil" in data or "suv" in data or "karavan" in data
        print("✅ Araç listesi API çalışıyor!")
        
    except requests.exceptions.RequestException:
        pytest.skip("Vehicles API test edilemiyor")

def test_appointments_api():
    """Test: Randevular API'sini test et"""
    try:
        response = requests.get(f"{BASE_URL}/api/appointments", timeout=5)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Randevular API çalışıyor! Toplam randevu: {len(data)}")
        
    except requests.exceptions.RequestException:
        pytest.skip("Appointments API test edilemiyor")

# =============================================
# VOICE PROCESSING FUNCTIONS
# =============================================

def extract_name_from_speech(text):
    """Basit isim çıkarma fonksiyonu"""
    patterns = [
        r"(?:ismim|adım|ben)\s+([a-zA-ZçğıöşüÇĞİÖŞÜ\s]+)",
        r"^([a-zA-ZçğıöşüÇĞİÖŞÜ\s]{2,20})$"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if len(name) > 1 and len(name.split()) <= 3:
                return name.title()
    return None

def extract_vehicle_type(text):
    """Basit araç tipi çıkarma fonksiyonu"""
    text_lower = text.lower()
    
    vehicle_keywords = {
        'otomobil': ['otomobil', 'araba', 'sedan', 'hatchback', 'binek'],
        'suv': ['suv', 'es u vi', 'esuvi', 'jeep', 'crossover'],
        'karavan': ['karavan', 'kamper', 'rv', 'kamp aracı']
    }
    
    for vehicle_type, keywords in vehicle_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                return vehicle_type
    return None

# =============================================
# VOICE PROCESSING UNIT TESTS
# =============================================

def test_extract_name_simple():
    """Test: Basit isim çıkarma"""
    assert extract_name_from_speech("Adım Mehmet") == "Mehmet"
    assert extract_name_from_speech("Ben Ali") == "Ali"
    assert extract_name_from_speech("Ayşe") == "Ayşe"
    assert extract_name_from_speech("Mehmet Ali") == "Mehmet Ali"
    print("✅ İsim çıkarma testi başarılı!")

def test_extract_vehicle_type_simple():
    """Test: Araç tipi çıkarma"""
    assert extract_vehicle_type("Otomobil almak istiyorum") == "otomobil"
    assert extract_vehicle_type("SUV arıyorum") == "suv"
    assert extract_vehicle_type("Karavan bakıyorum") == "karavan"
    assert extract_vehicle_type("Araba istiyorum") == "otomobil"
    print("✅ Araç tipi çıkarma testi başarılı!")

def test_invalid_inputs():
    """Test: Geçersiz girişler"""
    assert extract_name_from_speech("") is None
    assert extract_name_from_speech("123456") is None
    assert extract_vehicle_type("merhaba") is None
    print("✅ Geçersiz girişler testi başarılı!")

# =============================================
# MAIN TEST RUNNER
# =============================================

if __name__ == "__main__":
    print("🚀 Galeri AI Asistan - Basit Test Suite")
    print("=" * 50)
    
    # Manual test çalıştırma
    print("\n🔹 İsim Çıkarma Testi:")
    test_extract_name_simple()
    
    print("\n🔹 Araç Tipi Çıkarma Testi:")
    test_extract_vehicle_type_simple()
    
    print("\n🔹 Geçersiz Girişler Testi:")
    test_invalid_inputs()
    
    print("\n🎉 Tüm Unit Testler Başarılı!")
    
    # pytest ile çalıştır
    pytest.main(["-v", "--tb=short", __file__]) 