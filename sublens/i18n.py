"""Interface language (English / Turkish).

The English text is the key: t("Start") returns it unchanged in English and
looks it up in TR otherwise, so a missing translation degrades to English.
"""
from __future__ import annotations

import locale

_lang = "en"


def system_lang() -> str:
    try:
        import ctypes
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        if lcid & 0x3FF == 0x1F:          # LANG_TURKISH
            return "tr"
    except Exception:
        name = (locale.getlocale()[0] or "").lower()
        if name.startswith("tr") or name.startswith("turkish"):
            return "tr"
    return "en"


def set_lang(lang: str):
    global _lang
    _lang = lang if lang in ("en", "tr") else "en"


def lang() -> str:
    return _lang


def t(text: str, *args) -> str:
    s = TR.get(text, text) if _lang == "tr" else text
    return s.format(*args) if args else s


TR = {
    # languages
    "English": "İngilizce", "Turkish": "Türkçe", "Japanese": "Japonca", "Korean": "Korece",
    "Chinese": "Çince", "French": "Fransızca", "German": "Almanca", "Spanish": "İspanyolca",
    "Russian": "Rusça", "Italian": "İtalyanca", "Portuguese": "Portekizce",
    "Polish": "Lehçe", "Auto-Detect": "Otomatik algıla",

    # main window
    "Interface language": "Arayüz dili",
    "Help": "Yardım",
    "Settings": "Ayarlar",
    "Game profile": "Oyun profili",
    "Game profiles remember the area and reading settings per game, and switch "
    "automatically when that game is active.":
        "Oyun profilleri alanı ve okuma ayarlarını oyun bazında hatırlar, o oyun "
        "açıkken otomatik devreye girer.",
    "Save / delete game profiles": "Oyun profili kaydet / sil",
    "Save current settings as a game profile…": "Mevcut ayarları oyun profili olarak kaydet…",
    "Delete this profile": "Bu profili sil",
    "None": "Yok",
    "OCR view": "OCR görünümü",
    "Show what the OCR actually sees (after filtering)":
        "OCR'ın gerçekte ne gördüğünü göster (filtrelenmiş hali)",
    "1 · Subtitle area": "1 · Altyazı alanı",
    "Drag a box around both subtitle lines in the game.":
        "Oyunda iki altyazı satırını da kapsayan bir kutu çiz.",
    "Select area": "Alan seç",
    "No area selected": "Alan seçilmedi",
    "2 · Language and translator": "2 · Dil ve çevirmen",
    "Swap languages": "Dilleri değiştir",
    "3 · Text style": "3 · Metin stili",
    "Auto": "Otomatik",
    "Bright subtitle": "Parlak altyazı",
    "Dialog box": "Diyalog kutusu",
    "Tries the raw frame and the bright-subtitle filter, keeps the cleaner text.":
        "Ham görüntüyü ve parlak altyazı filtresini dener, daha temiz metni seçer.",
    "White / outlined / shadowed subtitles over busy scenes.":
        "Karışık sahnelerde beyaz / kenarlıklı / gölgeli altyazılar.",
    "Dialog boxes and menus on a flat background.":
        "Düz arka planlı diyalog kutuları ve menüler.",
    "Auto-tune": "Otomatik ayarla",
    "Tries every reading setting on the current frame and keeps the one that produces "
    "the cleanest text. Do it while a subtitle is visible.":
        "Mevcut karede tüm okuma ayarlarını dener ve en temiz metni veren ayarı seçer. "
        "Ekranda altyazı varken kullan.",
    "Translate once": "Tek çeviri",
    "Start": "Başlat",
    "Stop": "Durdur",
    "Original text": "Orijinal metin",
    "Translations appear here and over the game.": "Çeviriler burada ve oyunun üstünde görünür.",
    "Log": "Kayıt",
    "Idle": "Beklemede",
    "Reading": "Okuyor",
    "Paused": "Duraklatıldı",
    "Translating…": "Çevriliyor…",
    "Ready · Windows OCR": "Hazır · Windows OCR",
    "Area: {}": "Alan: {}",
    "Preview failed: {}": "Önizleme alınamadı: {}",
    "Source and target language are the same.": "Kaynak ve hedef dil aynı.",
    "Stopped.": "Durduruldu.",
    "Stopped": "Durduruldu",
    "Started · {}": "Başladı · {}",
    "Reading… switch to your game": "Okuyor… oyuna geç",
    "Reading…": "Okuyor…",
    "Paused - game not active": "Duraklatıldı - oyun aktif değil",
    "Overlay pinned where you dropped it (Settings > Overlay to change).":
        "Çeviri katmanı bıraktığın yere sabitlendi (değiştirmek için Ayarlar > Çeviri katmanı).",
    "Trying reading settings…": "Okuma ayarları deneniyor…",
    "No readable text found - make sure a subtitle is on screen while tuning.":
        "Okunabilir metin bulunamadı - ayarlarken ekranda altyazı olduğundan emin ol.",
    "Best: {} · {}x  →  “{}”": "En iyisi: {} · {}x  →  “{}”",
    "Save game profile": "Oyun profili kaydet",
    "Profile name (e.g. the game's name):": "Profil adı (örn. oyunun adı):",
    "Switch automatically?": "Otomatik geçilsin mi?",
    "Use this profile automatically whenever {} is the active game?":
        "{} aktif oyun olduğunda bu profil otomatik kullanılsın mı?",
    "Profile saved: {}": "Profil kaydedildi: {}",
    "Profile: {}": "Profil: {}",
    "Game window: {}": "Oyun penceresi: {}",
    "Global shortcuts unavailable: {}": "Global kısayollar kullanılamıyor: {}",
    "Settings saved": "Ayarlar kaydedildi",
    "Show / hide": "Göster / gizle",
    "Start / stop": "Başlat / durdur",
    "Hide overlay": "Çeviri katmanını gizle",
    "Quit": "Çıkış",
    "Still running in the tray · right-click it to quit":
        "Sistem tepsisinde çalışmaya devam ediyor · çıkmak için sağ tıkla",
    "Drag a box around where the subtitles appear  ·  include both lines and some "
    "margin  ·  Esc to cancel":
        "Altyazının çıktığı yerin etrafına kutu çiz  ·  iki satırı da biraz payla "
        "kapsa  ·  iptal için Esc",

    "No area selected yet.\nPress F2 and drag a box around the subtitles in your game.":
        "Henüz alan seçilmedi.\nF2'ye bas ve oyundaki altyazının etrafına bir kutu çiz.",
    "The original text appears here.": "Orijinal metin burada görünür.",
    "Filtered view": "Filtreli görünüm",
    "Show the area the way the OCR sees it, after filtering":
        "Alanı OCR'ın gördüğü şekilde, filtrelenmiş haliyle göster",
    "Screen": "Ekran",
    "Select": "Seç",
    "Change": "Değiştir",
    "Not selected": "Seçilmedi",
    "Subtitle area": "Altyazı alanı",
    "Text style": "Metin stili",
    "Languages": "Diller",
    "Translator": "Çevirmen",
    "Game": "Oyun",
    "Manage": "Yönet",
    "Show log": "Kayıtları göster",
    "Hide log": "Kayıtları gizle",
    "Only AI engines translate short replies from the conversation's context.":
        "Kısa cevapları konuşmanın bağlamına göre yalnızca AI motorları çevirebilir.",
    "AI (OpenAI-compatible)": "AI (OpenAI uyumlu)",

    # engines
    "Connection failed: {}": "Bağlantı kurulamadı: {}",
    "Request failed": "İstek başarısız",
    "DeepL API key is empty (Settings > Translation)":
        "DeepL API anahtarı boş (Ayarlar > Çeviri)",
    "{:,} / {:,} characters used": "{:,} / {:,} karakter kullanıldı",
    "The 'anthropic' package is missing: pip install anthropic":
        "'anthropic' paketi eksik: pip install anthropic",
    "Invalid Anthropic API key": "Geçersiz Anthropic API anahtarı",
    "Unknown model '{}'": "Bilinmeyen model '{}'",
    "Rate limited by Anthropic - slow down or try later":
        "Anthropic istek sınırına takıldı - biraz bekleyip tekrar dene",
    "Anthropic API error {}: {}": "Anthropic API hatası {}: {}",
    "Could not reach the Anthropic API": "Anthropic API'ye ulaşılamadı",
    "Claude declined to translate this line": "Claude bu satırı çevirmeyi reddetti",
    "Unexpected response from Google": "Google'dan beklenmeyen yanıt",
    "Empty response": "Boş yanıt",
    "Gemini API key is empty (Settings > Translation)":
        "Gemini API anahtarı boş (Ayarlar > Çeviri)",
    "Gemini returned no text": "Gemini metin döndürmedi",
    "Key OK, but '{}' not found. Available: {}": "Anahtar geçerli ama '{}' bulunamadı. Mevcut: {}",
    "Key OK - {} available": "Anahtar geçerli - {} kullanılabilir",
    "No model loaded on the AI server": "AI sunucusunda yüklü model yok",
    "Unexpected response: {}": "Beklenmeyen yanıt: {}",
    "Connected - {} model(s)": "Bağlandı - {} model",

    # pipeline / OCR
    "Engine too slow, skipped: {}": "Çevirmen yetişemedi, atlandı: {}",
    "Translation error: {}": "Çeviri hatası: {}",
    "Read error: {}": "Okuma hatası: {}",
    "Select the subtitle area first": "Önce altyazı alanını seç",
    "No text found in the area.": "Alanda metin bulunamadı.",
    "The text looks Turkish but the source language is {} - change it, or reading "
    "and translation suffer.":
        "Metin Türkçe görünüyor ama kaynak dil {} - değiştir, yoksa okuma ve çeviri bozulur.",
    "The text doesn't look like {} - check the source language, or reading and "
    "translation suffer.":
        "Metin {} gibi görünmüyor - kaynak dili kontrol et, yoksa okuma ve çeviri bozulur.",
    "Windows OCR is unavailable (needs Windows 10/11 and the winrt packages from "
    "requirements.txt).":
        "Windows OCR kullanılamıyor (Windows 10/11 ve requirements.txt'deki winrt "
        "paketleri gerekli).",
    "Windows OCR has no '{}' language pack. Install it from Settings > Time & language > "
    "Language > Add a language (tick 'Optical character recognition'), or in an admin "
    "PowerShell:  Add-WindowsCapability -Online -Name \"Language.OCR~~~{}~0.0.1.0\"":
        "Windows OCR'da '{}' dil paketi yok. Windows Ayarları > Saat ve dil > Dil > Dil "
        "ekle yolundan kur ('Optik karakter tanıma' işaretli olsun) ya da yönetici "
        "PowerShell'de:  Add-WindowsCapability -Online -Name \"Language.OCR~~~{}~0.0.1.0\"",

    # engine notes
    "Free, no key. Unofficial endpoint - Google may rate-limit it.":
        "Ücretsiz, anahtar gerekmez. Gayri resmi uç nokta - Google yoğun kullanımı kısıtlayabilir.",
    "Best quality machine translation. Free plan: 500k characters / month.":
        "En kaliteli makine çevirisi. Ücretsiz plan: ayda 500 bin karakter.",
    "LM Studio / Ollama (local, offline) or OpenAI, OpenRouter, Groq (API key).":
        "LM Studio / Ollama (yerel, internetsiz) ya da OpenAI, OpenRouter, Groq (API anahtarı).",
    "Anthropic API key. Haiku is the fastest/cheapest for live subtitles.":
        "Anthropic API anahtarı. Canlı altyazı için en hızlı/ucuz model Haiku.",
    "Google AI Studio API key (has a free tier).":
        "Google AI Studio API anahtarı (ücretsiz katmanı var).",

    # settings
    "Translation": "Çeviri",
    "Screen reading": "Okuma",
    "Overlay": "Çeviri katmanı",
    "General": "Genel",
    "Save": "Kaydet",
    "Cancel": "İptal",
    "Working...": "Çalışıyor...",
    "Configure:": "Ayarla:",
    "No setup needed. It uses Google's free web endpoint, which can occasionally "
    "rate-limit heavy use - switch engine for a while if it does.":
        "Kurulum gerekmez. Google'ın ücretsiz web uç noktasını kullanır; yoğun kullanımda "
        "ara sıra kısıtlayabilir - olursa bir süre başka motora geç.",
    "API key": "API anahtarı",
    "deepl.com > API > 'DeepL API Free' (500,000 characters/month). Free keys end with "
    "':fx'. Previous lines are sent as context.":
        "deepl.com > API > 'DeepL API Free' (ayda 500.000 karakter). Ücretsiz anahtarlar "
        "':fx' ile biter. Önceki satırlar bağlam olarak gönderilir.",
    "empty = first loaded model": "boş = ilk yüklü model",
    "Service": "Servis",
    "Base URL": "Adres",
    "Model": "Model",
    "LM Studio: load a model and start the local server. Ollama: run 'ollama serve'. "
    "Cloud services need an API key. Local models are offline and private but use "
    "GPU/RAM next to the game.":
        "LM Studio: bir model yükle ve yerel sunucuyu başlat. Ollama: 'ollama serve' "
        "çalıştır. Bulut servisleri API anahtarı ister. Yerel modeller internetsiz ve "
        "gizlidir ama oyunla birlikte GPU/RAM kullanır.",
    "Key from console.anthropic.com (empty = ANTHROPIC_API_KEY). Opus gives the best "
    "translations; Haiku is much faster and cheaper for fast-paced dialogue.":
        "Anahtar: console.anthropic.com (boş = ANTHROPIC_API_KEY). En iyi çeviriyi Opus "
        "verir; hızlı diyaloglar için Haiku çok daha hızlı ve ucuzdur.",
    "Key from aistudio.google.com. 'Test' lists the models your key can use.":
        "Anahtar: aistudio.google.com. 'Test' anahtarının kullanabildiği modelleri listeler.",
    "Game context (AI engines)": "Oyun bağlamı (AI motorları)",
    "e.g. Red Dead Redemption 2 - Wild West 1899, outlaw gang slang":
        "örn. Red Dead Redemption 2 - 1899 Vahşi Batı, kanun kaçağı çete argosu",
    "Glossary": "Sözlük",
    "One per line. 'Dutch' keeps the word untranslated, 'Saint Denis=Saint-Denis' "
    "forces a rendering. # starts a comment.":
        "Her satıra bir kural. 'Dutch' kelimeyi çevirmeden bırakır, "
        "'Spider-Man=Örümcek Adam' belirli bir karşılığı zorlar. # yorum başlatır.",
    "Test": "Test",
    "Text is read with Windows OCR. Installed languages: {}. Add more under Windows "
    "Settings > Time & language > Language (tick 'Optical character recognition').":
        "Metin Windows OCR ile okunur. Kurulu diller: {}. Daha fazlası için Windows "
        "Ayarları > Saat ve dil > Dil ('Optik karakter tanıma' işaretli olsun).",
    "Automatic": "Otomatik",
    "Upscale": "Büyütme",
    "Read every": "Okuma aralığı",
    "The area is only OCR'd when its pixels change, so short intervals are cheap.":
        "Alan yalnızca pikselleri değişince okunur, bu yüzden kısa aralık ucuzdur.",
    "Wait until the text stops changing before translating":
        "Çevirmeden önce metnin değişmesinin bitmesini bekle",
    "Avoids translating half-faded or typewriter text. Adds one read of delay.":
        "Yarım belirmiş ya da daktilo efektli metnin çevrilmesini önler. Bir okuma kadar gecikme ekler.",
    "Context lines": "Bağlam satırları",
    "Previous lines sent along (AI engines and DeepL) for consistent pronouns, gender "
    "and tone.":
        "Zamir, cinsiyet ve ton tutarlılığı için gönderilen önceki satırlar (AI motorları ve DeepL).",
    "Show translations over the game": "Çevirileri oyunun üstünde göster",
    "Font size": "Yazı boyutu",
    "Background": "Arka plan",
    "Above the subtitle area": "Altyazı alanının üstünde",
    "Below the subtitle area": "Altyazı alanının altında",
    "Where I drag it": "Sürüklediğim yerde",
    "Position": "Konum",
    "Also show the original text (small)": "Orijinal metni de göster (küçük)",
    "Click-through (mouse goes to the game; can't be dragged)":
        "Tıklamalar oyuna geçsin (fare oyuna gider; sürüklenemez)",
    "Hide after subtitle ends": "Altyazı bitince gizle",
    "0 = keep the last translation on screen. Drag the overlay to move it; right-click "
    "hides it.":
        "0 = son çeviri ekranda kalır. Taşımak için sürükle; sağ tık gizler.",
    "Same as Windows": "Windows ile aynı",
    "Global shortcuts (work while the game is focused)":
        "Global kısayollar (oyun öndeyken de çalışır)",
    "F2 / Ctrl+Alt+R  select area   ·   F3 / Ctrl+Alt+T  translate once\n"
    "F4 / Ctrl+Alt+G  start/stop   ·   Ctrl+Alt+H  hide overlay\n"
    "Some games run as administrator - then SubLens must too.":
        "F2 / Ctrl+Alt+R  alan seç   ·   F3 / Ctrl+Alt+T  tek çeviri\n"
        "F4 / Ctrl+Alt+G  başlat/durdur   ·   Ctrl+Alt+H  çeviriyi gizle\n"
        "Bazı oyunlar yönetici olarak çalışır - o zaman SubLens de öyle açılmalı.",
    "Pause reading while the game is not the active window":
        "Oyun aktif pencere değilken okumayı duraklat",
    "Closing the window keeps SubLens in the tray":
        "Pencereyi kapatınca SubLens sistem tepsisinde kalsın",
    "Show Windows notifications": "Windows bildirimlerini göster",
}
