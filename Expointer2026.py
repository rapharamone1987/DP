import base64
import datetime
import io
import json
import re
import urllib.parse
import urllib.request
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
import requests
import streamlit as st

# --- 1. CONFIGURAÇÃO E ESTILO ---
st.set_page_config(
    page_title="EXPOINTER 2026 | Gestão Institucional",
    page_icon="🌾",
    layout="wide",
)

# Configurações via Secrets
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "rapharamone1987/DP")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
FILE_EXCEL_PATH = "Grade Expointer 2026.xlsx"
URL_RAW_IMG = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/Screenshot_20260825-095320~2.jpg"

ORDEM_DIAS = [
    "Sábado 29/08", "Domingo 30/08", "Segunda 31/08", "Terça 01/09",
    "Quarta 02/09", "Quinta 03/09", "Sexta 04/09", "Sábado 05/09", "Domingo 06/09"
]

@st.cache_data(ttl=3600)
def load_bg(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        if GITHUB_TOKEN: headers["Authorization"] = f"token {GITHUB_TOKEN}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            return base64.b64encode(resp.read()).decode("utf-8")
    except: return ""

img_b64 = load_bg(URL_RAW_IMG)

def apply_custom_css():
    bg_style = f"url('data:image/jpeg;base64,{img_b64}')" if img_b64 else "linear-gradient(to right, #064e3b, #15803d)"
    st.markdown(f"""
    <style>
        .stApp {{
            background: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)), {bg_style} no-repeat center center fixed;
            background-size: cover;
        }}
        [data-testid="stMetricValue"] {{ font-size: 1.8rem !important; color: #facc15 !important; }}
        .event-card {{
            background: rgba(255, 255, 255, 0.95);
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
            border-left: 8px solid #15803d;
            box-shadow: 0 8px 16px rgba(0,0,0,0.3);
            transition: transform 0.2s;
        }}
        .event-card:hover {{ transform: translateY(-3px); }}
        .vago-card {{
            background: rgba(255, 255, 255, 0.1);
            border: 2px dashed #facc15;
            border-radius: 12px;
            padding: 15px;
            color: white;
            text-align: center;
        }}
        .status-badge {{
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.7rem;
            font-weight: bold;
            text-transform: uppercase;
        }}
    </style>
    """, unsafe_allow_html=True)

# --- 2. LÓGICA DE DADOS ---

def extract_minutes(horario_str):
    """Converte 'HH:MM' para minutos totais para cálculo de conflito."""
    match = re.search(r"(\d{2}):(\d{2})", str(horario_str))
    if match:
        h, m = map(int, match.groups())
        return h * 60 + m
    return 0

def check_conflicts(df):
    """Detecta se há sobreposição de horários no mesmo espaço e dia."""
    conflicts = []
    # Simples detecção de duplicidade de horário exato para este exemplo
    df['is_conflict'] = df.duplicated(subset=['Data', 'Espaço', 'Horário'], keep=False)
    return df

@st.cache_data(ttl=60)
def load_data():
    # ... (Mantenha sua lógica de load_excel_from_github aqui, mas adicione o check de conflito no final)
    # Por brevidade, vou focar nas melhorias de UI, mas assuma que df_data vem daqui.
    try:
        # Chamada original que você já tem...
        df = load_excel_from_github() # Função que você já escreveu
        return check_conflicts(df)
    except:
        return pd.DataFrame()

# --- 3. UI PRINCIPAL ---

apply_custom_css()

# Sidebar: Filtros e Ações
with st.sidebar:
    st.image("https://www.expointer.rs.gov.br/themes/custom/expointer/logo.png", width=200)
    st.title("⚙️ Painel de Controle")
    
    st.subheader("🔍 Filtros Globais")
    busca = st.text_input("Termo de busca", placeholder="Ex: Painel, Inovação...")
    
    # Carregamento prévio para popular filtros
    raw_df = load_excel_from_github()
    
    dias_sel = st.multiselect("📅 Dias", options=ORDEM_DIAS)
    espacos_sel = st.multiselect("📍 Espaços", options=sorted(raw_df['Espaço'].unique()) if not raw_df.empty else [])
    
    st.divider()
    st.subheader("📄 Exportação")
    # Botão de PDF movido para cá de forma mais elegante...

# Corpo Principal
st.markdown("<h1 style='color:white; text-align:center;'>🌾 EXPOINTER 2026</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#facc15; text-align:center; font-size:1.2rem; font-weight:bold;'>AGENDA INSTITUCIONAL DO GOVERNO DO RS</p>", unsafe_allow_html=True)

# Dashboard de Métricas
if not raw_df.empty:
    m1, m2, m3, m4 = st.columns(4)
    total_ev = len(raw_df[raw_df['Tema'] != "🔓 HORÁRIO VAGO"])
    vagos = len(raw_df[raw_df['Tema'] == "🔓 HORÁRIO VAGO"])
    ocupacao = (total_ev / (total_ev + vagos)) * 100 if (total_ev+vagos) > 0 else 0
    
    m1.metric("Eventos Agendados", total_ev)
    m2.metric("Espaços Livres", vagos)
    m3.metric("Taxa de Ocupação", f"{ocupacao:.1f}%")
    m4.metric("Dias de Evento", len(raw_df['Data'].unique()))

# Filtragem dos dados
df_display = raw_df.copy()
if busca:
    df_display = df_display[df_display.apply(lambda row: busca.lower() in row.astype(str).str.lower().values, axis=1)]
if dias_sel:
    df_display = df_display[df_display['Data'].isin(dias_sel)]
if espacos_sel:
    df_display = df_display[df_display['Espaço'].isin(espacos_sel)]

# TABS
tab1, tab2, tab3, tab4 = st.tabs(["📅 Agenda Visual", "📋 Tabela Completa", "🔓 Horários Vagos", "🔐 Administração"])

with tab1:
    if df_display.empty:
        st.warning("Nenhum evento encontrado para os filtros aplicados.")
    else:
        for dia in (dias_sel if dias_sel else ORDEM_DIAS):
            eventos_dia = df_display[df_display['Data'] == dia]
            if eventos_dia.empty: continue
            
            st.markdown(f"### 🗓️ {dia}")
            cols = st.columns(3)
            for idx, (_, row) in enumerate(eventos_dia.iterrows()):
                with cols[idx % 3]:
                    if row['Tema'] == "🔓 HORÁRIO VAGO":
                        st.markdown(f"""
                        <div class="vago-card">
                            <small>{row['Horário']}</small><br>
                            <strong>DISPONÍVEL</strong><br>
                            <small>{row['Espaço']}</small>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        conflict_border = "border: 2px solid #ef4444;" if row.get('is_conflict') else ""
                        st.markdown(f"""
                        <div class="event-card" style="{conflict_border}">
                            <div style="display:flex; justify-content:space-between;">
                                <span style="color:#15803d; font-weight:bold;">⏰ {row['Horário']}</span>
                                <span class="status-badge" style="background:#dcfce7; color:#166534;">Confirmado</span>
                            </div>
                            <div style="font-size:1.1rem; font-weight:700; color:#1e293b; margin:8px 0;">{row['Tema']}</div>
                            <div style="color:#0369a1; font-weight:600; font-size:0.85rem;">📍 {row['Espaço']}</div>
                            <hr style="margin:8px 0; opacity:0.2;">
                            <div style="font-size:0.8rem; color:#64748b;">
                                🏢 <b>{row['Secretaria']}</b><br>
                                👤 {row['Responsável']}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

with tab2:
    st.dataframe(df_display, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Filtro de Ocupação Imediata")
    # Lógica simplificada para mostrar o que está vago agora ou no próximo horário
    vagos_only = df_display[df_display['Tema'] == "🔓 HORÁRIO VAGO"]
    st.table(vagos_only[['Data', 'Horário', 'Espaço']])

with tab4:
    # Área de Edição (Mantenha sua lógica de senha e commit aqui)
    # DICA: Use st.expander para o histórico de alterações
    st.info("Acesse com sua credencial para modificar a planilha mestre.")
    # ... código de edição ...

# --- 4. GERADOR DE PDF MELHORADO ---
# (Modifique sua função generate_pdf_report para incluir um logo ou cores do RS)
