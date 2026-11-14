# SubLens

Oyundaki altyazıları ve diyalogları ekrandan okuyup anında çeviren Windows uygulaması. Çeviri, oyunun üstünde orijinal altyazı gibi görünen bir **overlay** olarak gösterilir.

## Hızlı başlangıç (3 adım)

1. **Alan seç (F2):** Oyunda altyazının çıktığı yerin etrafına kutu çiz. İki satırlık altyazılar için **iki satırı da** kapsayacak, biraz da pay bırakacak şekilde çiz.
2. **Dil ve çevirmen seç:** Örneğin English → Turkish, Google Translate (kurulum gerektirmez).
3. **Başlat (F4)** ve oyuna geç. Çeviri altyazının üstünde görünür.

Okuma kötüyse ekranda bir altyazı varken **Otomatik ayarla** düğmesine bas. Tüm okuma ayarları denenir ve en temiz metni veren ayar seçilir.

## Metin stili

| Stil | Ne zaman |
|---|---|
| **Otomatik** | Çoğu oyun. Ham görüntüyü ve parlak altyazı filtresini birlikte dener, daha anlamlı metni seçer. |
| **Parlak altyazı** | Beyaz, kenarlıklı ya da gölgeli altyazılar (RDR2, Spider-Man 2, GTA…). Karışık ve parlak arka planlarda en iyisi. |
| **Diyalog kutusu** | Düz renkli kutu içindeki diyaloglar ve menüler. |

**Filtreli görünüm** düğmesi OCR'ın gerçekte ne gördüğünü gösterir.

## Çevirmenler

| Motor | Kurulum | Not |
|---|---|---|
| **Google Translate** | Yok | Hızlı ve ücretsiz. Gayri resmi uç nokta olduğu için yoğun kullanımda geçici olarak engellenebilir. |
| **DeepL** | API anahtarı (ücretsiz plan: 500k karakter/ay) | Makine çevirisi içinde en kaliteli seçenek. Önceki satırları bağlam olarak kullanır. |
| **AI (OpenAI uyumlu)** | LM Studio / Ollama (yerel, internetsiz) ya da OpenAI, OpenRouter, Groq anahtarı | Oyun bağlamını, sözlüğü ve önceki satırları anlar. |
| **Claude** | Anthropic API anahtarı | Opus en kaliteli seçenek, Haiku hızlı diyaloglar için daha hızlı ve ucuz. |
| **Gemini** | Google AI Studio anahtarı | Ücretsiz katmanı var. |
| **Çeviri yok** | Yok | Metni çevirmeden, okunduğu gibi gösterir. İnternetsiz çalışır. Zaten bildiğin dildeki küçük ya da bulanık yazıları okumak için çeviri kutusunun yazı boyutunu Ayarlar > Çeviri katmanı'ndan büyüt. |

Ayarlar > Çeviri sekmesinde her motorun **Test** düğmesi var.

**Oyun bağlamı** (örn. *"Red Dead Redemption 2, 1899 Vahşi Batı, çete argosu"*) AI motorlarının tonu doğru tutturmasını sağlar.

**Sözlük:** Her satıra bir kural yazılır. `Dutch` yazmak kelimeyi çevirmeden bırakır, `Spider-Man=Örümcek Adam` belirli bir karşılığı zorlar.

## Oyun profilleri

**Oyun profili > Yönet > Mevcut ayarları oyun profili olarak kaydet** seçeneği alanı, dili, okuma ayarlarını, bağlamı ve sözlüğü oyun bazında kaydeder. Kaydederken oyunun exe'sine bağlarsan, o oyun açıkken taramayı başlattığında profil kendiliğinden yüklenir.

## Kısayollar

| Tuş | Global alternatif | İşlev |
|---|---|---|
| F2 | Ctrl+Alt+R | Alan seç |
| F3 | Ctrl+Alt+T | Tek seferlik çeviri |
| F4 | Ctrl+Alt+G | Başlat / durdur |
| Esc | Ctrl+Alt+H | Overlay'i gizle |

Global kısayollar oyun tam ekrandayken de çalışır. Oyun yönetici olarak çalışıyorsa SubLens'i de yönetici olarak açman gerekir. Klavyende F tuşları yoksa Ctrl+Alt kısayollarını ya da penceredeki düğmeleri kullan.

## Çeviri katmanı

- Genişliği altyazı metnine göre ayarlanır, bu yüzden iki satırlık bir altyazının çevirisi de iki satır olarak görünür.
- Sürükleyerek taşınabilir (bırakıldığı yere sabitlenir). Sağ tık gizler. Durdur'a basınca kapanır.
- Tıklamaların oyuna geçmesi açıksa sürüklenemez.
- Ayarlar > Çeviri katmanı: yazı boyutu, arka plan saydamlığı, konum, orijinal metni de gösterme, tıklamaların oyuna geçmesi, altyazı bitince gizlenme süresi.
- Katman ekran yakalamaya görünmez, bu yüzden alanın üstüne gelse bile kendi çevirisini tekrar okumaz.

## Okuma nasıl çalışıyor

- Okuma **Windows OCR** ile yapılır (Windows 10/11'de yerleşik, kare başına ~10-30 ms). Ek bir program kurmak gerekmez, yalnızca kaynak dilin Windows OCR paketi kurulu olmalıdır.
- **Kayan altyazılar** (YouTube, yayınlar, bazı oyunlar) otomatik algılanır. Önceki ekranda olan satırlar tekrar çevrilmez, yeni kelimeler cümle bitince tek seferde çevrilir. Çevirmen yavaşsa bekleyen parçalar birleştirilir, hiçbiri atlanmaz.
- Alan yalnızca piksel değiştiğinde okunur, bu yüzden kısa okuma aralığı (0,25 s) bile ucuzdur.
- Metin iki okuma boyunca aynı kalınca çevrilir. Böylece belirmekte olan ya da daktilo efektli yazılar yarım çevrilmez.
- Yarı saydam haldeyken bozuk okunan metin, düzgün okunması için en fazla 1,2 saniye bekletilir. Bozuk satır yine de çevrildiyse 3 saniye içinde gelen temiz okuma onun yerine geçer. Aynı altyazının kaybolurken bozulan okumaları yeniden çevrilmez.
- Konuşmacı etiketleri düzeltilir: iki nokta ile iki kez görülen bir ad öğrenilir, sonra "eter:", ".Harry•." ya da "Peter." gibi bozuk halleri "Peter:" olur.
- Okuma ve çeviri ayrı thread'lerde çalışır. Yavaş bir motor ekran okumasını durdurmaz, bu yüzden satır kaçmaz.
- Alt alta gelen satırlar tek cümle olarak çevrilir. `ARTHUR:` gibi bir konuşmacı etiketi yeni paragraf başlatır.
- **Konuşma bağlamı:** AI motorlarına önceki satırlar kendi çevirileriyle birlikte gider. Bu sayede kısa cevaplar önceki cümleye göre çevrilir ("Bunu denemelisin." → "Neyi?" = "Try what?"). 90 saniyeden eski satırlar yeni sahne sayılır ve bağlama girmez. Google bağlam kullanamaz, bunun için bir AI motoru seç.
- Kumanda/tuş ikonları, semboller ve küçük UI ipuçları ("Hold E to skip") metinden ayıklanır.

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| "Windows OCR'da '…' dil paketi yok" | Windows Ayarları > Saat ve dil > Dil > dil ekle ("Optik karakter tanıma" işaretli olsun). |
| "Metin … gibi görünmüyor" | Kaynak dil yanlış seçilmiş. Örneğin Türkçe bir video için kaynak dil **Türkçe** olmalı. |
| Metin bozuk okunuyor | Altyazı ekrandayken **Otomatik ayarla**. Olmazsa **Parlak altyazı**'ı dene, alanı yalnızca altyazıyı kapsayacak şekilde daralt. |
| Hiç metin yok | **Filtreli görünüm** ile kontrol et. Alan doğru yerde mi? |
| Konuşmacı adının ilk harfleri eksik | Alan adı kesiyor. Alanı soldan biraz genişlet. |
| Çeviri gecikiyor | Google veya DeepL yerel modellerden hızlıdır. Claude'da Haiku modelini seç. |
| Google hata veriyor | Bir süre DeepL veya başka bir motora geç. |
| Kısayollar oyunda çalışmıyor | SubLens'i yönetici olarak çalıştır. |

Arayüz dili sağ üstteki **EN / TR** düğmesiyle (ya da Ayarlar > Genel) değiştirilir. Windows bildirimleri de Ayarlar > Genel'den kapatılır.

SubLens açılışta GitHub'da yeni sürüm olup olmadığına bakar. Yeni sürüm varsa sürüm notlarını gösterir ve İndir düğmesiyle yeni exe'yi indirir. Bu kontrol Ayarlar > Genel'den kapatılabilir, Yardım penceresindeki **Güncellemeleri kontrol et** düğmesiyle de elle yapılabilir.

Ayarlar `%APPDATA%\SubLens\config.json` dosyasında tutulur. Eski sürümün ayarları otomatik taşınır. Dosya bozulursa silmek yeterlidir.

## Geliştirici

```
pip install -r requirements.txt
python main.py                      # çalıştır
python -m unittest discover tests   # testler
sublens_exe.bat                     # tek dosya exe
```

Kod düzeni: `sublens/ocr.py` (okuma), `textproc.py` (ikon filtresi, satır birleştirme, sözlük), `pipeline.py` (tarama ve çeviri thread'leri), `engines/` (çeviri motorları), `ui/` (arayüz). v1'in tek dosyalık sürümü GitHub'daki `1.0` etiketinde duruyor.
