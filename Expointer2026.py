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
    initial_sidebar_state="expanded",
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
    "29/08": "Sábado 29/08", "sabado 29": "Sábado 29/08", "sábado 29": "Sábado 29/08",
    "30/08": "Domingo 30/08", "domingo 30": "Domingo 30/08",
    "31/08": "Segunda 31/08", "segunda 31": "Segunda 31/08",
    "01/09": "Terça 01/09", "terca 01": "Terça 01/09", "terça 01": "Terça 01/09",
    "02/09": "Quarta 02/09", "quarta 02": "Quarta 02/09",
    "03/09": "Quinta 03/09", "quinta 03": "Quinta 03/09",
    "04/09": "Sexta 04/09", "sexta 04": "Sexta 04/09",
    "05/09": "Sábado 05/09", "sabado 05": "Sábado 05/09",
    "06/09": "Domingo 06/09", "domingo 06": "Domingo 06/09",
}

space_mapping = {
    "Agenda Auditório ADMINISTRAÇÃO": "Auditório Administração",
    "Agenda Auditório ESPAÇO GOV": "Auditório Espaço Gov",
    "Agenda ARENA ESPAÇO GOV": "Arena Espaço Gov",
    "Agenda BANCADA ESPAÇO GOV": "Bancada Espaço Gov",
}

# --- FUNÇÕES DE SUPORTE ---

def sanitize_space_name(raw_name):
    if not raw_name: return "Espaço Geral"
    name = str(raw_name).strip()
    if name in space_mapping: return space_mapping[name]
    clean = re.sub(r"^agenda\s+(auditório\s+)?", "", name, flags=re.IGNORECASE)
    return clean.strip().title()

def detect_day_from_line(line_str):
    s = line_str.lower()
    for key, mapped_day in MAPA_RECONHECIMENTO_DIAS.items():
        if key in s:
            if "sabado" in key or "sábado" in key:
                if "05" in s or "5" in s: return "Sábado 05/09"
                return "Sábado 29/08"
            if "domingo" in key:
                if "06" in s or "6" in s: return "Domingo 06/09"
                return "Domingo 30/08"
            return mapped_day
    return None

def clean_time_string(time_str):
    if not time_str or pd.isna(time_str): return ""
    s = str(time_str).strip()
    matches = re.findall(r"\b(?:[01]?\d|2[0-3])[:h][0-5]\d\b", s)
    if matches:
        formatted = [m.replace("h", ":") if "h" in m else (f"0{m}" if len(m) == 4 and m[1] == ":" else m) for m in matches]
        return f"{formatted[0]} - {formatted[1]}" if len(formatted) >= 2 else formatted[0]
    return s

def extract_start_time(horario_str):
    if not horario_str: return "99:99"
    match = re.search(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b", str(horario_str))
    if match:
        time_val = match.group(0)
        return time_val if len(time_val) == 5 else f"0{time_val}"
    return "99:99"

def extract_end_time(horario_str):
    if not horario_str: return ""
    matches = re.findall(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b", str(horario_str))
    if len(matches) >= 2: return matches[1]
    elif len(matches) == 1:
        h, m = map(int, matches[0].split(":"))
        return f"{(h + 1) % 24:02d}:{m:02d}"
    return ""

def merge_consecutive_events(df):
    if df.empty: return df
    merged_rows = []
    for (espaco, data), group in df.groupby(["Espaço", "Data"], sort=False):
        group = group.copy()
        group["Hora_Start"] = group["Horário"].apply(extract_start_time)
        group = group.sort_values(by="Hora_Start")
        current_event = None
        for _, row in group.iterrows():
            if current_event is None:
                current_event = dict(row)
                current_event["Hora_Inicio"] = extract_start_time(row["Horário"])
                current_event["Hora_Fim"] = extract_end_time(row["Horário"])
            else:
                same_theme = current_event["Tema"] == row["Tema"]
                same_sec = current_event["Secretaria"] == row["Secretaria"]
                if same_theme and same_sec and row["Tema"] != "🔓 HORÁRIO VAGO":
                    new_end = extract_end_time(row["Horário"])
                    if new_end: current_event["Hora_Fim"] = new_end
                else:
                    if current_event["Hora_Inicio"] and current_event["Hora_Fim"]:
                        current_event["Horário"] = f"{current_event['Hora_Inicio']} - {current_event['Hora_Fim']}"
                    merged_rows.append(current_event)
                    current_event = dict(row)
                    current_event["Hora_Inicio"] = extract_start_time(row["Horário"])
                    current_event["Hora_Fim"] = extract_end_time(row["Horário"])
        if current_event:
            if current_event["Hora_Inicio"] and current_event["Hora_Fim"]:
                current_event["Horário"] = f"{current_event['Hora_Inicio']} - {current_event['Hora_Fim']}"
            merged_rows.append(current_event)
    return pd.DataFrame(merged_rows).drop(columns=[c for c in ["Hora_Start", "Hora_Inicio", "Hora_Fim"] if c in pd.DataFrame(merged_rows).columns], errors='ignore')

# --- CARREGAMENTO GITHUB ---

@st.cache_data(ttl=15)
def load_excel_from_github():
    try:
        encoded_path = urllib.parse.quote(FILE_EXCEL_PATH)
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{encoded_path}"
        headers = {"Accept": "application/vnd.github.v3+json"}
        if GITHUB_TOKEN: headers["Authorization"] = f"token {GITHUB_TOKEN}"
        res = requests.get(api_url, headers=headers)
        if res.status_code == 200:
            content_bytes = base64.b64decode(res.json().get("content", ""))
            excel_file = pd.ExcelFile(io.BytesIO(content_bytes), engine="openpyxl")
        else:
            raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{encoded_path}"
            with urllib.request.urlopen(raw_url) as resp:
                excel_file = pd.ExcelFile(io.BytesIO(resp.read()), engine="openpyxl")
        all_events = []
        for sheet_name in excel_file.sheet_names:
            if "escala" in sheet_name.lower() or "equipe" in sheet_name.lower(): continue
            df_sheet = excel_file.parse(sheet_name, header=None).fillna("").astype(str)
            current_espaco = sanitize_space_name(sheet_name)
            current_data = "Sábado 29/08"
            for _, row in df_sheet.iterrows():
                line_str = " ".join([str(v) for v in row.values])
                det = detect_day_from_line(line_str)
                if det: current_data = det
                h = clean_time_string(row.values[0])
                if h:
                    tema, sec, resp = row.values[1], row.values[2], row.values[3] if len(row.values) > 3 else ""
                elif len(row.values) > 1 and clean_time_string(row.values[1]):
                    h, tema, sec, resp = clean_time_string(row.values[1]), row.values[2], row.values[3], row.values[4] if len(row.values) > 4 else ""
                else: continue
                is_vago = not tema or any(x in str(tema).lower() for x in ["vago", "livre", "disponível", "🔓"])
                all_events.append({
                    "Espaço": current_espaco, "Data": current_data, "Horário": h,
                    "Tema": "🔓 HORÁRIO VAGO" if is_vago else str(tema).strip(),
                    "Secretaria": str(sec).strip() if not is_vago else "",
                    "Responsável": str(resp).strip() if not is_vago else ""
                })
        return merge_consecutive_events(pd.DataFrame(all_events))
    except Exception as e:
        st.error(f"Erro: {e}")
        return pd.DataFrame()

def commit_changes_to_github(updated_df, change_log_notes=""):
    if not GITHUB_TOKEN: return False
    try:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            for space_name, group in updated_df.groupby("Espaço"):
                group.to_excel(writer, sheet_name=str(space_name)[:31], index=False)
        excel_buffer.seek(0)
        excel_b64 = base64.b64encode(excel_buffer.read()).decode("utf-8")
        encoded_filename = urllib.parse.quote(FILE_EXCEL_PATH)
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{encoded_filename}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        res = requests.get(url, headers=headers)
        sha = res.json().get("sha", "") if res.status_code == 200 else ""
        data = {"message": f"Update {datetime.datetime.now()}", "content": excel_b64, "branch": "main"}
        if sha: data["sha"] = sha
        requests.put(url, headers=headers, data=json.dumps(data))
        return True
    except: return False

# --- UI E ESTILIZAÇÃO ---

img_b64_bg = ""
try:
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(URL_RAW_IMG, headers=headers)
    with urllib.request.urlopen(req) as resp:
        img_b64_bg = base64.b64encode(resp.read()).decode("utf-8")
except: pass

st.markdown(f"""
<style>
    .stApp {{
        background: linear-gradient(rgba(15, 23, 42, 0.7), rgba(15, 23, 42, 0.7)), url("data:image/jpeg;base64,{img_b64_bg}") no-repeat center center fixed;
        background-size: cover;
    }}
    .metric-card {{
        background: rgba(255, 255, 255, 0.1);
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #15803d;
        color: white;
    }}
    .event-card {{
        background: white;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 10px;
        border-left: 5px solid #15803d;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }}
</style>
""", unsafe_allow_html=True)

# --- LÓGICA PRINCIPAL ---

df_raw = load_excel_from_github()

with st.sidebar:
    st.title("🔍 Filtros")
    busca = st.text_input("Palavra-chave", placeholder="Ex: Painel, Reunião...")
    dias_sel = st.multiselect("Filtrar Dias", ORDEM_DIAS)
    espacos = sorted(df_raw["Espaço"].unique()) if not df_raw.empty else []
    espacos_sel = st.multiselect("Filtrar Espaços", espacos)
    
    st.divider()
    if st.button("🔄 Atualizar Dados"):
        st.cache_data.clear()
        st.rerun()

# Dashboard de métricas
if not df_raw.empty:
    st.markdown("<h1 style='color:white; text-align:center;'>🌾 EXPOINTER 2026</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#facc15; text-align:center; font-weight:bold;'>AGENDA INSTITUCIONAL - ESPAÇOS GOV RS</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    total_ev = len(df_raw[df_raw["Tema"] != "🔓 HORÁRIO VAGO"])
    vagos = len(df_raw[df_raw["Tema"] == "🔓 HORÁRIO VAGO"])
    
    with col1: st.markdown(f'<div class="metric-card"><b>Eventos:</b><br><span style="font-size:20px;">{total_ev}</span></div>', unsafe_allow_html=True)
    with col2: st.markdown(f'<div class="metric-card"><b>Horários Livres:</b><br><span style="font-size:20px;">{vagos}</span></div>', unsafe_allow_html=True)
    with col3: st.markdown(f'<div class="metric-card"><b>Data:</b><br><span style="font-size:15px;">{datetime.datetime.now().strftime("%d/%m/%Y")}</span></div>', unsafe_allow_html=True)

    # Filtros aplicados
    df_f = df_raw.copy()
    if busca:
        df_f = df_f[df_f.apply(lambda row: busca.lower() in row.astype(str).str.lower().values, axis=1)]
    if dias_sel:
        df_f = df_f[df_f["Data"].isin(dias_sel)]
    if espacos_sel:
        df_f = df_f[df_f["Espaço"].isin(espacos_sel)]

    tab1, tab2, tab3 = st.tabs(["📅 Agenda", "🔓 Vagos", "🔒 Admin"])

    with tab1:
        if df_f.empty:
            st.info("Nenhum evento encontrado.")
        else:
            for dia in [d for d in ORDEM_DIAS if d in df_f["Data"].unique()]:
                st.subheader(f"🗓️ {dia}")
                evs = df_f[(df_f["Data"] == dia) & (df_f["Tema"] != "🔓 HORÁRIO VAGO")]
                cols = st.columns(3)
                for i, (_, row) in enumerate(evs.iterrows()):
                    with cols[i % 3]:
                        st.markdown(f"""
                        <div class="event-card">
                            <b style="color:#15803d;">⏰ {row['Horário']}</b><br>
                            <span style="font-weight:bold; color:#1e293b;">{row['Tema']}</span><br>
                            <small>📍 {row['Espaço']}</small><br>
                            <small>🏢 {row['Secretaria']}</small>
                        </div>
                        """, unsafe_allow_html=True)

    with tab2:
        vagos_f = df_f[df_f["Tema"] == "🔓 HORÁRIO VAGO"]
        st.dataframe(vagos_f[["Data", "Horário", "Espaço"]], use_container_width=True, hide_index=True)

    with tab3:
        senha = st.text_input("Senha", type="password")
        if senha == "expointer2026":
            st.success("Acesso Liberado")
            edited = st.data_editor(df_raw, use_container_width=True, num_rows="dynamic")
            if st.button("💾 Salvar no GitHub"):
                if commit_changes_to_github(edited):
                    st.success("Salvo!")
                    st.cache_data.clear()
                    st.rerun()
else:
    st.error("Não foi possível carregar os dados.")
