import streamlit as st
import pandas as pd
from streamlit_option_menu import option_menu
from datetime import datetime, timedelta
import io
import csv
import plotly.graph_objects as go
import plotly.express as px

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

# --- EXCEL'E DÖNÜŞTÜRME YARDIMCI FONKSİYONU ---
def to_excel(df):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Rapor')
    writer.close()
    processed_data = output.getvalue()
    return processed_data

# --- LOGLAMA FONKSİYONU ---
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
# --- TÜM SAYFA FONKSİYONLARI (TAM VE DÜZELTİLMİŞ HALLERİ) ---
# =======================================================================================

def page_genel_bakis(satis_df, stok_df, solen_borcu_degeri):
    st.title("📈 Genel Bakış")
    st.markdown("İşletmenizin genel durumunu gösteren anahtar performans göstergeleri.")
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
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        kpi_col1.metric("1-35 Gün Arası Alacak", f"{gun_1_35_genel:,.2f} TL")
        kpi_col2.metric("35+ Gün Geçikme", f"{ustu_35_gun_genel:,.2f} TL")
        kpi_col3.metric("45+ Gün Geçikme", f"{ustu_45_gun_genel:,.2f} TL")
        kpi_col4.metric("60+ Gün Geçikme (Riskli)", f"{ustu_60_gun_genel:,.2f} TL", delta_color="inverse")
        st.markdown("---")

        st.subheader("Temsilci Bazında Müşteri Bakiyelerinin Dağılımı")
        col1_chart, col2_table = st.columns([2, 1]) 

        with col1_chart:
            temsilci_bakiyeleri = satis_df[satis_df['Kalan Tutar Total'] > 0].groupby('ST')['Kalan Tutar Total'].sum().reset_index()
            temsilci_bakiyeleri.columns = ['Satış Temsilcisi', 'Toplam Bakiye']
            temsilci_bakiyeleri['parent'] = "Toplam Bakiye" 
            
            fig = px.sunburst(
                temsilci_bakiyeleri,
                path=['parent', 'Satış Temsilcisi'],
                values='Toplam Bakiye',
                color='Toplam Bakiye',
                color_continuous_scale='YlOrRd',
                title="Temsilcilerin Toplam Bakiyedeki Payları"
            )
            fig.update_traces(textinfo='label+percent parent', hovertemplate='<b>%{label}</b><br>Bakiye: ₺%{value:,.2f}<extra></extra>')
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
        
        personel_hedef_df = satis_hedef_df[satis_hedef_df['Satış Temsilcisi'] == secilen_temsilci]
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
        format_sozlugu = {'Brüt_Tutar': '{:,.2f} TL', fiyat_sutunu: '{:,.2f} TL'}
    else:
        gosterilecek_sutunlar = [depo_adi_sutunu, urun_kodu_sutunu, urun_adi_sutunu, miktar_sutunu, fiyat_sutunu, brut_tutar_sutunu]
        format_sozlugu = {brut_tutar_sutunu: '{:,.2f} TL', fiyat_sutunu: '{:,.2f} TL'}
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
    st.dataframe(en_degerli_musteriler, use_container_width=True, hide_index=True, column_config={"Toplam Bakiye (TL)": st.column_config.NumberColumn(format="%.2f TL")})
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
        st.dataframe(uyuyan_musteriler[['Müşteri', 'Gecikme Günü', 'Son İşlem Tarihi']], use_container_width=True, hide_index=True, column_config={"Gecikme Günü": "Gecikme Günü", "Son İşlem Tarihi": st.column_config.DateColumn(format="YYYY-MM-DD")})
    else:
        st.success("Belirlenen kriterde uyuyan müşteri bulunamadı.")

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
    st.info("Bu araç, potansiyel kararların sonuçlarını öngörmenize yardımcı olur. Kontrol araçlarıyla oynayarak sonuçları anlık olarak gözlemleyebilirsiniz.")

    if satis_df is None or stok_df is None or satis_hedef_df is None or satis_hedef_df.empty:
        st.warning("Bu modülün çalışması için `rapor.xls`, `stok.xls` ve `satis-hedef.xlsx` dosyalarının yüklenmiş olması gerekmektedir.")
        return

    try:
        total_row = satis_hedef_df[satis_hedef_df['Satış Temsilcisi'].str.strip() == 'TOPLAM']
        mevcut_toplam_hedef = total_row['HEDEF'].sum()
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
        kpi1, kpi2 = st.columns(2)
        kpi1.metric("Mevcut Ciro", f"₺{mevcut_toplam_satis:,.0f}")
        kpi2.metric("Simülasyon Sonrası Ciro", f"₺{simulasyon_satis:,.0f}", delta=f"₺{satis_fark:,.0f}")
        kpi3, kpi4 = st.columns(2)
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
        kpi5, kpi6 = st.columns(2)
        kpi5.metric("Mevcut Stok Değeri", f"₺{mevcut_stok_degeri:,.0f}")
        kpi6.metric("Zam Sonrası Stok Değeri", f"₺{simulasyon_stok_degeri:,.0f}", delta=f"₺{stok_deger_artisi:,.0f}")
        st.markdown("")
        kpi7, kpi8, kpi9 = st.columns(3)
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

def main_app(satis_df, stok_df, satis_hedef_df, solen_borcu_degeri):
    with st.sidebar:
        st.image("logo.jpeg", use_container_width=True)
        st.markdown("""<style>@import url('https://fonts.googleapis.com/css2?family=Exo+2:wght@700&display=swap');</style><div style="font-family: 'Exo 2', sans-serif; font-size: 28px; text-align: center; margin-bottom: 20px;"><span style="color: #FDB022;">ÖZLİDER TÜKETİM</span><span style="color: #E6EAF5;">- ŞÖLEN CRM</span></div>""", unsafe_allow_html=True)
        
        menu_options = ["Genel Bakış", "Tüm Temsilciler", "Satış/Hedef", "Yaşlandırma", "Stok", "Müşteri Analizi", "Şölen", "Hizmet Faturaları", "Senaryo Analizi"]
        menu_icons = ['graph-up', 'people-fill', 'bullseye', 'clock-history', 'box-seam', 'person-lines-fill', 'gift-fill', 'receipt-cutoff', 'robot']
        
        if st.session_state.get('current_user') == "Fatih Bakıcı":
            menu_options.append("Log Raporları")
            menu_icons.append('book')
            
        secim = option_menu(menu_title=None, 
                                options=menu_options, 
                                icons=menu_icons, 
                                menu_icon="cast", 
                                default_index=0, 
                                orientation="vertical", 
                                styles={"container": {"padding": "0!important", "background-color": "transparent"}, 
                                        "icon": {"color": "#FDB022", "font-size": "20px"}, 
                                        "nav-link": {"font-size": "16px", "text-align": "left", "margin":"5px", "--hover-color": "#111A33"}, 
                                        "nav-link-selected": {"background-color": "#3B2F8E"},})

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
    elif secim == "Senaryo Analizi":
        page_senaryo_analizi(satis_df, stok_df, satis_hedef_df)
    elif secim == "Müşteri Analizi":
        page_musteri_analizi(satis_df)
    elif secim == "Şölen":
        page_solen(solen_borcu_degeri)
    elif secim == "Hizmet Faturaları":
        page_hizmet_faturalari()
    elif secim == "Log Raporları":
        page_log_raporlari()
        
    add_developer_credit()

def login_page():
    st.markdown("""
        <style>
            .stApp {
                background-color: transparent !important;
            }
            .login-container {
                padding: 40px;
                border-radius: 10px;
                background-color: rgba(17, 26, 51, 0.8);
                text-align: center;
                box-shadow: 0 4px 10px rgba(0,0,0,0.5);
                margin: auto;
                width: fit-content;
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

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if st.session_state['logged_in']:
    main_app(satis_df_cache, stok_df_cache, temiz_satis_hedef_df_cache, solen_borcu_degeri_cache)
else:
    login_page()