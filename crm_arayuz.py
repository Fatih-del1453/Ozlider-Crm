import streamlit as st
import pandas as pd
from streamlit_option_menu import option_menu
from datetime import datetime, timedelta
import io
import csv
import plotly.graph_objects as go
import plotly.express as px
import requests # Harita için eklendi
import json     # Harita için eklendi

# --- Sayfa Ayarları ---
st.set_page_config(page_title="Öz lider CRM", page_icon="👑", layout="wide")

# --- Özel CSS Fonksiyonu ---
def local_css(file_name):
    try:
        with open(file_name, encoding='utf-8') as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"'{file_name}' adında bir stil dosyası bulunamadı.")
local_css("style.css")

# --- Kullanıcı Bilgileri ---
USER_CREDENTIALS = {
    "Mustafa Karcı": "0144",
    "M. Ali Çakılca": "0151",
    "Gökhan Gülmez": "0101",
    "Fatih Bakıcı": "0134"
}

# --- İsimleri Normalleştirme Fonksiyonu ---
def normalize_turkish_names(name):
    """
    Türkçe karakterleri ve boşlukları temizleyerek isimleri normalleştirir.
    """
    if pd.isna(name):
        return ""
    name = str(name).strip().lower()
    name = name.replace('i̇', 'i').replace('i', 'i').replace('ş', 's').replace('ç', 'c').replace('ğ', 'g').replace('ö', 'o').replace('ü', 'u').replace('ı', 'i')
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
        
# YENİ EKLENDİ - Harita için ilçe verisini yükleme fonksiyonu
@st.cache_data
def adana_ilce_veri_yukle(dosya_yolu):
    try:
        df = pd.read_excel(dosya_yolu)
        df.columns = df.columns.str.strip()
        # Türkçe karakter sorunlarını önlemek için ilçe isimlerini büyük harfe çevirelim
        if 'İlçe' in df.columns:
            # DÜZELTME: .upper() fonksiyonundan 'tr' parametresi kaldırıldı.
            df['İlçe'] = df['İlçe'].str.upper()
        return df
    except FileNotFoundError:
        return None
    except Exception as e:
        st.error(f"Adana ilçe verisi ('{dosya_yolu}') okunurken bir hata oluştu: {e}")
        return pd.DataFrame()

@st.cache_data
def parse_satis_hedef_excel_robust(df_raw):
    """satis-hedef.xlsx'teki tüm tabloları ve grupları okuyup tek bir DataFrame'e çevirir."""
    if df_raw is None:
        return pd.DataFrame()
    try:
        df_raw_copy = df_raw.copy()
        header_indices = df_raw_copy[df_raw_copy.iloc[:, 0].astype(str).str.strip() == 'Satış Temsilcisi'].index.tolist()
        all_tables = []
        for i in range(len(header_indices)):
            start_index = header_indices[i]
            end_index = header_indices[i+1] if i + 1 < len(header_indices) else None
            table = df_raw_copy.iloc[start_index:end_index].dropna(axis=0, how='all').dropna(axis=1, how='all').reset_index(drop=True)
            if table.empty or len(table) < 2: continue
            new_header = table.iloc[0]
            table = table[1:].copy()
            table.columns = new_header
            table.columns = table.columns.str.strip()
            for col in ['HEDEF', 'SATIŞ', '%', 'KALAN']:
                if col in table.columns:
                    table[col] = pd.to_numeric(table[col], errors='coerce').fillna(0)
            table_title = df_raw_copy.iloc[start_index - 1, 0] if start_index > 0 else f"Grup {i+1}"
            table['Grup'] = table_title
            table['ST_normal'] = table['Satış Temsilcisi'].apply(normalize_turkish_names)
            all_tables.append(table)
        if not all_tables:
            return pd.DataFrame()
        final_df = pd.concat(all_tables, ignore_index=True)
        return final_df
    except Exception:
        return pd.DataFrame()

def to_excel(df):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Rapor')
    writer.close()
    processed_data = output.getvalue()
    return processed_data

def log_user_activity(user, activity, page_name="N/A"):
    log_file = 'loglar.csv'
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ip_address = "N/A"
    with open(log_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if f.tell() == 0:
            writer.writerow(['Zaman Damgası', 'Kullanıcı Adı', 'IP Adresi', 'Sayfa Adı', 'Aktivite'])
        writer.writerow([timestamp, user, ip_address, page_name, activity])

# =======================================================================================
# --- SAYFA FONKSİYONLARI ---
# =======================================================================================

def page_genel_bakis(satis_df, stok_df, solen_borcu_degeri):
    st.title("📈 Genel Bakış")
    if satis_df is not None and stok_df is not None:
        toplam_bakiye = satis_df['Kalan Tutar Total'].sum()
        toplam_stok_degeri = stok_df['Brüt Tutar'].sum()
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Toplam Bakiye (TL)", f"{toplam_bakiye:,.2f}")
        with col2: st.metric("Toplam Stok Değeri (Brüt)", f"{toplam_stok_degeri:,.2f} TL")
        with col3: st.metric("Şölen'e Olan Borç", f"{solen_borcu_degeri:,.2f} TL")
        st.markdown("---")

        st.subheader("Vadesi Geçmiş Alacak Özeti (Tüm Temsilciler)")
        gecikmis_df_genel = satis_df[(satis_df['Gün'] > 0) & (satis_df['Kalan Tutar Total'] > 0)]
        gun_1_35_genel = gecikmis_df_genel[(gecikmis_df_genel['Gün'] > 0) & (gecikmis_df_genel['Gün'] <= 35)]['Kalan Tutar Total'].sum()
        ustu_35_gun_genel = gecikmis_df_genel[gecikmis_df_genel['Gün'] > 35]['Kalan Tutar Total'].sum()
        ustu_45_gun_genel = gecikmis_df_genel[gecikmis_df_genel['Gün'] > 45]['Kalan Tutar Total'].sum()
        ustu_60_gun_genel = gecikmis_df_genel[gecikmis_df_genel['Gün'] > 60]['Kalan Tutar Total'].sum()
        gun_1_35_str = f"{gun_1_35_genel:,.2f} TL"
        ustu_35_gun_str = f"{ustu_35_gun_genel:,.2f} TL"
        ustu_45_gun_str = f"{ustu_45_gun_genel:,.2f} TL"
        ustu_60_gun_str = f"{ustu_60_gun_genel:,.2f} TL"

        st.markdown(f"""
        <style>
            .kpi-container {{ display: flex; gap: 15px; align-items: stretch; }}
            .main-kpi-box {{ flex: 2; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 15px; display: flex; align-items: center; justify-content: space-around; box-shadow: 0 4px 8px rgba(0,0,0,0.05); }}
            .kpi-card {{ flex: 1; color: white; border-radius: 10px; padding: 20px; display: flex; flex-direction: column; justify-content: center; text-align: center; min-height: 140px; }}
            .kpi-card.green {{ background-color: #28a745; }}
            .kpi-card.yellow {{ background-color: #ffc107; color: #333; }}
            .kpi-card.orange {{ background-color: #fd7e14; }}
            .kpi-card.red {{ background-color: #dc3545; }}
            .kpi-title {{ font-size: 16px; font-weight: 600; margin-bottom: 10px; }}
            .kpi-value {{ font-size: 26px; font-weight: bold; }}
            .chain-icon {{ font-size: 32px; color: #4a4a4a; padding: 0 10px; align-self: center; }}
        </style>
        <div class="kpi-container">
            <div class="main-kpi-box">
                <div class="kpi-card green"><div class="kpi-title">1-35 Gün Arası Alacak</div><div class="kpi-value">{gun_1_35_str}</div></div>
                <div class="chain-icon">🔗</div>
                <div class="kpi-card yellow"><div class="kpi-title">35+ Gün Gecikme</div><div class="kpi-value">{ustu_35_gun_str}</div></div>
            </div>
            <div class="kpi-card orange"><div class="kpi-title">45+ Gün Gecikme</div><div class="kpi-value">{ustu_45_gun_str}</div></div>
            <div class="kpi-card red"><div class="kpi-title">60+ Gün Gecikme (Riskli)</div><div class="kpi-value">{ustu_60_gun_str}</div></div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("---")
        st.subheader("Temsilci Bazında Müşteri Bakiyelerinin Dağılımı")
        col1_chart, col2_table = st.columns([2, 1])
        with col1_chart:
            temsilci_bakiyeleri = satis_df[satis_df['Kalan Tutar Total'] > 0].groupby('ST')['Kalan Tutar Total'].sum().reset_index()
            temsilci_bakiyeleri.columns = ['Satış Temsilcisi', 'Toplam Bakiye']
            temsilci_bakiyeleri['parent'] = "Toplam Bakiye"
            fig = px.sunburst(temsilci_bakiyeleri, path=['parent', 'Satış Temsilcisi'], values='Toplam Bakiye', color='Toplam Bakiye', color_continuous_scale='YlOrRd', title="Temsilcilerin Toplam Bakiyedeki Payları")
            fig.update_traces(textinfo='label+percent parent', hovertemplate='<b>%{{label}}</b><br>Bakiye: ₺%{{value:,.2f}}<extra></extra>')
            fig.update_layout(margin=dict(t=50, l=25, r=25, b=25), height=500)
            st.plotly_chart(fig, use_container_width=True)
        with col2_table:
            st.write("#### En Yüksek Bakiyeli Temsilciler")
            top_temsilciler_df = temsilci_bakiyeleri[['Satış Temsilcisi', 'Toplam Bakiye']].sort_values(by='Toplam Bakiye', ascending=False).reset_index(drop=True)
            display_df = top_temsilciler_df.copy()
            display_df['Bakiye (TL)'] = display_df['Toplam Bakiye'].apply(lambda x: f"₺{x:,.2f}")
            st.dataframe(display_df[['Satış Temsilcisi', 'Bakiye (TL)']], use_container_width=True, hide_index=True)
    else:
        st.warning("Genel Bakış sayfasını görüntülemek için temel veri dosyalarının yüklenmesi gerekmektedir.")

def page_tum_temsilciler(satis_df, satis_hedef_df):
    st.title("👥 Tüm Temsilciler Detay Raporu")
    if satis_df is None or satis_hedef_df is None or satis_hedef_df.empty:
        st.warning("Bu sayfayı görüntülemek için `rapor.xls` ve `satis-hedef.xlsx` dosyalarının yüklenmesi gerekmektedir.")
        return
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
        personel_hedef_df = satis_hedef_df[satis_hedef_df['ST_normal'] == normalized_name]
        toplam_satis = personel_hedef_df['SATIŞ'].sum()
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
        gosterilecek_tablo['Bakiye (TL)'] = gosterilecek_tablo['Bakiye (TL)'].apply(lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.dataframe(gosterilecek_tablo, use_container_width=True, hide_index=True)

def page_stok(stok_df):
    st.title("📦 Stok Yönetimi ve Envanter Analizi")
    if stok_df is None:
        st.warning("Stok verileri yüklenemedi.")
        return
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
        format_sozlugu = {'Brüt_Tutar': '{{:,.2f}} TL', fiyat_sutunu: '{{:,.2f}} TL'}
    else:
        gosterilecek_sutunlar = [depo_adi_sutunu, urun_kodu_sutunu, urun_adi_sutunu, miktar_sutunu, fiyat_sutunu, brut_tutar_sutunu]
        format_sozlugu = {{brut_tutar_sutunu: '{{:,.2f}} TL', fiyat_sutunu: '{{:,.2f}} TL'}}
    st.dataframe(gosterilecek_nihai_df[gosterilecek_sutunlar].style.apply(highlight_critical, axis=1).format(format_sozlugu), use_container_width=True, hide_index=True)
def page_yaslandirma(satis_df):
    st.title("⏳ Borç Yaşlandırma Analizi")
    if satis_df is None:
        st.warning("Satış verileri yüklenemedi.")
        return
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

def page_satis_hedef(final_df):
    st.title("🎯 Satış / Hedef Analizi")
    if final_df is None or final_df.empty:
        st.warning("Lütfen `satis-hedef.xlsx` dosyasını yükleyin ve formatını kontrol edin.")
        return
    try:
        total_row = final_df[final_df['Satış Temsilcisi'].str.strip() == 'TOPLAM']
        toplam_hedef = total_row['HEDEF'].sum()
        toplam_satis = total_row['SATIŞ'].sum()
        st.subheader("Genel Performans Durumu")
        gauge_fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta", value = toplam_satis,
            number = {'prefix': "₺", 'valueformat': ',.0f'}, domain = {'x': [0, 1], 'y': [0.1, 1]},
            title = {'text': f"<b>Aylık Toplam Satış</b><br><span style='font-size:1.0em;color:#FDB022;'><b>Hedef: ₺{toplam_hedef:,.0f}</b></span>", 'font': {"size": 24}},
            delta = {'reference': toplam_hedef, 'relative': False, 'valueformat': ',.0f', 'increasing': {'color': "#2ECC71"}, 'decreasing': {'color': "#E74C3C"}},
            gauge = {'axis': {'range': [None, toplam_hedef * 1.2], 'tickwidth': 1, 'tickcolor': "darkblue"},
                     'bar': {'color': "#FDB022"}, 'bgcolor': "white", 'borderwidth': 2, 'bordercolor': "gray",
                     'steps': [{'range': [0, toplam_hedef * 0.5], 'color': '#FADBD8'}, {'range': [toplam_hedef * 0.5, toplam_hedef * 0.8], 'color': '#FDEBD0'}],
                     'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': toplam_hedef}}))
        
        tamamlanma_yuzdesi = (toplam_satis / toplam_hedef * 100) if toplam_hedef > 0 else 0
        gauge_fig.add_annotation(x=0.5, y=0.08, text=f"<b>%{tamamlanma_yuzdesi:.1f} Tamamlandı</b>", font=dict(size=22, color="#FDB022"), showarrow=False)
        gauge_fig.update_layout(height=450)
        st.plotly_chart(gauge_fig, use_container_width=True)

        st.markdown("---")
        st.subheader("Temsilci ve Grup Bazında Performans")
        
        personel_df = final_df[final_df['Satış Temsilcisi'].str.strip() != 'TOPLAM'].copy()
        personel_df = personel_df[personel_df['HEDEF'] > 0]
        personel_df['Performans'] = (personel_df['SATIŞ'] / personel_df['HEDEF'] * 100).fillna(0)
        personel_df['Y_Axis_Label'] = personel_df.apply(lambda row: f"{row['Satış Temsilcisi']} (%{row['Performans']:.0f})", axis=1)
        personel_df = personel_df.sort_values(by='Performans', ascending=True)

        bar_fig = go.Figure()
        bar_fig.add_trace(go.Bar(y=personel_df['Y_Axis_Label'], x=personel_df['HEDEF'], name='Hedef', orientation='h', text=personel_df['HEDEF'], marker=dict(color='rgba(58, 71, 80, 0.6)', line=dict(color='rgba(58, 71, 80, 1.0)', width=1))))
        bar_fig.add_trace(go.Bar(y=personel_df['Y_Axis_Label'], x=personel_df['SATIŞ'], name='Satış', orientation='h', text=personel_df['SATIŞ'], marker=dict(color='#FDB022', line=dict(color='#D35400', width=1))))
        bar_fig.update_traces(texttemplate='₺%{x:,.0f}', textposition='outside', textfont_size=12)
        bar_fig.update_layout(title_text='Satış Temsilcisi Hedef & Satış Karşılaştırması', barmode='group', yaxis_title=None, xaxis_title="Tutar (TL)", legend_title="Gösterge", height=600, margin=dict(l=50, r=50, t=70, b=70), yaxis=dict(categoryorder='total ascending', tickfont=dict(family="Arial Black, sans-serif", size=15, color="#FDB022")), bargap=0.30, bargroupgap=0.1)
        st.plotly_chart(bar_fig, use_container_width=True)
        
        with st.expander("Detaylı Veri Tablolarını Görüntüle"):
            for title, table in final_df.groupby('Grup'):
                st.subheader(title)
                df_display = table[table['Satış Temsilcisi'] != 'TOPLAM']
                st.dataframe(df_display.style.format({'HEDEF': '{:,.2f} TL', 'SATIŞ': '{:,.2f} TL', 'KALAN': '{:,.2f} TL', '%': '{:,.2f}%'}).background_gradient(cmap='RdYlGn', subset=['%'], vmin=0, vmax=120), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Grafikler oluşturulurken veya Excel dosyası ayrıştırılırken bir hata oluştu. Lütfen dosya formatını kontrol edin. Hata: {e}")

def page_solen(solen_borcu_degeri):
    st.title("🎉 Şölen Cari Hesap Özeti")
    st.metric("Güncel Borç Bakiyesi", f"{solen_borcu_degeri:,.2f} TL")
    st.info("Bu veri `solen_borc.xlsx` dosyasından okunmaktadır.")

def page_hizmet_faturalari():
    st.title("🧾 Hizmet Faturaları")
    st.warning("Bu sayfa şu anda yapım aşamasındadır.")

# ==========================================================================================
# MÜŞTERİ ANALİZİ SAYFASI - NİHAİ GÜNCELLEME: EKSİK İLÇELER, HARİTA STİLİ VE İLÇE SEÇİM KUTUSU
# ==========================================================================================
def page_musteri_analizi(satis_df, ilce_df):
    st.title("👥 Müşteri Analizi")
    st.markdown("Değerli, sadık veya hareketsiz müşterilerinizi keşfedin ve bölgesel performansı analiz edin.")
    st.markdown("---")

    # --- BÖLGESEL YOĞUNLUK HARİTASI ---
    st.subheader("🗺️ Adana İlçe Bazında Performans Haritası")
    if ilce_df is None:
        st.warning("Haritayı görüntülemek için lütfen `adana_ilce_ciro.xlsx` dosyasını ana klasöre ekleyin.")
    elif ilce_df.empty or 'İlçe' not in ilce_df.columns:
        st.error("`adana_ilce_ciro.xlsx` dosyasında 'İlçe' sütunu bulunamadı veya dosya formatı hatalı.")
    else:
        col1, col2 = st.columns([3, 1])
        with col2:
            st.write("#### Harita Görünümü")
            secim = st.selectbox(
                "Görüntülenecek Veri:",
                ["Toplam Ciro", "Müşteri Sayısı"],
                key="harita_veri_secim" # Key güncellendi
            )
            
            if secim == "Toplam Ciro":
                gosterilecek_veri = ilce_df.groupby("İlçe")["Brüt Fiyat"].sum().reset_index()
                renk_skalasi = "Greens"
                hover_adi = "Toplam Ciro"
            elif secim == "Müşteri Sayısı":
                gosterilecek_veri = ilce_df.groupby("İlçe")["Müşteri Ünvanı"].nunique().reset_index()
                gosterilecek_veri.rename(columns={"Müşteri Ünvanı": "Müşteri Sayısı"}, inplace=True)
                renk_skalasi = "Blues"
                hover_adi = "Müşteri Sayısı"

            if not gosterilecek_veri.empty:
                gosterilecek_veri = gosterilecek_veri.sort_values(by=gosterilecek_veri.columns[1], ascending=False)
                en_iyi_ilce = gosterilecek_veri.iloc[0]
                st.metric(
                    label=f"En Yüksek {hover_adi} Olan İlçe",
                    value=en_iyi_ilce['İlçe'],
                    help=f"Değer: {en_iyi_ilce[gosterilecek_veri.columns[1]]:,.0f}"
                )
            
            st.markdown("---")
            st.write("#### Detaylı İlçe Analizi")
            
            # --- YENİ EKLENEN İLÇE SEÇİM KUTUSU ---
            tum_ilceler = ['Tüm Adana'] + sorted(ilce_df['İlçe'].unique().tolist())
            secilen_ilce_detay = st.selectbox(
                "Detaylarını görmek istediğiniz ilçeyi seçin:",
                tum_ilceler,
                key="ilce_detay_secim"
            )

            if secilen_ilce_detay and secilen_ilce_detay != 'Tüm Adana':
                filtreli_ilce_df = ilce_df[ilce_df['İlçe'] == secilen_ilce_detay]
                toplam_ciro_ilce = filtreli_ilce_df['Brüt Fiyat'].sum()
                musteri_sayisi_ilce = filtreli_ilce_df['Müşteri Ünvanı'].nunique()

                st.markdown(f"**{secilen_ilce_detay} İçin Detaylar:**")
                st.metric("Toplam Ciro", f"₺{toplam_ciro_ilce:,.2f}")
                st.metric("Müşteri Sayısı", f"{musteri_sayisi_ilce:,.0f}")
            elif secilen_ilce_detay == 'Tüm Adana':
                 st.info("Yukarıdaki harita ve genel metrikler 'Tüm Adana' için geçerlidir.")


        with col1:
            try:
                # GeoJSON verisi güncellendi ve tüm Adana ilçelerini içeriyor
                adana_geojson = {
                  "type": "FeatureCollection",
                  "features": [
                    {"type": "Feature", "properties": { "name": "ALADAĞ" }, "geometry": { "type": "Polygon", "coordinates": [ [ [35.5036, 37.5241], [35.4190, 37.4771], [35.3338, 37.5451], [35.3719, 37.6430], [35.3352, 37.7033], [35.4050, 37.7502], [35.4800, 37.7011], [35.5269, 37.6066], [35.5036, 37.5241] ] ] } },
                    {"type": "Feature", "properties": { "name": "CEYHAN" }, "geometry": { "type": "Polygon", "coordinates": [ [ [35.9188, 36.8488], [35.8080, 36.8794], [35.7725, 36.9838], [35.8458, 37.0505], [35.9680, 37.0422], [36.0391, 37.1008], [36.0880, 37.0116], [36.1666, 36.9388], [35.9980, 36.8850], [35.9188, 36.8488] ] ] } },
                    {"type": "Feature", "properties": { "name": "ÇUKUROVA" }, "geometry": { "type": "Polygon", "coordinates": [ [ [35.3236, 37.0041], [35.2119, 37.0308], [35.2513, 37.0902], [35.3619, 37.0705], [35.3236, 37.0041] ] ] } },
                    {"type": "Feature", "properties": { "name": "FEKE" }, "geometry": { "type": "Polygon", "coordinates": [ [ [35.9402, 37.7205], [35.8211, 37.7788], [35.8580, 37.9011], [35.9991, 37.8894], [36.0494, 37.8105], [35.9402, 37.7205] ] ] } },
                    {"type": "Feature", "properties": { "name": "İMAMOĞLU" }, "geometry": { "type": "Polygon", "coordinates": [ [ [35.7316, 37.1994], [35.6133, 37.2400], [35.5891, 37.3111], [35.7002, 37.3402], [35.7891, 37.2794], [35.7316, 37.1994] ] ] } },
                    {"type": "Feature", "properties": { "name": "KARAİSALI" }, "geometry": { "type": "Polygon", "coordinates": [ [ [35.1583, 37.1683], [35.0480, 37.2211], [35.0880, 37.3308], [35.2013, 37.3011], [35.2413, 37.2280], [35.1583, 37.1683] ] ] } },
                    {"type": "Feature", "properties": { "name": "KARATAŞ" }, "geometry": { "type": "Polygon", "coordinates": [ [ [35.5394, 36.5611], [35.3719, 36.5511], [35.2816, 36.6897], [35.4091, 36.7816], [35.5813, 36.7113], [35.5394, 36.5611] ] ] } },
                    {"type": "Feature", "properties": { "name": "KOZAN" }, "geometry": { "type": "Polygon", "coordinates": [ [ [35.9288, 37.3811], [35.7725, 37.4000], [35.6983, 37.5211], [35.8016, 37.6011], [35.9180, 37.5400], [35.9288, 37.3811] ] ] } },
                    {"type": "Feature", "properties": { "name": "POZANTI" }, "geometry": { "type": "Polygon", "coordinates": [ [ [34.9016, 37.2905], [34.8211, 37.4788], [34.9980, 37.5794], [35.0811, 37.4300], [34.9016, 37.2905] ] ] } },
                    {"type": "Feature", "properties": { "name": "SAİMBEYLİ" }, "geometry": { "type": "Polygon", "coordinates": [ [ [36.1511, 37.8813], [35.9991, 37.9483], [35.9400, 38.0805], [36.0880, 38.1000], [36.2280, 37.9894], [36.1511, 37.8813] ] ] } },
                    {"type": "Feature", "properties": { "name": "SARIÇAM" }, "geometry": { "type": "Polygon", "coordinates": [ [ [35.5816, 37.0183], [35.4419, 37.0500], [35.4880, 37.1813], [35.6319, 37.1500], [35.5816, 37.0183] ] ] } },
                    {"type": "Feature", "properties": { "name": "SEYHAN" }, "geometry": { "type": "Polygon", "coordinates": [ [ [35.3236, 37.0041], [35.3619, 37.0705], [35.2513, 37.0902], [35.1583, 36.9511], [35.3236, 37.0041] ] ] } },
                    {"type": "Feature", "properties": { "name": "TUFANBEYLİ" }, "geometry": { "type": "Polygon", "coordinates": [ [ [36.3111, 38.1811], [36.1411, 38.2513], [36.2080, 38.3811], [36.3811, 38.3308], [36.3111, 38.1811] ] ] } },
                    {"type": "Feature", "properties": { "name": "YUMURTALIK" }, "geometry": { "type": "Polygon", "coordinates": [ [ [35.8402, 36.6500], [35.7080, 36.6811], [35.6980, 36.8300], [35.8913, 36.8000], [35.8402, 36.6500] ] ] } },
                    {"type": "Feature", "properties": { "name": "YÜREĞİR" }, "geometry": { "type": "Polygon", "coordinates": [ [ [35.4419, 37.0500], [35.5816, 37.0183], [35.5394, 36.8194], [35.3719, 36.8794], [35.4419, 37.0500] ] ] } }
                  ]
                }
                
                # GeoJSON'daki ilçe isimlerini büyük harfe çevir
                for feature in adana_geojson["features"]:
                    feature["properties"]["name"] = feature["properties"]["name"].upper()

                fig = px.choropleth_mapbox(
                    gosterilecek_veri,
                    geojson=adana_geojson,
                    locations='İlçe',
                    featureidkey="properties.name",
                    color=gosterilecek_veri.columns[1],
                    color_continuous_scale=renk_skalasi,
                    # Harita stilini ve başlangıç görünümünü daha iyi hale getirme
                    mapbox_style="carto-positron", # Daha modern ve temiz bir stil
                    zoom=9.3, # Daha yakın başlangıç yakınlaştırma
                    center={"lat": 37.10, "lon": 35.60}, # Adana merkezine daha yakın bir konum
                    opacity=0.8,
                    labels={gosterilecek_veri.columns[1]: hover_adi}
                )
                fig.update_layout(
                    margin={"r":0,"t":0,"l":0,"b":0},
                    mapbox_accesstoken=None, # Public harita stilleri için token gerekmez
                    # Harita çerçevelerini daha belirgin yapalım
                    mapbox_layers=[
                        {
                            "sourcetype": "geojson",
                            "source": adana_geojson,
                            "type": "line",
                            "color": "black", # İlçe sınır çizgilerinin rengi
                            "line": {"width": 1.5} # İlçe sınır çizgilerinin kalınlığı
                        }
                    ]
                )
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Harita oluşturulurken beklenmedik bir hata oluştu. Lütfen Excel dosyanızdaki 'İlçe' isimlerinin doğru olduğundan ve Türkçe karakterlerin eşleştiğinden emin olun. Hata: {e}")

    st.markdown("---")

    st.subheader("🥇 En Değerli Müşteriler (Yıllık Ciroya Göre)")
    if ilce_df is None or ilce_df.empty:
        st.warning("En değerli müşterileri görüntülemek için `adana_ilce_ciro.xlsx` dosyası gereklidir.")
    else:
        top_n = st.slider("Listelenecek müşteri sayısı:", 5, 50, 10, step=5, key='degerli_slider')
        en_degerli_musteriler = ilce_df.groupby('Müşteri Ünvanı')['Brüt Fiyat'].sum().sort_values(ascending=False).head(top_n).reset_index()
        en_degerli_musteriler.rename(columns={'Müşteri Ünvanı': 'Müşteri Adı', 'Brüt Fiyat': 'Toplam Ciro (TL)'}, inplace=True)
        en_degerli_musteriler['Toplam Ciro (TL)'] = en_degerli_musteriler['Toplam Ciro (TL)'].apply(lambda x: f"₺{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.dataframe(en_degerli_musteriler, use_container_width=True, hide_index=True)

    if satis_df is not None:
        st.markdown("---")
        st.subheader("❤️ Sadık Müşteriler (İşlem Sayısı)")
        top_n_sadik = st.slider("Listelenecek sadık müşteri sayısı:", 5, 50, 10, step=5, key='sadik_slider')
        sadik_musteriler = satis_df['Müşteri'].value_counts().head(top_n_sadik).reset_index()
        sadik_musteriler.columns = ['Müşteri Adı', 'Toplam İşlem Sayısı']
        st.dataframe(sadik_musteriler, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("😴 'Uyuyan' Müşteriler (Son İşlem Tarihine Göre)")
        son_islem_gunleri = satis_df.groupby('Müşteri')['Gün'].max().reset_index()
        son_islem_gunleri.columns = ['Müşteri', 'Gecikme Günü']
        bugunun_tarihi = datetime.today().date()
        son_islem_gunleri['Son İşlem Tarihi'] = son_islem_gunleri['Gecikme Günü'].apply(lambda x: bugunun_tarihi - pd.Timedelta(days=x) if pd.notna(x) else None)
        gecikme_gunu = st.slider("İşlem görmeyen minimum gün sayısı:", 30, 180, 60)
        uyuyan_musteriler = son_islem_gunleri[son_islem_gunleri['Gecikme Günü'] >= gecikme_gunu].sort_values(by='Gecikme Günü', ascending=False)
        if not uyuyan_musteriler.empty:
            st.info(f"Son işlemi **{gecikme_gunu} günden** eski olan müşteriler listeleniyor.")
            st.dataframe(uyuyan_musteriler[['Müşteri', 'Gecikme Günü', 'Son İşlem Tarihi']], use_container_width=True, hide_index=True, column_config={"Gecikme Günü": "Gecikme Günü", "Son İşlem Tarihi": st.column_config.DateColumn(format="YYYY-MM-DD")})
        else:
            st.success("Belirlenen kriterde uyuyan müşteri bulunamadı.")
    else:
        st.warning("Sadık ve uyuyan müşterileri analiz etmek için `rapor.xls` dosyası gereklidir.")

    st.subheader("🥇 En Değerli Müşteriler (Yıllık Ciroya Göre)")
    if ilce_df is None or ilce_df.empty:
        st.warning("En değerli müşterileri görüntülemek için `adana_ilce_ciro.xlsx` dosyası gereklidir.")
    else:
        top_n = st.slider("Listelenecek müşteri sayısı:", 5, 50, 10, step=5, key='degerli_slider')
        en_degerli_musteriler = ilce_df.groupby('Müşteri Ünvanı')['Brüt Fiyat'].sum().sort_values(ascending=False).head(top_n).reset_index()
        en_degerli_musteriler.rename(columns={'Müşteri Ünvanı': 'Müşteri Adı', 'Brüt Fiyat': 'Toplam Ciro (TL)'}, inplace=True)
        en_degerli_musteriler['Toplam Ciro (TL)'] = en_degerli_musteriler['Toplam Ciro (TL)'].apply(lambda x: f"₺{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.dataframe(en_degerli_musteriler, use_container_width=True, hide_index=True)

    if satis_df is not None:
        st.markdown("---")
        st.subheader("❤️ Sadık Müşteriler (İşlem Sayısı)")
        top_n_sadik = st.slider("Listelenecek sadık müşteri sayısı:", 5, 50, 10, step=5, key='sadik_slider')
        sadik_musteriler = satis_df['Müşteri'].value_counts().head(top_n_sadik).reset_index()
        sadik_musteriler.columns = ['Müşteri Adı', 'Toplam İşlem Sayısı']
        st.dataframe(sadik_musteriler, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("😴 'Uyuyan' Müşteriler (Son İşlem Tarihine Göre)")
        son_islem_gunleri = satis_df.groupby('Müşteri')['Gün'].max().reset_index()
        son_islem_gunleri.columns = ['Müşteri', 'Gecikme Günü']
        bugunun_tarihi = datetime.today().date()
        son_islem_gunleri['Son İşlem Tarihi'] = son_islem_gunleri['Gecikme Günü'].apply(lambda x: bugunun_tarihi - pd.Timedelta(days=x) if pd.notna(x) else None)
        gecikme_gunu = st.slider("İşlem görmeyen minimum gün sayısı:", 30, 180, 60)
        uyuyan_musteriler = son_islem_gunleri[son_islem_gunleri['Gecikme Günü'] >= gecikme_gunu].sort_values(by='Gecikme Günü', ascending=False)
        if not uyuyan_musteriler.empty:
            st.info(f"Son işlemi **{gecikme_gunu} günden** eski olan müşteriler listeleniyor.")
            st.dataframe(uyuyan_musteriler[['Müşteri', 'Gecikme Günü', 'Son İşlem Tarihi']], use_container_width=True, hide_index=True, column_config={"Gecikme Günü": "Gecikme Günü", "Son İşlem Tarihi": st.column_config.DateColumn(format="YYYY-MM-DD")})
        else:
            st.success("Belirlenen kriterde uyuyan müşteri bulunamadı.")
    else:
        st.warning("Sadık ve uyuyan müşterileri analiz etmek için `rapor.xls` dosyası gereklidir.")
    st.markdown("---")

    st.subheader("🥇 En Değerli Müşteriler (Yıllık Ciroya Göre)")
    if ilce_df is None or ilce_df.empty:
        st.warning("En değerli müşterileri görüntülemek için `adana_ilce_ciro.xlsx` dosyası gereklidir.")
    else:
        top_n = st.slider("Listelenecek müşteri sayısı:", 5, 50, 10, step=5, key='degerli_slider')
        en_degerli_musteriler = ilce_df.groupby('Müşteri Ünvanı')['Brüt Fiyat'].sum().sort_values(ascending=False).head(top_n).reset_index()
        en_degerli_musteriler.rename(columns={'Müşteri Ünvanı': 'Müşteri Adı', 'Brüt Fiyat': 'Toplam Ciro (TL)'}, inplace=True)
        en_degerli_musteriler['Toplam Ciro (TL)'] = en_degerli_musteriler['Toplam Ciro (TL)'].apply(lambda x: f"₺{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.dataframe(en_degerli_musteriler, use_container_width=True, hide_index=True)

    if satis_df is not None:
        st.markdown("---")
        st.subheader("❤️ Sadık Müşteriler (İşlem Sayısı)")
        top_n_sadik = st.slider("Listelenecek sadık müşteri sayısı:", 5, 50, 10, step=5, key='sadik_slider')
        sadik_musteriler = satis_df['Müşteri'].value_counts().head(top_n_sadik).reset_index()
        sadik_musteriler.columns = ['Müşteri Adı', 'Toplam İşlem Sayısı']
        st.dataframe(sadik_musteriler, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("😴 'Uyuyan' Müşteriler (Son İşlem Tarihine Göre)")
        son_islem_gunleri = satis_df.groupby('Müşteri')['Gün'].max().reset_index()
        son_islem_gunleri.columns = ['Müşteri', 'Gecikme Günü']
        bugunun_tarihi = datetime.today().date()
        son_islem_gunleri['Son İşlem Tarihi'] = son_islem_gunleri['Gecikme Günü'].apply(lambda x: bugunun_tarihi - pd.Timedelta(days=x) if pd.notna(x) else None)
        gecikme_gunu = st.slider("İşlem görmeyen minimum gün sayısı:", 30, 180, 60)
        uyuyan_musteriler = son_islem_gunleri[son_islem_gunleri['Gecikme Günü'] >= gecikme_gunu].sort_values(by='Gecikme Günü', ascending=False)
        if not uyuyan_musteriler.empty:
            st.info(f"Son işlemi **{gecikme_gunu} günden** eski olan müşteriler listeleniyor.")
            st.dataframe(uyuyan_musteriler[['Müşteri', 'Gecikme Günü', 'Son İşlem Tarihi']], use_container_width=True, hide_index=True, column_config={"Gecikme Günü": "Gecikme Günü", "Son İşlem Tarihi": st.column_config.DateColumn(format="YYYY-MM-DD")})
        else:
            st.success("Belirlenen kriterde uyuyan müşteri bulunamadı.")
    else:
        st.warning("Sadık ve uyuyan müşterileri analiz etmek için `rapor.xls` dosyası gereklidir.")
    st.markdown("---")

    st.subheader("🥇 En Değerli Müşteriler (Yıllık Ciroya Göre)")
    if ilce_df is None or ilce_df.empty:
        st.warning("En değerli müşterileri görüntülemek için `adana_ilce_ciro.xlsx` dosyası gereklidir.")
    else:
        top_n = st.slider("Listelenecek müşteri sayısı:", 5, 50, 10, step=5, key='degerli_slider')
        en_degerli_musteriler = ilce_df.groupby('Müşteri Ünvanı')['Brüt Fiyat'].sum().sort_values(ascending=False).head(top_n).reset_index()
        en_degerli_musteriler.rename(columns={'Müşteri Ünvanı': 'Müşteri Adı', 'Brüt Fiyat': 'Toplam Ciro (TL)'}, inplace=True)
        en_degerli_musteriler['Toplam Ciro (TL)'] = en_degerli_musteriler['Toplam Ciro (TL)'].apply(lambda x: f"₺{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.dataframe(en_degerli_musteriler, use_container_width=True, hide_index=True)

    if satis_df is not None:
        st.markdown("---")
        st.subheader("❤️ Sadık Müşteriler (İşlem Sayısı)")
        top_n_sadik = st.slider("Listelenecek sadık müşteri sayısı:", 5, 50, 10, step=5, key='sadik_slider')
        sadik_musteriler = satis_df['Müşteri'].value_counts().head(top_n_sadik).reset_index()
        sadik_musteriler.columns = ['Müşteri Adı', 'Toplam İşlem Sayısı']
        st.dataframe(sadik_musteriler, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("😴 'Uyuyan' Müşteriler (Son İşlem Tarihine Göre)")
        son_islem_gunleri = satis_df.groupby('Müşteri')['Gün'].max().reset_index()
        son_islem_gunleri.columns = ['Müşteri', 'Gecikme Günü']
        bugunun_tarihi = datetime.today().date()
        son_islem_gunleri['Son İşlem Tarihi'] = son_islem_gunleri['Gecikme Günü'].apply(lambda x: bugunun_tarihi - pd.Timedelta(days=x) if pd.notna(x) else None)
        gecikme_gunu = st.slider("İşlem görmeyen minimum gün sayısı:", 30, 180, 60)
        uyuyan_musteriler = son_islem_gunleri[son_islem_gunleri['Gecikme Günü'] >= gecikme_gunu].sort_values(by='Gecikme Günü', ascending=False)
        if not uyuyan_musteriler.empty:
            st.info(f"Son işlemi **{gecikme_gunu} günden** eski olan müşteriler listeleniyor.")
            st.dataframe(uyuyan_musteriler[['Müşteri', 'Gecikme Günü', 'Son İşlem Tarihi']], use_container_width=True, hide_index=True, column_config={"Gecikme Günü": "Gecikme Günü", "Son İşlem Tarihi": st.column_config.DateColumn(format="YYYY-MM-DD")})
        else:
            st.success("Belirlenen kriterde uyuyan müşteri bulunamadı.")
    else:
        st.warning("Sadık ve uyuyan müşterileri analiz etmek için `rapor.xls` dosyası gereklidir.")
    st.markdown("---")

    st.subheader("🥇 En Değerli Müşteriler (Yıllık Ciroya Göre)")
    if ilce_df is None or ilce_df.empty:
        st.warning("En değerli müşterileri görüntülemek için `adana_ilce_ciro.xlsx` dosyası gereklidir.")
    else:
        top_n = st.slider("Listelenecek müşteri sayısı:", 5, 50, 10, step=5, key='degerli_slider')
        en_degerli_musteriler = ilce_df.groupby('Müşteri Ünvanı')['Brüt Fiyat'].sum().sort_values(ascending=False).head(top_n).reset_index()
        en_degerli_musteriler.rename(columns={'Müşteri Ünvanı': 'Müşteri Adı', 'Brüt Fiyat': 'Toplam Ciro (TL)'}, inplace=True)
        en_degerli_musteriler['Toplam Ciro (TL)'] = en_degerli_musteriler['Toplam Ciro (TL)'].apply(lambda x: f"₺{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.dataframe(en_degerli_musteriler, use_container_width=True, hide_index=True)

    if satis_df is not None:
        st.markdown("---")
        st.subheader("❤️ Sadık Müşteriler (İşlem Sayısı)")
        top_n_sadik = st.slider("Listelenecek sadık müşteri sayısı:", 5, 50, 10, step=5, key='sadik_slider')
        sadik_musteriler = satis_df['Müşteri'].value_counts().head(top_n_sadik).reset_index()
        sadik_musteriler.columns = ['Müşteri Adı', 'Toplam İşlem Sayısı']
        st.dataframe(sadik_musteriler, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("😴 'Uyuyan' Müşteriler (Son İşlem Tarihine Göre)")
        son_islem_gunleri = satis_df.groupby('Müşteri')['Gün'].max().reset_index()
        son_islem_gunleri.columns = ['Müşteri', 'Gecikme Günü']
        bugunun_tarihi = datetime.today().date()
        son_islem_gunleri['Son İşlem Tarihi'] = son_islem_gunleri['Gecikme Günü'].apply(lambda x: bugunun_tarihi - pd.Timedelta(days=x) if pd.notna(x) else None)
        gecikme_gunu = st.slider("İşlem görmeyen minimum gün sayısı:", 30, 180, 60)
        uyuyan_musteriler = son_islem_gunleri[son_islem_gunleri['Gecikme Günü'] >= gecikme_gunu].sort_values(by='Gecikme Günü', ascending=False)
        if not uyuyan_musteriler.empty:
            st.info(f"Son işlemi **{gecikme_gunu} günden** eski olan müşteriler listeleniyor.")
            st.dataframe(uyuyan_musteriler[['Müşteri', 'Gecikme Günü', 'Son İşlem Tarihi']], use_container_width=True, hide_index=True, column_config={"Gecikme Günü": "Gecikme Günü", "Son İşlem Tarihi": st.column_config.DateColumn(format="YYYY-MM-DD")})
        else:
            st.success("Belirlenen kriterde uyuyan müşteri bulunamadı.")
    else:
        st.warning("Sadık ve uyuyan müşterileri analiz etmek için `rapor.xls` dosyası gereklidir.")

def page_log_raporlari():
    st.title("🗒️ Kullanıcı Aktivite Logları")
    log_file = 'loglar.csv'
    try:
        log_df = pd.read_csv(log_file)
        log_df = log_df.sort_values(by='Zaman Damgası', ascending=False)
        st.info("Kullanıcıların sisteme giriş ve sayfa ziyaret aktiviteleri aşağıda listelenmiştir.")
        st.dataframe(log_df, use_container_width=True, hide_index=True)
    except FileNotFoundError:
        st.warning("Henüz herhangi bir log kaydı bulunmamaktadır.")
    except Exception as e:
        st.error(f"Log raporları okunurken bir hata oluştu: {e}")

def page_senaryo_analizi(satis_df, stok_df, satis_hedef_df):
    st.title("♟️ Senaryo Analizi (What-If)")
    if satis_df is None or stok_df is None or satis_hedef_df is None or satis_hedef_df.empty:
        st.warning("Bu modülün çalışması için `rapor.xls`, `stok.xls` ve `satis-hedef.xlsx` dosyalarının yüklenmiş olması gerekmektedir.")
        return
    try:
        total_row = satis_hedef_df[satis_hedef_df['Satış Temsilcisi'].str.strip() == 'TOPLAM']
        mevcut_toplam_satis = total_row['SATIŞ'].sum()
    except Exception:
        st.error("`satis-hedef.xlsx` dosyasındaki TOPLAM satırları okunamadı. Lütfen dosya formatını kontrol edin.")
        return
    mevcut_toplam_bakiye = satis_df['Kalan Tutar Total'].sum()
    vadesi_gecmis_df = satis_df[(satis_df['Gün'] > 0) & (satis_df['Kalan Tutar Total'] > 0)]
    toplam_vadesi_gecmis = vadesi_gecmis_df['Kalan Tutar Total'].sum()
    mevcut_stok_degeri = stok_df['Brüt Tutar'].sum()

    st.markdown("---")
    st.subheader("Genel Performans Simülasyonu")
    col1, col2 = st.columns([1, 2])
    with col1:
        satis_degisim_yuzde = st.slider("Satış Performansı Değişimi (%)", -50, 100, 0, 1, key="satis_slider")
        tahsilat_yuzde = st.slider("Vadesi Geçmiş Tahsilat Oranı (%)", 0, 100, 0, 5, key="tahsilat_slider")
    with col2:
        simulasyon_satis = mevcut_toplam_satis * (1 + satis_degisim_yuzde / 100)
        satis_fark = simulasyon_satis - mevcut_toplam_satis
        tahsil_edilen_tutar = toplam_vadesi_gecmis * (tahsilat_yuzde / 100)
        simulasyon_bakiye = mevcut_toplam_bakiye - tahsil_edilen_tutar
        kpi1, kpi2, kpi3, kpi4 = st.columns(2)
        kpi1.metric("Mevcut Ciro", f"₺{mevcut_toplam_satis:,.0f}")
        kpi2.metric("Simülasyon Sonrası Ciro", f"₺{simulasyon_satis:,.0f}", delta=f"₺{satis_fark:,.0f}")
        kpi3.metric("Mevcut Toplam Bakiye", f"₺{mevcut_toplam_bakiye:,.0f}")
        kpi4.metric("Simülasyon Sonrası Bakiye", f"₺{simulasyon_bakiye:,.0f}", delta=f"-₺{tahsil_edilen_tutar:,.0f}", delta_color="inverse")
    
    st.markdown("---")
    st.subheader("Stok ve Kârlılık Simülasyonu")
    col3, col4 = st.columns([1, 2])
    with col3:
        stok_zam_yuzde = st.slider("Stok Değerine Zam Oranı (%)", 0, 50, 0, 1)
        maliyet_orani = st.slider("Ortalama Ürün Maliyet Oranı (%)", 0, 100, 75, 1)
        iskonto_orani = st.slider("Genel Satış İskonto Oranı (%)", 0, 50, 0, 1)
    with col4:
        simulasyon_stok_degeri = mevcut_stok_degeri * (1 + stok_zam_yuzde / 100)
        stok_deger_artisi = simulasyon_stok_degeri - mevcut_stok_degeri
        iskontolu_satis = simulasyon_satis * (1 - iskonto_orani / 100)
        toplam_maliyet = iskontolu_satis * (maliyet_orani / 100)
        brut_kar = iskontolu_satis - toplam_maliyet
        kpi5, kpi6, kpi7, kpi8, kpi9 = st.columns(2)
        kpi5.metric("Mevcut Stok Değeri", f"₺{mevcut_stok_degeri:,.0f}")
        kpi6.metric("Zam Sonrası Stok Değeri", f"₺{simulasyon_stok_degeri:,.0f}", delta=f"₺{stok_deger_artisi:,.0f}")
        st.markdown("")
        kpi7.metric("İskontolu Ciro", f"₺{iskontolu_satis:,.0f}")
        kpi8.metric("Toplam Maliyet", f"₺{toplam_maliyet:,.0f}")
        kpi9.metric("Brüt Kâr", f"₺{brut_kar:,.0f}")
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

def main_app(satis_df, stok_df, satis_hedef_df, solen_borcu_degeri, ilce_df):
    st.markdown("""
    <style>
    div[data-testid="stMetric"] { background-color: #F7F7F7 !important; border: 2px solid #FDB022 !important; border-radius: 10px !important; padding: 20px !important; transition: transform 0.3s ease-in-out, box-shadow 0.3s ease-in-out !important; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important; }
    div[data-testid="stMetric"]:hover { transform: translateY(-5px) !important; box-shadow: 0 8px 12px rgba(0, 0, 0, 0.15) !important; }
    div[data-testid="stMetric"] label { color: #333333 !important; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #333333 !important; }
    div[data-testid="stMetric"] div[data-testid="stMetricDelta"] { color: #333333 !important; }
    div[data-testid="stSelectbox"] > label { font-size: 16px !important; color: #E6EAF5 !important; margin-bottom: 8px !important; font-weight: bold !important; }
    .stSelectbox div[data-baseweb="select"] > div { background-color: #0E1528 !important; border: 2px solid #FDB022 !important; color: #FDB022 !important; font-weight: bold !important; border-radius: 8px !important; font-size: 18px !important; }
    .stSelectbox svg { fill: #FDB022 !important; }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.image("logo.jpeg", use_container_width=True)
        st.markdown("""<style>@import url('https://fonts.googleapis.com/css2?family=Exo+2:wght@700&display=swap');</style><div style="font-family: 'Exo 2', sans-serif; font-size: 28px; text-align: center; margin-bottom: 20px;"><span style="color: #FDB022;">ÖZLİDER TÜKETİM</span><span style="color: #E6EAF5;">- ŞÖLEN CRM</span></div>""", unsafe_allow_html=True)
        
        menu_options = ["Genel Bakış", "Tüm Temsilciler", "Satış/Hedef", "Yaşlandırma", "Stok", "Müşteri Analizi", "Şölen", "Hizmet Faturaları", "Senaryo Analizi"]
        menu_icons = ['graph-up', 'people-fill', 'bullseye', 'clock-history', 'box-seam', 'person-lines-fill', 'gift-fill', 'receipt-cutoff', 'robot']
        
        if st.session_state.get('current_user') == "Fatih Bakıcı":
            menu_options.append("Log Raporları")
            menu_icons.append('book')
            
        secim = option_menu(menu_title=None, options=menu_options, icons=menu_icons, menu_icon="cast", default_index=0, orientation="vertical", styles={"container": {"padding": "0!important", "background-color": "transparent"}, "icon": {"color": "#FDB022", "font-size": "20px"}, "nav-link": {"font-size": "16px", "text-align": "left", "margin":"5px", "--hover-color": "#111A33"}, "nav-link-selected": {"background-color": "#3B2F8E"},})

    if 'last_page' not in st.session_state or st.session_state['last_page'] != secim:
        log_user_activity(st.session_state['current_user'], f"Sayfa ziyareti: {secim}", page_name=secim)
        st.session_state['last_page'] = secim

    if secim == "Genel Bakış":
        page_genel_bakis(satis_df, stok_df, solen_borcu_degeri)
    elif secim == "Tüm Temsilciler":
        page_tum_temsilciler(satis_df, satis_hedef_df)
    elif secim == "Satış/Hedef":
        page_satis_hedef(satis_hedef_df)
    elif secim == "Yaşlandırma":
        page_yaslandirma(satis_df)
    elif secim == "Stok":
        page_stok(stok_df)
    elif secim == "Müşteri Analizi":
        page_musteri_analizi(satis_df, ilce_df)
    elif secim == "Şölen":
        page_solen(solen_borcu_degeri)
    elif secim == "Hizmet Faturaları":
        page_hizmet_faturalari()
    elif secim == "Log Raporları":
        page_log_raporlari()
    elif secim == "Senaryo Analizi":
        page_senaryo_analizi(satis_df, stok_df, satis_hedef_df)
        
    add_developer_credit()

def login_page():
    st.markdown("""
        <style>
            .stApp { background-color: transparent !important; }
            .login-container { padding: 40px; border-radius: 10px; background-color: rgba(17, 26, 51, 0.8); text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.5); margin: auto; width: fit-content; }
            .stTextInput>div>div>input { color: #FDB022; background-color: #0E1528; border: 2px solid #3B2F8E; border-radius: 5px; box-shadow: inset 2px 2px 5px rgba(0,0,0,0.5), inset -2px -2px 5px rgba(255,255,255,0.1); }
            .stButton>button { color: #111A33; background-color: #FDB022; border-radius: 5px; font-weight: bold; box-shadow: 2px 2px 5px rgba(0,0,0,0.5); }
        </style>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("logo.jpeg", width=250)

        with st.container():
            st.markdown("<div class='login-container'>", unsafe_allow_html=True)
            st.title("🔐 Giriş Ekranı")
            st.markdown("Lütfen devam etmek için kullanıcı adı ve şifrenizi girin.")
            usernames = list(USER_CREDENTIALS.keys())
            selected_username = st.selectbox("Kullanıcı Adı", usernames, key='username_select')
            password = st.text_input("Şifre", type="password", key='password_input')
            if st.button("Giriş Yap", key='login_button'):
                if USER_CREDENTIALS.get(selected_username) == password:
                    st.session_state['logged_in'] = True
                    st.session_state['current_user'] = selected_username
                    log_user_activity(selected_username, "Giriş Yaptı")
                    st.success("Giriş başarılı!")
                    st.rerun()
                else:
                    st.error("Hatalı şifre.")
            st.markdown("</div>", unsafe_allow_html=True)

# --- ANA KOD AKIŞI ---
satis_df_cache = satis_veri_yukle('rapor.xls')
stok_df_cache = stok_veri_yukle('stok.xls')
satis_hedef_df_raw_cache = satis_hedef_veri_yukle('satis-hedef.xlsx')
solen_borcu_degeri_cache = solen_borc_excel_oku('solen_borc.xlsx')
temiz_satis_hedef_df_cache = parse_satis_hedef_excel_robust(satis_hedef_df_raw_cache)
ilce_df_cache = adana_ilce_veri_yukle('adana_ilce_ciro.xlsx')


if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if st.session_state['logged_in']:
    main_app(satis_df_cache, stok_df_cache, temiz_satis_hedef_df_cache, solen_borcu_degeri_cache, ilce_df_cache)
else:
    login_page()