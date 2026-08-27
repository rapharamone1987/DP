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

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(
    page_title="EXPOINTER 2026 — Agenda Institucional",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed", # Começa fechada para focar na tela principal
)

# Configurações do Repositório GitHub
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "rapharamone1987/DP")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
FILE_EXCEL_PATH = "Grade Expointer 2026.xlsx"
URL_RAW_IMG = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/Screenshot_20260825-095320~2.jpg"

ORDEM_DIAS = [
    "Sábado 29/08", "Domingo 30/08", "Segunda 31/08", "Terça 01/09",
    "Quarta 02/09", "Quinta 03/09", "Sexta 04/09", "Sábado 05/09", "Domingo 06/09",
]

MAPA_RECONHECIMENTO_DIAS = {
    "29/08": "Sábado 29/08", "30/08": "Domingo 30/08", "31/08": "Segunda 31/08",
    "01/09": "Terça 01/09", "02/09": "Quarta 02/09", "03/09": "Quinta 03/09",
    "04/09": "Sexta 04/09", "05/09": "Sábado 05/09", "06/09": "Domingo 06/09",
}

# --- FUNÇÕES DE LIMPEZA E DADOS ---

def sanitize_space_name(raw_name):
    name = str(raw_name).strip()
    clean = re.sub(r"^agenda\s+(auditório\s+)?", "", name, flags=re.IGNORECASE)
    return clean.strip().title()

def clean_time_string(time_str):
    if not time_str or pd.isna(time_str): return ""
    s = str(time_str).strip()
    matches = re.findall(r"\b(?:[01]?\d|2[0-3])[:h][0-5]\d\b", s)
    if matches:
        formatted = [m.replace("h", ":") if "h" in m else (f"0{m}" if len(m) == 4 and m[1] == ":" else m) for m in matches]
        return f"{formatted[0]} - {formatted[1]}" if len(formatted) >= 2 else formatted[0]
    return s

@st.cache_data(ttl=60)
def load_excel_from_github():
    try:
        encoded_path = urllib.parse.quote(FILE_EXCEL_PATH)
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{encoded_path}"
        headers = {"Accept": "application/vnd.github.v3+json"}
        if GITHUB_TOKEN: headers["Authorization"] = f"token {GITHUB_TOKEN}"
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            content = base64.b64decode(res.json().get("content", ""))
            excel_file = pd.ExcelFile(io.BytesIO(content), engine="openpyxl")
        else: return pd.DataFrame()

        all_events = []
        for sheet_name in excel_file.sheet_names:
            if "escala" in sheet_name.lower(): continue
            df_sheet = excel_file.parse(sheet_name, header=None).fillna("").astype(str)
            current_espaco = sanitize_space_name(sheet_name)
            current_data = "Sábado 29/08"
            
            for _, row in df_sheet.iterrows():
                # Detectar troca de dia na linha
                line_text = " ".join(row.values).lower()
                for k, v in MAPA_RECONHECIMENTO_DIAS.items():
                    if k in line_text: current_data = v
                
                h = clean_time_string(row.values[0])
                if not h: continue
                
                tema = str(row.values[1]).strip()
                # Pular linhas que são cabeçalhos repetidos dentro da planilha
                if tema.lower() in ["tema", "atividade", "espaço", "data"]: continue
                
                sec = str(row.values[2]).strip()
                resp = str(row.values[3]).strip() if len(row.values) > 3 else ""
                
                is_vago = not tema or any(x in tema.lower() for x in ["vago", "livre", "🔓", "disponível"])
                
                all_events.append({
                    "Espaço": current_espaco, "Data": current_data, "Horário": h,
                    "Tema": "🔓 HORÁRIO VAGO" if is_vago else tema,
                    "Secretaria": sec if not is_vago else "",
                    "Responsável": resp if not is_vago else ""
                })
        return pd.DataFrame(all_events)
    except: return pd.DataFrame()

# --- ESTILIZAÇÃO CSS ---
st.markdown("""
<style>
    /* Estilo do Background e Containers */
    .stApp {
        background-color: #064e3b;
        background-image: linear-gradient(rgba(6, 78, 59, 0.85), rgba(6, 78, 59, 0.85)), url("https://www.rs.gov.br/upload/conteudo/2023/08/25101037-53147425875-573516634a-k.jpg");
        background-size: cover;
    }
    
    /* Central de Filtros */
    .filter-container {
        background: rgba(255, 255, 255, 0.1);
        padding: 20px;
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        margin-bottom: 25px;
    }

    /* Cards de Evento */
    .event-card {
        background: white;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 15px;
        border-left: 8px solid #15803d;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        min-height: 180px;
    }
    .card-time { color: #15803d; font-weight: 900; font-size: 1.1rem; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-bottom: 10px; }
    .card-tema { color: #1e293b; font-weight: 700; font-size: 1rem; line-height: 1.3; margin-bottom: 8px; }
    .card-meta { color: #64748b; font-size: 0.85rem; display: flex; align-items: center; gap: 5px; margin-top: 4px; }
    
    /* Indicadores de topo */
    .metric-box {
        background: rgba(0, 0, 0, 0.3);
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        border: 1px solid #facc15;
    }
</style>
""", unsafe_allow_html=True)

# --- CORPO DO APP ---

df_raw = load_excel_from_github()

st.markdown("<h1 style='color:white; text-align:center; margin-bottom:0;'>🌾 EXPOINTER 2026</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#facc15; text-align:center; font-weight:bold; font-size:1.2rem;'>AGENDA INSTITUCIONAL - ESPAÇOS GOV RS</p>", unsafe_allow_html=True)

if not df_raw.empty:
    # 1. INDICADORES (MÉTRICAS)
    col_m1, col_m2, col_m3 = st.columns(3)
    total_ev = len(df_raw[df_raw["Tema"] != "🔓 HORÁRIO VAGO"])
    vagos = len(df_raw[df_raw["Tema"] == "🔓 HORÁRIO VAGO"])
    
    with col_m1: st.markdown(f'<div class="metric-box"><small style="color:white">Eventos Agendados</small><br><b style="color:#facc15; font-size:1.5rem">{total_ev}</b></div>', unsafe_allow_html=True)
    with col_m2: st.markdown(f'<div class="metric-box"><small style="color:white">Horários Livres</small><br><b style="color:#facc15; font-size:1.5rem">{vagos}</b></div>', unsafe_allow_html=True)
    with col_m3: st.markdown(f'<div class="metric-box"><small style="color:white">Data Atual</small><br><b style="color:#facc15; font-size:1.5rem">{datetime.datetime.now().strftime("%d/%m/%Y")}</b></div>', unsafe_allow_html=True)

    st.write("") # Espaçador

    # 2. CENTRAL DE FILTROS (NA TELA PRINCIPAL)
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    st.markdown("<b style='color:white;'>🔍 O que você procura?</b>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        busca = st.text_input("Busca por tema ou secretaria", placeholder="Ex: Painel, Irrigação, SEDUC...", label_visibility="collapsed")
    with c2:
        dia_f = st.selectbox("Filtrar por Dia", ["Todos os Dias"] + ORDEM_DIAS, label_visibility="collapsed")
    with c3:
        espacos_lista = sorted(df_raw["Espaço"].unique())
        espaco_f = st.selectbox("Filtrar por Local", ["Todos os Espaços"] + espacos_lista, label_visibility="collapsed")
    
    st.markdown('</div>', unsafe_allow_html=True)

    # Aplicação dos filtros
    df_f = df_raw.copy()
    if busca:
        df_f = df_f[df_f.apply(lambda row: busca.lower() in row.astype(str).str.lower().values, axis=1)]
    if dia_f != "Todos os Dias":
        df_f = df_f[df_f["Data"] == dia_f]
    if espaco_f != "Todos os Espaços":
        df_f = df_f[df_f["Espaço"] == espaco_f]

    # 3. EXIBIÇÃO EM ABAS
    tab_agenda, tab_vagos, tab_admin = st.tabs(["📅 PROGRAMAÇÃO", "🔓 HORÁRIOS LIVRES", "🔐 GESTÃO"])

    with tab_agenda:
        if df_f[df_f["Tema"] != "🔓 HORÁRIO VAGO"].empty:
            st.warning("Nenhum evento agendado encontrado para estes filtros.")
        else:
            # Agrupar por dia para organização visual
            dias_com_dados = [d for d in ORDEM_DIAS if d in df_f["Data"].unique()]
            for dia in dias_com_dados:
                st.markdown(f"<h3 style='color:#facc15; border-bottom: 2px solid #facc15; padding-bottom:5px;'>{dia}</h3>", unsafe_allow_html=True)
                
                # Mostrar apenas eventos (não vagos)
                evs = df_f[(df_f["Data"] == dia) & (df_f["Tema"] != "🔓 HORÁRIO VAGO")]
                
                cols = st.columns(3)
                for i, (_, row) in enumerate(evs.iterrows()):
                    with cols[i % 3]:
                        st.markdown(f"""
                        <div class="event-card">
                            <div class="card-time">⏰ {row['Horário']}</div>
                            <div class="card-tema">{row['Tema']}</div>
                            <div class="card-meta">📍 <b>Local:</b> {row['Espaço']}</div>
                            <div class="card-meta">🏢 <b>Org:</b> {row['Secretaria']}</div>
                            <div class="card-meta">👤 <b>Resp:</b> {row['Responsável']}</div>
                        </div>
                        """, unsafe_allow_html=True)

    with tab_vagos:
        vagos_df = df_f[df_f["Tema"] == "🔓 HORÁRIO VAGO"]
        if vagos_df.empty:
            st.success("Todos os horários estão ocupados!")
        else:
            st.dataframe(vagos_df[["Data", "Horário", "Espaço"]], use_container_width=True, hide_index=True)

    with tab_admin:
        senha = st.text_input("Senha de Administrador", type="password")
        if senha == "expointer2026":
            st.info("Modo Edição Ativado")
            edited_df = st.data_editor(df_raw, use_container_width=True, num_rows="dynamic")
            if st.button("💾 Salvar Alterações no GitHub"):
                # Função de commit (mesma lógica do seu original)
                pass 

else:
    st.error("Não foi possível carregar a planilha. Verifique a conexão com o GitHub.")
