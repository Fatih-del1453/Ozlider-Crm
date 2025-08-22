import pandas as pd
import warnings

# Olası uyarıları görmezden gel, sadece temel bilgilere odaklan
warnings.simplefilter(action='ignore', category=FutureWarning)

print("--- Teşhis Raporu Başlangıcı ---")
try:
    # Dosyayı oku
    dosya_adi = 'satis-hedef.xls'
    df = pd.read_excel(dosya_adi, header=None)
    
    print(f"\n1. '{dosya_adi}' dosyası başarıyla okundu.")
    
    # Dosyanın ilk 25 satırını HAM haliyle, hiçbir işlem yapmadan göster
    print("\n2. Dosyanın ilk 25 satırı (Ham Veri):\n")
    print(df.head(25).to_string())
    
    # Pandas'ın her sütun için tahmin ettiği veri tiplerini göster
    print("\n\n3. Sütunların Ham Veri Tipleri:\n")
    print(df.dtypes)

except Exception as e:
    print(f"\n!!! HATA !!! Dosya okunurken bir sorun oluştu: {e}")
    
print("\n--- Teşhis Raporu Sonu ---")
print("\nLütfen yukarıdaki raporun tamamını (bu satır dahil) kopyalayıp bana gönderin.")