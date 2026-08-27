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

# 1. Configuração Inicial da Página
st.set_page_config(
    page_title="EXPOINTER 2026 — Agenda Institucional",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

GITHUB_REPO = st.secrets.get("GITHUB_REPO", "rapharamone1987/DP")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
FILE_EXCEL_PATH = "Grade Expointer 2026.xlsx"

URL_RAW_IMG = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/Screenshot_20260825-095320~2.jpg"

ORDEM_DIAS = [
    "Sábado 29/08",
    "Domingo 30/08",
    "Segunda 31/08",
    "Terça 01/09",
    "Quarta 02/09",
    "Quinta 03/09",
    "Sexta 04/09",
    "Sábado 05/09",
    "Domingo 06/09",
]

MAPA_RECONHECIMENTO_DIAS = {
    "29/08": "Sábado 29/08",
    "sabado 29": "Sábado 29/08",
    "sábado 29": "Sábado 29/08",
    "30/08": "Domingo 30/08",
    "domingo 30": "Domingo 30/08",
    "31/08": "Segunda 31/08",
    "segunda 31": "Segunda 31/08",
    "segunda": "Segunda 31/08",
    "01/09": "Terça 01/09",
    "terca 01": "Terça 01/09",
    "terça 01": "Terça 01/09",
    "terca": "Terça 01/09",
    "terça": "Terça 01/09",
    "02/09": "Quarta 02/09",
    "quarta 02": "Quarta 02/09",
    "quarta": "Quarta 02/09",
    "03/09": "Quinta 03/09",
    "quinta 03": "Quinta 03/09",
    "quinta": "Quinta 03/09",
    "04/09": "Sexta 04/09",
    "sexta 04": "Sexta 04/09",
    "sexta": "Sexta 04/09",
    "05/09": "Sábado 05/09",
    "sabado 05": "Sábado 05/09",
    "sábado 05": "Sábado 05/09",
    "06/09": "Domingo 06/09",
    "domingo 06": "Domingo 06/09",
}

TERMOS_IGNORAR = [
    "características do espaço",
    "caracteristicas do espaço",
    "lugares",
    "telão",
    "som",
    "paz no campo",
    "pavilhão",
    "pavilhão internacional",
    "estande de governo",
    "horário",
    "horario",
    "secretaria",
    "responsável",
    "responsavel",
    "tema",
    "atividade",
    "espaço",
    "local",
    "agenda auditório administração",
    "agenda auditório espaço gov",
    "agenda arena espaço gov",
    "agenda bancada espaço gov",
]

def map_sheet_to_space(sheet_name):
    s = sheet_name.strip().lower()
    if "admin" in s:
        return "Auditório Administração"
    elif "bancada" in s:
        return "Bancada Espaço Gov"
    elif "arena" in s:
        return "Arena Espaço Gov"
    elif "audit" in s or "gov" in s:
        return "Auditório Espaço Gov"
    
    clean = re.sub(r"^(agenda\s+)?(auditório\s+|arena\s+|bancada\s+)?", "", sheet_name, flags=re.IGNORECASE).strip()
    return clean.title() if clean else sheet_name

def detect_day_from_line(line_str):
    s = line_str.lower()
    for key, mapped_day in MAPA_RECONHECIMENTO_DIAS.items():
        if key in s:
            if "sabado" in key or "sábado" in key:
                if "05" in s or "5" in s:
                    return "Sábado 05/09"
                return "Sábado 29/08"
            if "domingo" in key:
                if "06" in s or "6" in s:
                    return "Domingo 06/09"
                return "Domingo 30/08"
            return mapped_day
    return None

@st.cache_data(ttl=3600)
def load_background_base64(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            return base64.b64encode(resp.read()).decode("utf-8")
    except Exception:
        return ""

img_b64 = load_background_base64(URL_RAW_IMG)

def clean_time_string(time_str):
    if not time_str or pd.isna(time_str):
        return ""
    s = str(time_str).strip()
    matches = re.findall(r" (?:[01]?\d|2[0-3])[:h][0-5]\d ", s)
    if matches:
        formatted = [
            m.replace("h", ":")
            if "h" in m
            else (f"0{m}" if len(m) == 4 and m[1] == ":" else m)
            for m in matches
        ]
        if len(formatted) >= 2:
            return f"{formatted[0]} - {formatted[1]}"
        return formatted[0]
    return s

def extract_start_time(horario_str):
    if not horario_str:
        return "99:99"
    match = re.search(r" (?:[01]?\d|2[0-3]):[0-5]\d ", str(horario_str))
    if match:
        time_val = match.group(0)
        return time_val if len(time_val) == 5 else f"0{time_val}"
    return "99:99"

def extract_end_time(horario_str):
    if not horario_str:
        return ""
    matches = re.findall(r" (?:[01]?\d|2[0-3]):[0-5]\d ", str(horario_str))
    if len(matches) >= 2:
        return matches[1]
    elif len(matches) == 1:
        h, m = map(int, matches[0].split(":"))
        return f"{(h + 1) % 24:02d}:{m:02d}"
    return ""

def merge_consecutive_events(df):
    if df.empty:
        return df

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
                same_resp = current_event["Responsável"] == row["Responsável"]

                if (
                    same_theme
                    and same_sec
                    and same_resp
                    and row["Tema"] != "🔓 HORÁRIO VAGO"
                ):
                    new_end = extract_end_time(row["Horário"])
                    if new_end:
                        current_event["Hora_Fim"] = new_end
                else:
                    if current_event["Hora_Inicio"] and current_event["Hora_Fim"]:
                        current_event["Horário"] = (
                            f"{current_event['Hora_Inicio']} -"
                            f" {current_event['Hora_Fim']}"
                        )
                    merged_rows.append(current_event)

                    current_event = dict(row)
                    current_event["Hora_Inicio"] = extract_start_time(row["Horário"])
                    current_event["Hora_Fim"] = extract_end_time(row["Horário"])

        if current_event:
            if current_event["Hora_Inicio"] and current_event["Hora_Fim"]:
                current_event["Horário"] = (
                    f"{current_event['Hora_Inicio']} - {current_event['Hora_Fim']}"
                )
            merged_rows.append(current_event)

    res_df = pd.DataFrame(merged_rows)
    cols_to_drop = [
        c for c in ["Hora_Start", "Hora_Inicio", "Hora_Fim"] if c in res_df.columns
    ]
    return res_df.drop(columns=cols_to_drop)

@st.cache_data(ttl=15)
def load_excel_from_github():
    try:
        encoded_path = urllib.parse.quote(FILE_EXCEL_PATH)
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{encoded_path}"

        headers = {"Accept": "application/vnd.github.v3+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        res = requests.get(api_url, headers=headers)

        if res.status_code == 200:
            content_b64 = res.json().get("content", "")
            content_bytes = base64.b64decode(content_b64)
            excel_file = pd.ExcelFile(io.BytesIO(content_bytes), engine="openpyxl")
        else:
            raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{encoded_path}"
            raw_req = urllib.request.Request(
                raw_url,
                headers={
                    "Authorization": f"token {GITHUB_TOKEN}"
                    if GITHUB_TOKEN
                    else ""
                },
            )
            with urllib.request.urlopen(raw_req) as resp:
                excel_file = pd.ExcelFile(io.BytesIO(resp.read()), engine="openpyxl")

        all_events = []

        for sheet_name in excel_file.sheet_names:
            if "escala" in sheet_name.lower() or "equipe" in sheet_name.lower():
                continue

            # Mapeamento do espaço FIXO pelo nome da aba
            sheet_espaco = map_sheet_to_space(sheet_name)

            df_sheet = excel_file.parse(sheet_name, header=None)
            if df_sheet.empty:
                continue

            df_sheet = df_sheet.fillna("").astype(str)
            current_data = "Sábado 29/08"

            for idx, row in df_sheet.iterrows():
                row_vals = [str(v).strip() for v in row.values if str(v).strip() != ""]
                if not row_vals:
                    continue

                line_str = " ".join(row_vals)
                line_lower = line_str.lower()

                # Ignora linhas institucionais e cabeçalhos repetidos
                if any(term in line_lower for term in TERMOS_IGNORAR):
                    continue

                detected_day = detect_day_from_line(line_str)
                if detected_day:
                    current_data = detected_day
                    continue

                col0 = str(row.values[0]).strip() if len(row.values) > 0 else ""
                col1 = str(row.values[1]).strip() if len(row.values) > 1 else ""
                col2 = str(row.values[2]).strip() if len(row.values) > 2 else ""
                col3 = str(row.values[3]).strip() if len(row.values) > 3 else ""

                horario_limpo = clean_time_string(col0)
                if horario_limpo:
                    tema = col1
                    sec = col2
                    resp = col3
                else:
                    alt_horario = clean_time_string(col1)
                    if alt_horario:
                        horario_limpo = alt_horario
                        tema = col2
                        sec = col3
                        resp = str(row.values[4]).strip() if len(row.values) > 4 else ""
                    else:
                        continue

                tema_clean = tema.strip()
                is_vago = (
                    not tema_clean
                    or tema_clean.lower()
                    in [
                        "livre",
                        "vago",
                        "disponível",
                        "disponivel",
                        "horário vago",
                        "horario vago",
                        "nan",
                        "none",
                        "",
                        "-",
                        "--",
                    ]
                    or tema_clean.startswith("🔓")
                )

                all_events.append({
                    "Espaço": sheet_espaco,
                    "Data": current_data,
                    "Horário": horario_limpo,
                    "Tema": "🔓 HORÁRIO VAGO" if is_vago else tema_clean,
                    "Secretaria": sec.strip() if not is_vago else "",
                    "Responsável": resp.strip() if not is_vago else "",
                })

        df_raw = pd.DataFrame(all_events)
        return merge_consecutive_events(df_raw)

    except Exception as e:
        st.error(f"⚠️ Erro ao carregar planilha do GitHub: {e}")
        return pd.DataFrame()

def commit_changes_to_github(updated_df, change_log_notes=""):
    if not GITHUB_TOKEN:
        st.error("❌ GITHUB_TOKEN não configurado no Secrets do Streamlit Cloud.")
        return False

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            for space_name, group in updated_df.groupby("Espaço"):
                sheet_title = re.sub(r"[\\/*?:\[\]]", "_", f"Agenda {space_name}")[:31]
                group.to_excel(writer, sheet_name=sheet_title, index=False)

        excel_buffer.seek(0)
        excel_b64 = base64.b64encode(excel_buffer.read()).decode("utf-8")

        encoded_filename = urllib.parse.quote(FILE_EXCEL_PATH)
        get_file_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{encoded_filename}"
        res = requests.get(get_file_url, headers=headers)
        sha = res.json().get("sha", "") if res.status_code == 200 else ""

        update_data = {
            "message": f"Atualização da grade de eventos ({timestamp})",
            "content": excel_b64,
            "branch": "main",
        }
        if sha:
            update_data["sha"] = sha

        requests.put(get_file_url, headers=headers, data=json.dumps(update_data))

        log_content = {
            "data_alteracao": timestamp,
            "observacoes": change_log_notes,
            "total_eventos": len(updated_df),
            "eventos": updated_df.to_dict(orient="records"),
        }
        log_b64 = base64.b64encode(
            json.dumps(log_content, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("utf-8")

        log_file_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/historico_alteracoes/alteracao_{timestamp}.json"
        log_data = {
            "message": f"Registro de histórico de alteração ({timestamp})",
            "content": log_b64,
            "branch": "main",
        }
        requests.put(log_file_url, headers=headers, data=json.dumps(log_data))

        return True

    except Exception as e:
        st.error(f"⚠️ Erro no commit para o GitHub: {e}")
        return False

def generate_pdf_report(df_export, doc_title_info):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#064e3b"),
        fontName="Helvetica-Bold",
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#15803d"),
        fontName="Helvetica-Bold",
        spaceAfter=15,
    )
    cell_header_style = ParagraphStyle(
        "CellHeader",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        alignment=1,
    )
    cell_time_style = ParagraphStyle(
        "CellTime",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#15803d"),
        fontName="Helvetica-Bold",
    )
    cell_title_style = ParagraphStyle(
        "CellTitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#0f172a"),
        fontName="Helvetica-Bold",
        leading=11,
    )
    cell_meta_style = ParagraphStyle(
        "CellMeta",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#475569"),
        fontName="Helvetica",
    )

    elements.append(
        Paragraph(
            "EXPOINTER 2026 — Programação Institucional - Espaços Gov RS",
            title_style,
        )
    )
    elements.append(
        Paragraph(f"Filtro do Relatório: <b>{doc_title_info}</b>", subtitle_style)
    )

    table_data = [[
        Paragraph("Data", cell_header_style),
        Paragraph("Horário", cell_header_style),
        Paragraph("Espaço / Auditório", cell_header_style),
        Paragraph("Atividade / Tema", cell_header_style),
        Paragraph("Organização / Responsável", cell_header_style),
    ]]

    for _, row in df_export.iterrows():
        resp_str = f" ({row['Responsável']})" if row["Responsável"] else ""
        org_resp = (
            f"{row['Secretaria']}{resp_str}"
            if row["Secretaria"]
            else row["Responsável"]
        )
        table_data.append([
            Paragraph(f"<b>{row['Data']}</b>", cell_meta_style),
            Paragraph(row["Horário"], cell_time_style),
            Paragraph(row["Espaço"], cell_meta_style),
            Paragraph(row["Tema"], cell_title_style),
            Paragraph(org_resp if org_resp else "-", cell_meta_style),
        ])

    t = Table(table_data, colWidths=[90, 80, 130, 320, 160], repeatRows=1)
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#064e3b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [colors.white, colors.HexColor("#f8fafc")],
            ),
        ])
    )
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ESTILIZAÇÃO CSS
bg_url_css = f"data:image/jpeg;base64,{img_b64}" if img_b64 else ""

custom_css = f"""
<style>
    .stApp {{
        background: linear-gradient(rgba(15, 23, 42, 0.40), rgba(15, 23, 42, 0.40)), url("{bg_url_css}") no-repeat center center fixed !important;
        background-size: cover !important;
        font-family: 'Segoe UI', system-ui, sans-serif !important;
    }}

    .rs-banner-card {{
        background: linear-gradient(135deg, rgba(11, 102, 35, 0.88) 0%, rgba(21, 128, 61, 0.85) 35%, rgba(185, 28, 28, 0.85) 68%, rgba(234, 179, 8, 0.88) 100%) !important;
        border-radius: 16px;
        padding: 38px 20px;
        text-align: center;
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.65);
        margin-bottom: 26px;
        border-bottom: 6px solid #facc15;
        position: relative;
    }}

    .rs-banner-title {{
        font-size: 2.2rem !important;
        font-weight: 900 !important;
        color: #ffffff !important;
        margin: 0 !important;
        text-shadow: 0 3px 8px rgba(0, 0, 0, 0.95);
        letter-spacing: 0.5px;
    }}

    .cal-header {{
        background-color: #064e3b !important;
        color: #ffffff !important;
        text-align: center;
        padding: 12px 6px;
        font-weight: 800;
        border-radius: 8px;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.4);
        font-size: 0.9rem;
        border: 1px solid #15803d;
    }}

    .cal-event-box {{
        background-color: rgba(255, 255, 255, 0.96) !important;
        border: 1px solid #cbd5e1 !important;
        border-left: 6px solid #15803d !important;
        padding: 12px;
        margin-bottom: 12px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.25);
    }}

    .cal-event-box span {{
        color: #15803d !important;
        font-weight: 800 !important;
        display: block;
        margin-bottom: 4px;
        text-shadow: none !important;
    }}

    .event-card-vago {{
        background-color: rgba(255, 255, 255, 0.96) !important;
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 12px;
        border-left: 6px solid #15803d !important;
        border: 1px dashed #16a34a;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.25);
    }}

    .card-time-vago {{
        color: #15803d !important;
        font-weight: 900 !important;
        font-size: 0.9rem !important;
        display: block !important;
        margin-bottom: 6px !important;
        text-shadow: none !important;
    }}

    div[data-baseweb="select"] > div, input {{
        background-color: rgba(255, 255, 255, 0.95) !important;
        color: #0f172a !important;
        border-radius: 8px !important;
    }}

    label, .stSelectbox label, .stMultiSelect label, .stTextInput label, div[data-testid="stMarkdownContainer"] p {{
        color: #ffffff !important;
        font-weight: 800 !important;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.9);
    }}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# Carregamento dos dados
df_data = load_excel_from_github()

banner_html = """
<div class="rs-banner-card">
    <div class="rs-banner-title">EXPOINTER 2026 — Programação Institucional - Espaços Gov RS</div>
</div>
"""
st.markdown(banner_html, unsafe_allow_html=True)

if df_data.empty:
    st.stop()

# Filtros Globais
dias_encontrados = [d for d in df_data["Data"].unique() if d]
todos_dias = [
    d for d in ORDEM_DIAS if d in dias_encontrados
] + [d for d in dias_encontrados if d not in ORDEM_DIAS]
todos_espacos = sorted([e for e in df_data["Espaço"].unique() if e])
todas_sec = sorted([
    s
    for s in df_data["Secretaria"].unique()
    if s and str(s).strip() != "🔓 HORÁRIO VAGO"
])

st.markdown("### 🔍 Pesquisar e Filtrar Programação")
with st.container():
    col_busca, col_dias = st.columns([2, 2])
    with col_busca:
        busca = st.text_input(
            "🔎 Palavra-chave:", "", placeholder="Digite um tema ou termo..."
        )
    with col_dias:
        dias_sel = st.multiselect(
            "📅 Filtrar por Dia(s):",
            todos_dias,
            default=[],
            placeholder="Selecione os dias...",
        )

    col_espaco, col_sec = st.columns(2)
    with col_espaco:
        espacos_sel = st.multiselect(
            "📍 Filtrar por Espaço / Auditório:",
            todos_espacos,
            default=[],
            placeholder="Selecione os locais...",
        )
    with col_sec:
        sec_sel = st.multiselect(
            "🏢 Filtrar por Secretaria / Entidade:",
            todas_sec,
            default=[],
            placeholder="Selecione as entidades...",
        )

df_filtered = df_data.copy()

if busca:
    t = busca.lower()
    df_filtered = df_filtered[
        df_filtered["Tema"].astype(str).str.lower().str.contains(t)
        | df_filtered["Espaço"].astype(str).str.lower().str.contains(t)
        | df_filtered["Responsável"].astype(str).str.lower().str.contains(t)
    ]
if dias_sel:
    df_filtered = df_filtered[df_filtered["Data"].isin(dias_sel)]
if espacos_sel:
    df_filtered = df_filtered[df_filtered["Espaço"].isin(espacos_sel)]
if sec_sel:
    df_filtered = df_filtered[df_filtered["Secretaria"].isin(sec_sel)]

# Ordenação Cronológica
df_filtered["Hora_Sort"] = df_filtered["Horário"].apply(extract_start_time)
df_filtered["Data_Cat"] = pd.Categorical(
    df_filtered["Data"], categories=ORDEM_DIAS, ordered=True
)
df_filtered = df_filtered.sort_values(
    by=["Data_Cat", "Hora_Sort"]
).drop(columns=["Data_Cat", "Hora_Sort"])

df_agendados = df_filtered[df_filtered["Tema"] != "🔓 HORÁRIO VAGO"]
df_vagos_totais = df_filtered[df_filtered["Tema"] == "🔓 HORÁRIO VAGO"]

# Sidebar
st.sidebar.header("📄 Exportação & Gestão")
if st.sidebar.button("⚙️ Gerar Relatório PDF"):
    if not df_agendados.empty:
        info_str = "Seleção Personalizada"
        if espacos_sel:
            info_str = f"Espaços: {', '.join(espacos_sel)}"
        elif dias_sel:
            info_str = f"Dias: {', '.join(dias_sel)}"
        pdf_bytes = generate_pdf_report(df_agendados, info_str)
        st.sidebar.download_button(
            label="📥 Baixar PDF da Programação",
            data=pdf_bytes,
            file_name="agenda_expointer.pdf",
            mime="application/pdf",
        )
    else:
        st.sidebar.error("Nenhum evento agendado selecionado.")

st.sidebar.divider()

# Abas
tab_calendar, tab_vagos, tab_edit = st.tabs([
    "📅 Visão Calendário",
    "🔓 Horários Livres / Vagos",
    "🔒 Edição & Versionamento",
])

# ABA 1: CALENDÁRIO
with tab_calendar:
    dia_grid_sel = st.selectbox(
        "📆 Destacar dia na grade:",
        ["Exibir Todos Selecionados"] + todos_dias,
        index=0,
    )
    df_grid = df_agendados.copy()
    if dia_grid_sel != "Exibir Todos Selecionados":
        df_grid = df_grid[df_grid["Data"] == dia_grid_sel]

    if df_grid.empty:
        st.info("Nenhum evento agendado para exibir nesta visão.")
    else:
        dias_unicos = [d for d in ORDEM_DIAS if d in df_grid["Data"].unique()]

        if len(dias_unicos) == 0:
            st.info("Nenhum dia correspondente para os filtros selecionados.")
        else:
            grid_cols = st.columns(len(dias_unicos))
            for idx, d in enumerate(dias_unicos):
                with grid_cols[idx]:
                    st.markdown(
                        f'<div class="cal-header">📅 {d}</div>', unsafe_allow_html=True
                    )
                    evs_dia = df_grid[df_grid["Data"] == d]
                    for _, ev in evs_dia.iterrows():
                        sec_val = (
                            str(ev["Secretaria"]).strip()
                            if pd.notna(ev["Secretaria"])
                            else ""
                        )
                        resp_val = (
                            str(ev["Responsável"]).strip()
                            if pd.notna(ev["Responsável"])
                            else ""
                        )

                        sec_display = (
                            f'<div style="color:#334155; font-size:0.75rem;'
                            f' font-weight:600; margin-top:4px;">🏢 {sec_val}</div>'
                            if sec_val and sec_val.lower() not in ["nan", "none", ""]
                            else ""
                        )
                        resp_display = (
                            f'<div style="color:#475569; font-size:0.75rem;'
                            f' font-weight:500;">👤 {resp_val}</div>'
                            if resp_val and resp_val.lower() not in ["nan", "none", ""]
                            else ""
                        )

                        st.markdown(
                            f"""
                            <div class="cal-event-box">
                                <span>⏰ {ev['Horário']}</span>
                                <div style="font-weight:700; color:#0f172a; margin-bottom:4px;">{ev['Tema']}</div>
                                <div style="color:#0369a1; font-weight:700; font-size:0.8rem;">📍 {ev['Espaço']}</div>
                                {sec_display}
                                {resp_display}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

# ABA 2: HORÁRIOS LIVRES / VAGOS
with tab_vagos:
    st.markdown("### 🔓 Consulta de Horários Livres para Agendamento")
    if df_vagos_totais.empty:
        st.success("🎉 Todos os espaços estão ocupados para o filtro selecionado!")
    else:
        st.metric("Total de Horários Disponíveis", len(df_vagos_totais))
        for data, grupo in df_vagos_totais.groupby("Data", sort=False):
            st.markdown(f"#### 📅 {data}")
            cols_vago = st.columns(3)
            for idx, (_, row) in enumerate(grupo.iterrows()):
                vago_html = f"""
                <div class="event-card-vago">
                    <span class="card-time-vago">⏰ {row['Horário']}</span>
                    <div style="font-weight:800; font-size:0.95rem; color:#b45309; margin-top:4px;">🔓 HORÁRIO DISPONÍVEL</div>
                    <div style="color:#0369a1; font-weight:800; font-size:0.88rem; margin-top:2px;">📍 {row['Espaço']}</div>
                </div>
                """
                cols_vago[idx % 3].markdown(vago_html, unsafe_allow_html=True)

# ABA 3: EDIÇÃO COM VERSIONAMENTO
with tab_edit:
    st.markdown("### 🔒 Edição & Versionamento Automático")
    senha = st.text_input("Digite a senha de administrador:", type="password")

    if senha == "expointer2026":
        st.success(
            "🔓 Acesso liberado! Edite os dados na tabela e registre a alteração."
        )

        notes = st.text_input(
            "Motivo / Descrição da Alteração (Auditoria):",
            placeholder="Ex: Ajuste no horário do painel SEDUC",
        )

        edited_df = st.data_editor(
            df_data,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Espaço": st.column_config.SelectboxColumn(
                    "Espaço / Local", options=todos_espacos, required=True
                ),
                "Data": st.column_config.SelectboxColumn(
                    "Dia", options=ORDEM_DIAS, required=True
                ),
                "Horário": st.column_config.TextColumn("Horário", required=True),
                "Tema": st.column_config.TextColumn(
                    "Atividade / Tema", required=True
                ),
                "Secretaria": st.column_config.TextColumn("Secretaria / Entidade"),
                "Responsável": st.column_config.TextColumn("Responsável"),
            },
            key="editor_github",
        )

        if st.button("💾 Salvar & Registrar Versão no GitHub"):
            with st.spinner("Enviando alterações e registrando histórico..."):
                if commit_changes_to_github(edited_df, notes):
                    st.success(
                        "✅ Planilha atualizada e novo arquivo de histórico registrado"
                        " no GitHub!"
                    )
                    st.cache_data.clear()
                    st.rerun()

    elif senha:
        st.error("❌ Senha incorreta.")
