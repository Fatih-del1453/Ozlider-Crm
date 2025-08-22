import pandas as pd

# --- KULLANICI AYARLARI ---
DOSYA_YOLU = 'rapor.xls'

# !!! İŞTE DÜZELTME BURADA !!!
# Temsilci isimlerinin olduğu sütunun başlığı 'Satış Temsilcisi' değil, 'ST' imiş.
TEMSILCI_SUTUNU = 'ST' 

MUSTERI_SUTUNU = 'Müşteri'
TUTAR_SUTUNU = 'Kalan Tutar Total' 

# --- KODUN ANA GÖVDESİ ---
try:
    df = pd.read_excel(DOSYA_YOLU)
    print(f"'{DOSYA_YOLU}' başarıyla okundu.")
    
    # İsimlerin olduğu 'ST' sütunundaki tüm verileri metin (string) formatına dönüştür.
    df[TEMSILCI_SUTUNU] = df[TEMSILCI_SUTUNU].astype(str)

    temsilci_adi = input("Raporu istenen temsilcinin adının bir parçasını yazın -> ")

    # Büyük/küçük harfe duyarsız ve ismin bir parçasını içermesine göre DOĞRU SÜTUNDA filtrele
    temsilci_df = df[df[TEMSILCI_SUTUNU].str.contains(temsilci_adi.strip(), case=False, na=False)]

    if temsilci_df.empty:
        print(f"\nHATA: İçinde '{temsilci_adi}' geçen bir satış temsilcisi bulunamadı.")
    else:
        bulunan_isimler = temsilci_df[TEMSILCI_SUTUNU].unique()
        print(f"\nBulunan temsilci(ler): {', '.join(bulunan_isimler)}")
        
        toplam_bakiye = temsilci_df[TUTAR_SUTUNU].sum()
        musteri_bazinda_bakiye = temsilci_df.groupby(MUSTERI_SUTUNU)[TUTAR_SUTUNU].sum()
        musteri_bazinda_bakiye = musteri_bazinda_bakiye[musteri_bazinda_bakiye > 0]
        
        print("\n" + "="*40)
        print(f"         RAPOR SONUCU")
        print("="*40)
        print(f"\nGENEL TOPLAM ALACAK: {toplam_bakiye:,.2f} TL")
        print("-"*40)

        if not musteri_bazinda_bakiye.empty:
            print("\nMÜŞTERİ BAZINDA BAKİYE DÖKÜMÜ:")
            dokum_df = musteri_bazinda_bakiye.reset_index()
            dokum_df = dokum_df.rename(columns={TUTAR_SUTUNU: 'Toplam Alacak (TL)'})
            print(dokum_df.to_string(index=False))
        else:
            print("\nBu temsilci(ler)e ait pozitif bakiye bulunan müşteri yok.")

except Exception as e:
    print("\nBEKLENMEDİK BİR HATA OLUŞTU:")
    print("Hata Mesajı:", e)

input("\nProgram sonlandı. Kapatmak için Enter tuşuna basın...")