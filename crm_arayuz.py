import streamlit as st
import pandas as pd
from streamlit_option_menu import option_menu
from datetime import datetime, timedelta
import io

# --- Sayfa Ayarları ---
st.set_page_config(page_title="Öz lider CRM", page_icon="👑", layout="wide")

# --- Özel CSS Fonksiyonu ---
def local_css(file_name):
    # Artık harici CSS kullanmıyoruz, bu fonksiyon boş kalacak
    pass

# --- İsimleri Normalleştirme Fonksiyonu ---
def normalize_turkish_names(name):
    """
    Türkçe karakterleri ve boşlukları temizleyerek isimleri normalleştirir.
    """
    if pd.isna(name):
        return ""
    name = str(name).strip().lower()
    name = name.replace('i̇', 'i').replace('i', 'i').replace('ş', 's').replace('ç', 'c').replace('ğ', 'g').replace('ö', 'o').replace('ü', 'u').replace('ı', 'i')
    
    # Özel yazım hatası düzeltmesi
    name = name.replace('kalyuncu', 'kalyoncu')
    
    return name

# --- VERİ YÜKLEME FONKSİYONLARI ---
@st.cache_data
def satis_veri_yukle(dosya_yolu):
    try:
        df = pd.read_excel(dosya_yolu)
        df.columns = df.columns.str.strip()
        df['Gün'] = pd.to_numeric(df['Gün'], errors='coerce')
        df['ST'] = df['ST'].astype(str)
        df['Müşteri'] = df['Müşteri'].astype(str)
        
        df = df.dropna(subset=['ST'])
        
        df['ST_normal'] = df['ST'].apply(normalize_turkish_names)
        
        return df
    except Exception as e:
        st.error(f"Satış verisi ('{dosya_yolu}') okunurken bir hata oluştu: {e}")
        return None

@st.cache_data
def stok_veri_yukle(dosya_yolu):
    try:
        df = pd.read_excel(dosya_yolu)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Stok verisi ('{dosya_yolu}') okunurken bir hata oluştu: {e}")
        return None

@st.cache_data
def satis_hedef_veri_yukle(dosya_yolu):
    try:
        df = pd.read_excel(dosya_yolu, header=None)
        return df
    except Exception as e:
        st.error(f"Satış/Hedef verisi ('{dosya_yolu}') okunurken bir hata oluştu: {e}")
        return None

@st.cache_data
def solen_borc_excel_oku(dosya_yolu):
    try:
        df = pd.read_excel(dosya_yolu, header=None)
        deger = df.iloc[:1, :1].values.flatten()[0]
        if isinstance(deger, (int, float)):
            return float(deger)
        else:
            rakam_str = str(deger).strip().replace('.', '').replace(',', '.')
            return float(rakam_str)
    except Exception:
        return 0.0

# --- SATIŞ/HEDEF VERİSİNİ AYRIŞTIRMA FONKSİYONU ---
def parse_satis_hedef_df(df_raw):
    """satis-hedef.xlsx'teki tüm tabloları tek bir DataFrame'de birleştirir."""
    df_raw_copy = df_raw.copy()
    header_indices = df_raw_copy[df_raw_copy.iloc[:, 0].astype(str).str.strip() == 'Satış Temsilcisi'].index.tolist()
    
    cleaned_tables = []
    for i in range(len(header_indices)):
        start_index = header_indices[i]
        end_index = header_indices[i+1] if i + 1 < len(header_indices) else None
        
        table = df_raw_copy.iloc[start_index:end_index].dropna(axis=0, how='all').dropna(axis=1, how='all').reset_index(drop=True)
        if table.empty or len(table) < 2:
            continue
        
        new_header = table.iloc[0]
        table = table[1:].copy()
        table.columns = new_header
        table.columns = table.columns.str.strip()
        
        if 'Satış Temsilcisi' in table.columns and 'SATIŞ' in table.columns:
            table = table[table['Satış Temsilcisi'].str.strip() != 'TOPLAM']
            table['SATIŞ'] = pd.to_numeric(table['SATIŞ'], errors='coerce').fillna(0)
            
            # İsimleri normalleştirme
            table['Satış Temsilcisi_normal'] = table['Satış Temsilcisi'].apply(normalize_turkish_names)
            
            cleaned_tables.append(table[['Satış Temsilcisi_normal', 'SATIŞ']])
    
    if cleaned_tables:
        df = pd.concat(cleaned_tables, ignore_index=True)
        return df.set_index('Satış Temsilcisi_normal')
    return pd.DataFrame(columns=['SATIŞ'])

# --- EXCEL'E DÖNÜŞTÜRME YARDIMCI FONKSİYONU ---
def to_excel(df):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Rapor')
    writer.close()
    processed_data = output.getvalue()
    return processed_data

# --- GİRİŞ EKRANI İÇİN STİLLER ---
st.markdown("""
<style>
    /* Genel Uygulama Stilleri */
    @import url('https://fonts.googleapis.com/css2?family=Exo+2:wght@700&display=swap');
    
    body {
        background-color: #0E1528;
        color: #E6EAF5;
        font-family: 'Exo 2', sans-serif;
    }

    /* Metrik kartlarını buton gibi gösteren stil */
    [data-testid="stMetric"] {
        background-color: #111A33;
        border: 2px solid #3B2F8E;
        border-radius: 8px;
        box-shadow: 6px 6px 12px rgba(0, 0, 0, 0.4), inset -2px -2px 4px rgba(0, 0, 0, 0.2);
        transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
    }

    [data-testid="stMetric"]:hover {
        border-color: #FDB022;
        box-shadow: 8px 8px 16px rgba(0, 0, 0, 0.6), inset -2px -2px 4px rgba(0, 0, 0, 0.2);
        transform: translateY(-2px);
    }

    /* Metrik başlıklarını sarı renkte gösterir */
    [data-testid="stMetricLabel"] {
        color: #FDB022;
        font-weight: 700;
    }

    /* Tüm alt başlık ve açıklama yazılarını renklendirir ve stillerini değiştirir */
    .st-emotion-cache-1216t4c > p {
        color: #A9B4CF;
        font-size: 1rem;
        font-weight: 400;
    }

    /* Selectbox ve input etiketleri */
    [data-testid="stFormLabel"] {
        color: #A9B4CF;
        font-size: 1.1rem;
        font-weight: 600;
    }

    /* Input ve Selectbox'lar için stil */
    [data-testid="stInputContainer"] {
        background-color: #111A33;
        border: 2px solid #3B2F8E;
        border-radius: 8px;
        box-shadow: 6px 6px 12px rgba(0, 0, 0, 0.4), inset -2px -2px 4px rgba(0, 0, 0, 0.2);
        transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out, border-color 0.2s ease-in-out;
    }

    [data-testid="stInputContainer"]:hover {
        border-color: #FDB022;
        box-shadow: 8px 8px 16px rgba(0, 0, 0, 0.6), inset -2px -2px 4px rgba(0, 0, 0, 0.2);
    }
    
    [data-testid="stInputContainer"] div {
        color: #FDB022 !important;
        font-size: 1.1rem;
        font-family: 'Exo 2', sans-serif;
        font-weight: 500;
    }

    /* Giriş sayfası için özel stil */
    .login-body {
        background-image: url("arka_plan.jpg");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
    }
    .stApp.login-bg > header {
        display: none;
    }

    .developer-credit {
        position: fixed;
        bottom: 10px;
        right: 10px;
        color: #FFD700;
        font-size: 14px;
        font-family: 'Exo 2', sans-serif;
        font-weight: 700;
        text-shadow: 1px 1px 2px #000;
    }
</style>
""", unsafe_allow_html=True)

# =======================================================================================
# --- SAYFA FONKSİYONLARI ---
# =======================================================================================
def page_genel_bakis(satis_df, stok_df, satis_hedef_df, solen_borcu_degeri):
    st.title("📈 Genel Bakış")
    st.markdown("İşletmenizin genel durumunu gösteren anahtar performans göstergeleri.")
    if satis_df is not None and stok_df is not None:
        toplam_bakiye = satis_df['Kalan Tutar Total'].sum()
        toplam_stok_degeri = stok_df['Brüt Tutar'].sum()
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Toplam Bakiye (TL)", f"{toplam_bakiye:,.2f}", delta="1.2%")
        with col2: st.metric("Toplam Stok Değeri (Brüt)", f"{toplam_stok_degeri:,.2f} TL")
        with col3: st.metric("Şölen'e Olan Borç", f"{solen_borcu_degeri:,.2f} TL")
        st.markdown("---")
        if satis_hedef_df is not None:
            st.subheader("Genel Satış & Hedef Performansı")
            try:
                toplam_hedef = 0; toplam_satis = 0; toplam_kalan = 0
                temp_df = satis_hedef_df.dropna(how='all').reset_index(drop=True)
                total_rows = temp_df[temp_df.iloc[:, 0].astype(str).str.strip() == 'TOPLAM']
                if not total_rows.empty:
                    toplam_hedef = pd.to_numeric(total_rows.iloc[:, 1], errors='coerce').sum()
                    toplam_satis = pd.to_numeric(total_rows.iloc[:, 2], errors='coerce').sum()
                    toplam_kalan = pd.to_numeric(total_rows.iloc[:, 3], errors='coerce').sum()
                kpi1, kpi2, kpi3 = st.columns(3)
                kpi1.metric("Genel Toplam Hedef", f"{toplam_hedef:,.2f} TL")
                kpi2.metric("Genel Toplam Satış", f"{toplam_satis:,.2f} TL")
                kpi3.metric("Genel Toplam Kalan", f"{toplam_kalan:,.2f} TL")
            except Exception:
                st.warning("Satış/Hedef özeti hesaplanamadı.")
            st.markdown("---")
        st.subheader("Vadesi Geçmiş Alacak Özeti (Tüm Temsilciler)")
        gecikmis_df_genel = satis_df[(satis_df['Gün'] > 0) & (satis_df['Kalan Tutar Total'] > 0)]
        gun_1_35_genel = gecikmis_df_genel[(gecikmis_df_genel['Gün'] > 0) & (gecikmis_df_genel['Gün'] <= 35)]['Kalan Tutar Total'].sum()
        ustu_35_gun_genel = gecikmis_df_genel[gecikmis_df_genel['Gün'] > 35]['Kalan Tutar Total'].sum()
        ustu_45_gun_genel = gecikmis_df_genel[gecikmis_df_genel['Gün'] > 45]['Kalan Tutar Total'].sum()
        ustu_60_gun_genel = gecikmis_df_genel[gecikmis_df_genel['Gün'] > 60]['Kalan Tutar Total'].sum()
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        kpi_col1.metric("1-35 Gün Arası Alacak", f"{gun_1_35_genel:,.2f} TL")
        kpi_col2.metric("35+ Gün Geçikme", f"{ustu_35_gun_genel:,.2f} TL")
        kpi_col3.metric("45+ Gün Geçikme", f"{ustu_45_gun_genel:,.2f} TL")
        kpi_col4.metric("60+ Gün Geçikme (Riskli)", f"{ustu_60_gun_genel:,.2f} TL", delta_color="inverse")
        st.markdown("---")
        st.subheader("Temsilci Bazında Toplam Bakiyeler")
        temsilci_bakiyeleri = satis_df.groupby('ST')['Kalan Tutar Total'].sum().sort_values(ascending=False)
        st.bar_chart(temsilci_bakiyeleri, color="#FDB022")
    else:
        st.warning("Genel Bakış sayfasını görüntülemek için temel veri dosyalarının yüklenmesi gerekmektedir.")
def page_tum_temsilciler(satis_df, temiz_satis_hedef_df):
    st.title("👥 Tüm Temsilciler Detay Raporu")
    if satis_df is not None:
        toplam_musteri = satis_df['Müşteri'].nunique()
        toplam_temsilci = satis_df['ST'].nunique()
        col1, col2 = st.columns(2)
        with col1: st.metric("Toplam Müşteri Sayısı", f"{toplam_musteri}")
        with col2: st.metric("Aktif Temsilci Sayısı", f"{toplam_temsilci}")
        st.markdown("---")
        temsilci_listesi = sorted(satis_df['ST'].unique())
        secilen_temsilci = st.selectbox('İncelemek istediğiniz temsilciyi seçin:', temsilci_listesi)
        if secilen_temsilci:
            st.markdown(f"### {secilen_temsilci} Raporu")
            normalized_name = normalize_turkish_names(secilen_temsilci)
            toplam_satis = temiz_satis_hedef_df.loc[normalized_name]['SATIŞ'] if normalized_name in temiz_satis_hedef_df.index else 0
            temsilci_df = satis_df[satis_df['ST'] == secilen_temsilci]
            toplam_bakiye = temsilci_df['Kalan Tutar Total'].sum()
            musteri_sayisi = temsilci_df['Müşteri'].nunique()
            gecikmis_df_temsilci = temsilci_df[(temsilci_df['Gün'] > 0) & (temsilci_df['Kalan Tutar Total'] > 0)]
            ustu_35_gun_temsilci = gecikmis_df_temsilci[gecikmis_df_temsilci['Gün'] > 35]['Kalan Tutar Total'].sum()
            ustu_60_gun_temsilci = gecikmis_df_temsilci[gecikmis_df_temsilci['Gün'] > 60]['Kalan Tutar Total'].sum()
            kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
            kpi_col1.metric("Toplam Satış Cirosu", f"{toplam_satis:,.2f} TL")
            kpi_col2.metric("Toplam Bakiye", f"{toplam_bakiye:,.2f} TL")
            kpi_col3.metric("35+ Gün Geçikme", f"{ustu_35_gun_temsilci:,.2f} TL")
            kpi_col4.metric("60+ Gün Geçikme", f"{ustu_60_gun_temsilci:,.2f} TL", delta_color="inverse")
            st.markdown("---")
            st.metric("Müşteri Sayısı", f"{musteri_sayisi}")
            st.markdown("---")
            st.subheader("Müşteri Bakiye Dökümü")
            pozitif_bakiye_df = temsilci_df[temsilci_df['Kalan Tutar Total'] > 0]
            gosterilecek_tablo = pozitif_bakiye_df[['Müşteri', 'Kalan Tutar Total']].rename(columns={'Müşteri': 'Müşteri Adı', 'Kalan Tutar Total': 'Bakiye (TL)'}).sort_values(by='Bakiye (TL)', ascending=False)
            st.dataframe(gosterilecek_tablo, use_container_width=True, hide_index=True)
def page_stok(stok_df):
    st.title("📦 Stok Yönetimi ve Envanter Analizi")
    if stok_df is None: return
    brut_tutar_sutunu = 'Brüt Tutar'; miktar_sutunu = 'Miktar'; urun_adi_sutunu = 'Ürün'; urun_kodu_sutunu = 'Ürün Kodu'; depo_adi_sutunu = 'Depo Adı'; fiyat_sutunu = 'Fiyat'
    gerekli_sutunlar = [brut_tutar_sutunu, miktar_sutunu, urun_adi_sutunu]
    for sutun in gerekli_sutunlar:
        if sutun not in stok_df.columns:
            st.error(f"HATA: Stok Excel dosyasında '{sutun}' adında bir sütun bulunamadı!")
            return
    aktif_stok_df = stok_df[stok_df[miktar_sutunu] > 0].copy()
    st.markdown("Depo seçimi yaparak envanteri filtreleyin veya tüm depolardaki ürünleri toplu olarak görün.")
    col1, col2 = st.columns([1, 1])
    with col1:
        depo_listesi = ['Tüm Depolar'] + sorted(aktif_stok_df[depo_adi_sutunu].unique())
        secilen_depo = st.selectbox('Depo Seçin:', depo_listesi)
    with col2:
        sadece_kritikleri_goster = st.toggle('Sadece Kritik Seviyedeki Ürünleri Göster', value=False)
    if secilen_depo == 'Tüm Depolar':
        goruntulenecek_df = aktif_stok_df.groupby([urun_kodu_sutunu, urun_adi_sutunu, fiyat_sutunu]).agg(Miktar=(miktar_sutunu, 'sum'), Brüt_Tutar=(brut_tutar_sutunu, 'sum')).reset_index()
        is_aggregated = True
    else:
        goruntulenecek_df = aktif_stok_df[aktif_stok_df[depo_adi_sutunu] == secilen_depo]
        is_aggregated = False
    st.markdown("---")
    toplam_stok_degeri = goruntulenecek_df['Brüt_Tutar' if is_aggregated else brut_tutar_sutunu].sum()
    kritik_seviye_degeri = 40
    kritik_seviyedeki_urunler_df = goruntulenecek_df[goruntulenecek_df[miktar_sutunu] < kritik_seviye_degeri]
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Toplam Stok Değeri (Brüt)", f"{toplam_stok_degeri:,.2f} TL")
    kpi2.metric("Stoktaki Ürün Çeşidi", f"{goruntulenecek_df[urun_adi_sutunu].nunique()}")
    kpi3.metric(f"KRİTİK SEVİYEDEKİ ÜRÜNLER (<{kritik_seviye_degeri} Koli)", f"{kritik_seviyedeki_urunler_df.shape[0]} Ürün", delta_color="inverse")
    st.markdown("---")
    if sadece_kritikleri_goster:
        gosterilecek_nihai_df = kritik_seviyedeki_urunler_df
        st.warning(f"Aşağıda sadece stok miktarı {kritik_seviye_degeri} kolinin altına düşmüş ürünler listelenmektedir.")
    else:
        gosterilecek_nihai_df = goruntulenecek_df
    st.subheader("Detaylı Stok Listesi")
    def highlight_critical(row):
        if row[miktar_sutunu] < kritik_seviye_degeri: return ['background-color: #5E2A2A'] * len(row)
        return [''] * len(row)
    gosterilecek_nihai_df = gosterilecek_nihai_df.sort_values(by=urun_adi_sutunu, ascending=True)
    if is_aggregated:
        gosterilecek_sutunlar = [urun_kodu_sutunu, urun_adi_sutunu, miktar_sutunu, fiyat_sutunu, 'Brüt_Tutar']
        format_sozlugu = {'Brüt_Tutar': '{:,.2f} TL', fiyat_sutunu: '{:,.2f} TL'}
    else:
        gosterilecek_sutunlar = [depo_adi_sutunu, urun_kodu_sutunu, urun_adi_sutunu, miktar_sutunu, fiyat_sutunu, brut_tutar_sutunu]
        format_sozlugu = {brut_tutar_sutunu: '{:,.2f} TL', fiyat_sutunu: '{:,.2f} TL'}
    st.dataframe(gosterilecek_nihai_df[gosterilecek_sutunlar].style.apply(highlight_critical, axis=1).format(format_sozlugu), use_container_width=True, hide_index=True)
def page_yaslandirma(satis_df):
    st.title("⏳ Borç Yaşlandırma Analizi")
    if satis_df is None: return
    gun_sutunu = 'Gün'
    if gun_sutunu not in satis_df.columns:
        st.error(f"HATA: Satış verilerinde ('rapor.xls') '{gun_sutunu}' adında bir sütun bulunamadı!")
        return
    st.markdown("Satış temsilcisi seçerek vadesi geçmiş alacakların dökümünü ve özetini görüntüleyin.")
    temsilci_listesi = sorted(satis_df['ST'].unique())
    secilen_temsilcisi = st.selectbox('Analiz için bir satış temsilcisi seçin:', temsilci_listesi)
    if secilen_temsilcisi:
        temsilci_df = satis_df[satis_df['ST'] == secilen_temsilcisi].copy()
        gecikmis_df = temsilci_df[(temsilci_df[gun_sutunu] > 0) & (temsilci_df['Kalan Tutar Total'] > 0)]
        st.markdown("---")
        st.subheader(f"{secilen_temsilcisi} - Vadesi Geçmiş Alacak Özeti")
        ustu_35_gun_df = gecikmis_df[gecikmis_df['Gün'] > 35]
        ustu_45_gun_df = gecikmis_df[gecikmis_df['Gün'] > 45]
        ustu_60_gun_df = gecikmis_df[gecikmis_df['Gün'] > 60]
        col1, col2, col3 = st.columns(3)
        col1.metric("35+ Gün Geçikme", f"{ustu_35_gun_df['Kalan Tutar Total'].sum():,.2f} TL")
        col2.metric("45+ Gün Geçikme", f"{ustu_45_gun_df['Kalan Tutar Total'].sum():,.2f} TL")
        col3.metric("60+ Gün Geçikme (Riskli)", f"{ustu_60_gun_df['Kalan Tutar Total'].sum():,.2f} TL")
        st.markdown("---")
        min_gun_sayisi = int(gecikmis_df[gun_sutunu].min()) if not gecikmis_df.empty else 0
        max_gun_sayisi = int(gecikmis_df[gun_sutunu].max()) if not gecikmis_df.empty else 1
        secilen_gun = st.slider('Özel Gecikme Günü Filtresi', min_gun_sayisi, max_gun_sayisi, max_gun_sayisi)
        dinamik_gecikmis_df = gecikmis_df[gecikmis_df['Gün'] >= secilen_gun]
        st.subheader(f"{secilen_gun}+ Gün Gecikmiş Alacakların Detaylı Listesi")
        if dinamik_gecikmis_df.empty:
            st.success(f"{secilen_temsilcisi} adlı temsilcinin {secilen_gun} günden fazla gecikmiş alacağı bulunmamaktadır.")
        else:
            sirali_liste = dinamik_gecikmis_df.sort_values(by=gun_sutunu, ascending=False)
            gosterilecek_sutunlar = ['Müşteri', 'Kalan Tutar Total', gun_sutunu]
            st.dataframe(sirali_liste[gosterilecek_sutunlar], use_container_width=True, hide_index=True, column_config={gun_sutunu: "Gecikme Günü", "Kalan Tutar Total": st.column_config.NumberColumn("Bakiye (TL)", format="%.2f TL")})
        st.markdown("")
        if not dinamik_gecikmis_df.empty:
            st.download_button(label=f"📥 {secilen_gun}+ Gün Raporunu İndir", data=to_excel(dinamik_gecikmis_df), file_name=f"{secilen_temsilcisi}_{secilen_gun}_gun_ustu.xlsx")
def page_satis_hedef(satis_hedef_df):
    st.title("🎯 Satış / Hedef Analizi")
    if satis_hedef_df is None: 
        st.warning("Lütfen `Raporlama` klasörüne `satis-hedef.xlsx` dosyasını ekleyin.")
        return
    st.markdown("Temsilci gruplarına göre satış ve hedef performanslarını görsel olarak analiz edin.")
    try:
        df_raw = satis_hedef_df.copy()
        header_indices = df_raw[df_raw.iloc[:, 0].astype(str).str.strip() == 'Satış Temsilcisi'].index.tolist()
        tables_raw = []
        for i in range(len(header_indices)):
            start_index = header_indices[i]
            end_index = header_indices[i+1] if i + 1 < len(header_indices) else None
            table_title_index = start_index - 1 if start_index > 0 else 0
            tables_raw.append((df_raw.iloc[table_title_index, 0], df_raw.iloc[start_index:end_index]))
        def clean_table(df):
            df = df.dropna(axis=0, how='all').dropna(axis=1, how='all').reset_index(drop=True)
            if df.empty or len(df) < 2: return None
            new_header = df.iloc[0]
            df = df[1:]
            df.columns = new_header
            df.columns = df.columns.str.strip()
            for col in ['HEDEF', 'SATIŞ', '%', 'KALAN']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        cleaned_tables = [(title, clean_table(t)) for title, t in tables_raw]
        cleaned_tables = [item for item in cleaned_tables if item[1] is not None]
        toplam_hedef = 0; toplam_satis = 0; toplam_kalan = 0
        for title, table in cleaned_tables:
            if 'TOPLAM' in table['Satış Temsilcisi'].values:
                total_row = table[table['Satış Temsilcisi'] == 'TOPLAM']
                toplam_hedef += total_row['HEDEF'].sum()
                toplam_satis += total_row['SATIŞ'].sum()
                toplam_kalan += total_row['KALAN'].sum()
        st.markdown("---")
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Genel Toplam Hedef", f"{toplam_hedef:,.2f} TL")
        kpi2.metric("Genel Toplam Satış", f"{toplam_satis:,.2f} TL")
        kpi3.metric("Genel Toplam Kalan", f"{toplam_kalan:,.2f} TL")
        st.markdown("---")
        def style_dataframe(df):
            df_display = df[df['Satış Temsilcisi'] != 'TOPLAM']
            return df_display.style.format({'HEDEF': '{:,.2f} TL', 'SATIŞ': '{:,.2f} TL', 'KALAN': '{:,.2f} TL', '%': '{:,.2f}%'}).background_gradient(cmap='RdYlGn', subset=['%'], vmin=0, vmax=120)
        for title, table in cleaned_tables:
            st.subheader(title)
            st.dataframe(style_dataframe(table), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Excel dosyası ayrıştırılırken bir hata oluştu. Lütfen dosya formatını kontrol edin. Hata: {e}")
def page_solen(solen_borcu_degeri):
    st.title("🎉 Şölen Cari Hesap Özeti")
    st.markdown("Şölen'e olan güncel borç bakiyesi.")
    st.markdown("---")
    st.metric("Güncel Borç Bakiyesi", f"{solen_borcu_degeri:,.2f} TL")
    st.info("Bu veri `solen_borc.xlsx` dosyasından okunmaktadır.")
def page_hizmet_faturalari():
    st.title("🧾 Hizmet Faturaları")
    st.warning("Bu sayfa şu anda yapım aşamasındadır.")
def page_musteri_analizi(satis_df):
    st.title("👥 Müşteri Analizi")
    if satis_df is None:
        st.warning("Müşteri analizi için satış verileri (rapor.xls) yüklenemedi.")
        return
    st.markdown("Değerli, sadık veya hareketsiz müşterilerinizi keşfedin.")
    st.markdown("---")
    st.subheader("🥇 En Değerli Müşteriler (Ciro)")
    top_n = st.slider("Listelenecek müşteri sayısı:", 5, 50, 10, step=5)
    en_degerli_musteriler = satis_df.groupby('Müşteri')['Kalan Tutar Total'].sum().sort_values(ascending=False).head(top_n).reset_index()
    en_degerli_musteriler.rename(columns={'Müşteri': 'Müşteri Adı', 'Kalan Tutar Total': 'Toplam Bakiye (TL)'}, inplace=True)
    st.dataframe(en_degerli_musteriler, use_container_width=True, hide_index=True, column_config={
        "Toplam Bakiye (TL)": st.column_config.NumberColumn(format="%.2f TL")
    })
    st.markdown("---")
    st.subheader("❤️ Sadık Müşteriler (İşlem Sayısı)")
    top_n_sadik = st.slider("Listelenecek sadık müşteri sayısı:", 5, 50, 10, step=5, key='sadik_slider')
    sadik_musteriler = satis_df['Müşteri'].value_counts().head(top_n_sadik).reset_index()
    sadik_musteriler.columns = ['Müşteri Adı', 'Toplam İşlem Sayısı']
    st.dataframe(sadik_musteriler, use_container_width=True, hide_index=True)
    st.markdown("---")
    st.subheader("😴 'Uyuyan' Müşteriler")
    son_islem_gunleri = satis_df.groupby('Müşteri')['Gün'].max().reset_index()
    son_islem_gunleri.columns = ['Müşteri', 'Gecikme Günü']
    bugunun_tarihi = datetime.today().date()
    son_islem_gunleri['Son İşlem Tarihi'] = son_islem_gunleri['Gecikme Günü'].apply(lambda x: bugunun_tarihi - pd.Timedelta(days=x) if pd.notna(x) else None)
    gecikme_gunu = st.slider("İşlem görmeyen minimum gün sayısı:", 30, 180, 60)
    uyuyan_musteriler = son_islem_gunleri[son_islem_gunleri['Gecikme Günü'] >= gecikme_gunu].sort_values(by='Gecikme Günü', ascending=False)
    if not uyuyan_musteriler.empty:
        st.info(f"Son işlemi **{gecikme_gunu} günden** eski olan müşteriler listeleniyor.")
        st.dataframe(uyuyan_musteriler[['Müşteri', 'Gecikme Günü', 'Son İşlem Tarihi']], use_container_width=True, hide_index=True, column_config={
            "Gecikme Günü": "Gecikme Günü",
            "Son İşlem Tarihi": st.column_config.DateColumn(format="YYYY-MM-DD")
        })
    else:
        st.success("Belirlenen kriterde uyuyan müşteri bulunamadı.")
def add_developer_credit():
    st.markdown("""
    <style>
    .developer-credit {
        position: fixed;
        bottom: 10px;
        right: 10px;
        color: #FFD700;
        font-size: 14px;
        font-family: 'Exo 2', sans-serif;
        font-weight: 700;
        text-shadow: 1px 1px 2px #000;
    }
    </style>
    <div class='developer-credit'>DEVELOPED BY FATİH BAKICI</div>
    """, unsafe_allow_html=True)
def main_app(satis_df, stok_df, satis_hedef_df, solen_borcu_degeri, temiz_satis_hedef_df):
    with st.sidebar:
        st.markdown("""<style>@import url('https://fonts.googleapis.com/css2?family=Exo+2:wght@700&display=swap');</style><div style="font-family: 'Exo 2', sans-serif; font-size: 28px; text-align: center; margin-bottom: 20px;"><span style="color: #FDB022;">ÖZLİDER TÜKETİM</span><span style="color: #E6EAF5;">- ŞÖLEN CRM</span></div>""", unsafe_allow_html=True)
        secim = option_menu(menu_title=None, 
                            options=["Genel Bakış", "Tüm Temsilciler", "Şölen", "Hizmet Faturaları", "Yaşlandırma", "Stok", "Satış/Hedef", "Müşteri Analizi"], 
                            icons=['graph-up', 'people-fill', 'gift-fill', 'receipt-cutoff', 'clock-history', 'box-seam', 'bullseye', 'person-lines-fill'], 
                            menu_icon="cast", 
                            default_index=0, 
                            orientation="vertical", 
                            styles={"container": {"padding": "0!important", "background-color": "transparent"}, 
                                    "icon": {"color": "#FDB022", "font-size": "20px"}, 
                                    "nav-link": {"font-size": "16px", "text-align": "left", "margin":"5px", "--hover-color": "#111A33"}, 
                                    "nav-link-selected": {"background-color": "#3B2F8E"},})
    if secim == "Genel Bakış":
        page_genel_bakis(satis_df, stok_df, satis_hedef_df, solen_borcu_degeri)
    elif secim == "Tüm Temsilciler":
        page_tum_temsilciler(satis_df, temiz_satis_hedef_df)
    elif secim == "Şölen":
        page_solen(solen_borcu_degeri)
    elif secim == "Hizmet Faturaları":
        page_hizmet_faturalari()
    elif secim == "Yaşlandırma":
        page_yaslandirma(satis_df)
    elif secim == "Stok":
        page_stok(stok_df)
    elif secim == "Satış/Hedef":
        page_satis_hedef(satis_hedef_df)
    elif secim == "Müşteri Analizi":
        page_musteri_analizi(satis_df)
    add_developer_credit()
def login_page():
    # Bu fonksiyon, harici CSS dosyasından stilleri çeker
    st.markdown("""
        <style>
            .stApp {
                background-image: url("arka_plan.jpg");
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
            }
            .main {
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
            }
            .login-container {
                padding: 40px;
                border-radius: 10px;
                background-color: rgba(17, 26, 51, 0.85); /* Hafif saydam bir kutu */
                text-align: center;
                box-shadow: 0 4px 20px rgba(0,0,0,0.5);
                width: 400px;
            }
            .stTextInput>div>div>input {
                color: #FDB022;
                background-color: #0E1528;
                border: 2px solid #3B2F8E;
                border-radius: 5px;
                box-shadow: inset 2px 2px 5px rgba(0,0,0,0.5), inset -2px -2px 5px rgba(255,255,255,0.1);
            }
            .stButton>button {
                color: #111A33;
                background-color: #FDB022;
                border-radius: 5px;
                font-weight: bold;
                box-shadow: 2px 2px 5px rgba(0,0,0,0.5);
            }
            .developer-credit {
                position: fixed;
                bottom: 10px;
                right: 10px;
                color: #FFD700;
                font-size: 14px;
                font-family: 'Exo 2', sans-serif;
                font-weight: 700;
                text-shadow: 1px 1px 2px #000;
            }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container():
            st.markdown("<div class='login-container'>", unsafe_allow_html=True)
            st.title("🔐 Giriş Ekranı")
            st.markdown("Lütfen devam etmek için kullanıcı adı ve şifrenizi girin.")
            st.session_state['username'] = st.text_input("Kullanıcı Adı")
            st.session_state['password'] = st.text_input("Şifre", type="password")
            if st.button("Giriş Yap"):
                if st.session_state['username'] == "admin" and st.session_state['password'] == "12345":
                    st.session_state['logged_in'] = True
                    st.success("Giriş başarılı!")
                    st.rerun()
                else:
                    st.error("Hatalı kullanıcı adı veya şifre.")
            st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='developer-credit'>DEVELOPED BY FATİH BAKICI</div>", unsafe_allow_html=True)

satis_df_cache = satis_veri_yukle('rapor.xls')
stok_df_cache = stok_veri_yukle('stok.xls')
satis_hedef_df_cache = satis_hedef_veri_yukle('satis-hedef.xlsx')
solen_borcu_degeri_cache = solen_borc_excel_oku('solen_borc.xlsx')
temiz_satis_hedef_df_cache = parse_satis_hedef_df(satis_hedef_df_cache)

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if st.session_state['logged_in']:
    main_app(satis_df_cache, stok_df_cache, satis_hedef_df_cache, solen_borcu_degeri_cache, temiz_satis_hedef_df_cache)
else:
    login_page()