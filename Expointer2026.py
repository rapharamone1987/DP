import base64
import datetime
import io
import json
import re
import urllib.parse
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
# Mova a senha real para Streamlit Secrets: ADMIN_PASSWORD
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "expointer2026")
if ADMIN_PASSWORD == "expointer2026":
    st.warning("Usando senha admin padrão embutida. Considere configurar ADMIN_PASSWORD em st.secrets.")

FILE_CSV_PATH = "Grade Expointer 2026.csv"

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

MAPA_DIAS = {
    "29/08": "Sábado 29/08",
    "30/08": "Domingo 30/08",
    "31/08": "Segunda 31/08",
    "01/09": "Terça 01/09",
    "02/09": "Quarta 02/09",
    "03/09": "Quinta 03/09",
    "04/09": "Sexta 04/09",
    "05/09": "Sábado 05/09",
    "06/09": "Domingo 06/09",
}


@st.cache_data(ttl=3600)
def load_background_base64(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        # Para raw.githubusercontent em repositório público a Authorization não é necessária,
        # mas caso seja privado, a API de conteúdos deve ser usada; mantemos a possibilidade:
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"
        resp = requests.get(url, headers=headers, timeout=10)
        if not resp.ok:
            return ""
        return base64.b64encode(resp.content).decode("utf-8")
    except Exception:
        return ""


img_b64 = load_background_base64(URL_RAW_IMG)


def clean_time_string(time_str):
    if not time_str or pd.isna(time_str):
        return ""
    s = str(time_str).strip()
    matches = re.findall(r"\b(?:[01]?\d|2[0-3])[:h][0-5]\d\b", s)
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
    match = re.search(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b", str(horario_str))
    if match:
        time_val = match.group(0)
        return time_val if len(time_val) == 5 else f"0{time_val}"
    return "99:99"


def extract_end_time(horario_str):
    if not horario_str:
        return ""
    matches = re.findall(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b", str(horario_str))
    if len(matches) >= 2:
        return matches[1]
    elif len(matches) == 1:
        try:
            h, m = map(int, matches[0].split(":"))
            return f"{(h + 1) % 24:02d}:{m:02d}"
        except Exception:
            return ""
    return ""


def detect_space_from_string(text):
    if not text:
        return None
    t = str(text).lower()
    if "admin" in t:
        return "Auditório Administração"
    elif "bancada" in t:
        return "Bancada Espaço Gov"
    elif "arena" in t:
        return "Arena Espaço Gov"
    elif "audit" in t or "espaço gov" in t or "espaco gov" in t:
        return "Auditório Espaço Gov"
    return None


def detect_day_from_string(text):
    if not text:
        return None
    t = str(text).lower()
    for key, full_day in MAPA_DIAS.items():
        if key in t:
            return full_day
    for d in ORDEM_DIAS:
        if d.lower() in t:
            return d
    return None


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
                same_theme = current_event.get("Tema") == row.get("Tema")
                same_sec = current_event.get("Secretaria") == row.get("Secretaria")
                same_resp = current_event.get("Responsável") == row.get("Responsável")

                if (
                    same_theme
                    and same_sec
                    and same_resp
                    and row.get("Tema") != "🔓 HORÁRIO VAGO"
                ):
                    new_end = extract_end_time(row["Horário"])
                    if new_end:
                        current_event["Hora_Fim"] = new_end
                else:
                    if current_event.get("Hora_Inicio") and current_event.get("Hora_Fim"):
                        current_event["Horário"] = (
                            f"{current_event['Hora_Inicio']} -"
                            f" {current_event['Hora_Fim']}"
                        )
                    merged_rows.append(current_event)

                    current_event = dict(row)
                    current_event["Hora_Inicio"] = extract_start_time(row["Horário"])
                    current_event["Hora_Fim"] = extract_end_time(row["Horário"])

        if current_event:
            if current_event.get("Hora_Inicio") and current_event.get("Hora_Fim"):
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
def load_csv_from_github():
    try:
        encoded_path = urllib.parse.quote(FILE_CSV_PATH)
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{encoded_path}"

        headers = {"Accept": "application/vnd.github.v3+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        res = requests.get(api_url, headers=headers, timeout=15)
        if not res.ok:
            st.error(
                f"⚠️ Erro HTTP {res.status_code} ao buscar '{FILE_CSV_PATH}' no GitHub: {res.text}"
            )
            return pd.DataFrame()

        content_b64 = res.json().get("content", "")
        if not content_b64:
            st.error("⚠️ Conteúdo do arquivo vazio no GitHub.")
            return pd.DataFrame()

        content_bytes = base64.b64decode(content_b64)

        df_raw = None
        for enc in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
            for sep in [";", ",", "\t"]:
                try:
                    temp_df = pd.read_csv(
                        io.BytesIO(content_bytes),
                        sep=sep,
                        encoding=enc,
                        dtype=str,
                        header=None,
                    )
                    if temp_df.shape[1] >= 2:
                        df_raw = temp_df
                        break
                except Exception:
                    continue
            if df_raw is not None:
                break

        if df_raw is None or df_raw.empty:
            st.error("⚠️ O arquivo CSV está vazio ou não pôde ser lido.")
            return pd.DataFrame()

        df_raw = df_raw.fillna("").astype(str)

        # Estado de rastreamento dinamico para linhas de contexto
        current_space = "Auditório Espaço Gov"
        current_day = "Sábado 29/08"

        eventos = []

        for _, row in df_raw.iterrows():
            # Preserve original column positions (não remover células vazias)
            row_list = [str(v).strip() if pd.notna(v) else "" for v in row.values]

            # Se a linha está totalmente vazia, ignora
            if all((not x or x.lower() == "nan") for x in row_list):
                continue

            # Linha combinada sem células vazias apenas para detecção de espaço/dia
            full_line = " ".join([x for x in row_list if x and x.lower() != "nan"])

            # 1. Verifica se a linha indica mudança de Espaço/Local
            found_space = detect_space_from_string(full_line)
            # Considera mudança de espaço apenas quando a primeira coluna não tem horário e a linha é curta
            if found_space and not clean_time_string(row_list[0]) and sum(1 for x in row_list if x and x.lower() != "nan") <= 2:
                current_space = found_space
                continue

            # 2. Verifica se a linha indica mudança de Data/Dia
            found_day = detect_day_from_string(full_line)
            if found_day and not clean_time_string(row_list[0]) and sum(1 for x in row_list if x and x.lower() != "nan") <= 2:
                current_day = found_day
                continue

            # 3. Descobre em qual coluna está o Horário (sem colapsar colunas)
            idx_h = -1
            horario_limpo = ""
            for idx, val in enumerate(row_list):
                if not val or val.lower() == "nan":
                    continue
                h = clean_time_string(val)
                if h and val.lower() not in ["horario", "horário", "hora", "espaço", "data"]:
                    horario_limpo = h
                    idx_h = idx
                    break

            if idx_h == -1:
                # Não encontrou horário válido nessa linha
                continue

            # Extrai dados em relação ao índice da coluna de Horário, respeitando colunas vazias
            espaco = row_list[0] if (idx_h > 0 and detect_space_from_string(row_list[0])) else current_space
            data = row_list[1] if (idx_h > 1 and detect_day_from_string(row_list[1])) else current_day

            tema = row_list[idx_h + 1] if idx_h + 1 < len(row_list) else ""
            sec = row_list[idx_h + 2] if idx_h + 2 < len(row_list) else ""
            resp = row_list[idx_h + 3] if idx_h + 3 < len(row_list) else ""

            # Valida se a primeira coluna era o Espaço (mantendo compatibilidade)
            if detect_space_from_string(row_list[0]):
                espaco = detect_space_from_string(row_list[0])

            # Valida se alguma coluna da linha trazia o Dia explicitamente
            for v in row_list:
                d_found = detect_day_from_string(v)
                if d_found:
                    data = d_found
                    break

            is_vago = (
                not tema
                or tema.lower()
                in [
                    "livre",
                    "vago",
                    "disponível",
                    "disponivel",
                    "horário vago",
                    "nan",
                    "none",
                    "",
                    "-",
                ]
                or (isinstance(tema, str) and tema.startswith("🔓"))
            )

            eventos.append({
                "Espaço": espaco,
                "Data": data,
                "Horário": horario_limpo,
                "Tema": "🔓 HORÁRIO VAGO" if is_vago else tema,
                "Secretaria": sec if not is_vago else "",
                "Responsável": resp if not is_vago else "",
            })

        df_final = pd.DataFrame(eventos)
        if df_final.empty:
            st.error(
                "⚠️ O arquivo CSV foi lido, mas nenhuma linha com horário válido foi identificada."
            )
            return pd.DataFrame()

        return merge_consecutive_events(df_final)

    except Exception as e:
        st.error(f"⚠️ Erro ao processar o CSV do GitHub: {e}")
        return pd.DataFrame()


def commit_changes_to_github(updated_df, change_log_notes=""):
    if not GITHUB_TOKEN:
        st.error(
            "❌ GITHUB_TOKEN não configurado no Secrets do Streamlit Cloud."
        )
        return False

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        # Determina branch default do repositório
        repo_api = f"https://api.github.com/repos/{GITHUB_REPO}"
        repo_res = requests.get(repo_api, headers=headers, timeout=10)
        if repo_res.ok:
            default_branch = repo_res.json().get("default_branch", "main")
        else:
            default_branch = "main"
            st.warning("Aviso: não foi possível obter a branch padrão do repositório; usando 'main' como fallback.")

        csv_buffer = io.StringIO()
        updated_df.to_csv(csv_buffer, index=False, sep=";")
        csv_b64 = base64.b64encode(csv_buffer.getvalue().encode("utf-8")).decode("utf-8")

        encoded_filename = urllib.parse.quote(FILE_CSV_PATH)
        get_file_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{encoded_filename}"
        res = requests.get(get_file_url, headers=headers, timeout=10)

        sha = ""
        if res.ok:
            sha = res.json().get("sha", "")

        update_data = {
            "message": f"Atualização da grade CSV ({timestamp})",
            "content": csv_b64,
            "branch": default_branch,
        }
        if sha:
            update_data["sha"] = sha

        res_put = requests.put(get_file_url, headers=headers, json=update_data, timeout=15)
        if not res_put.ok:
            st.error(f"Falha ao atualizar '{FILE_CSV_PATH}' no GitHub: {res_put.status_code} - {res_put.text}")
            return False

        # Prepara registro de histórico (evita logs enormes)
        max_events_for_log = 2000
        eventos_for_log = updated_df.to_dict(orient="records")
        if len(eventos_for_log) > max_events_for_log:
            eventos_for_log = eventos_for_log[:1000]
            truncated_msg = f" (truncated: original {len(updated_df)} eventos)"
        else:
            truncated_msg = ""

        log_content = {
            "data_alteracao": timestamp,
            "observacoes": change_log_notes + truncated_msg,
            "total_eventos": len(updated_df),
            "eventos": eventos_for_log,
        }
        log_b64 = base64.b64encode(
            json.dumps(log_content, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("utf-8")

        log_file_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/historico_alteracoes/alteracao_{timestamp}.json"
        log_data = {
            "message": f"Registro de histórico de alteração ({timestamp})",
            "content": log_b64,
            "branch": default_branch,
        }
        res_log = requests.put(log_file_url, headers=headers, json=log_data, timeout=15)
        if not res_log.ok:
            st.warning(f"Aviso: falha ao criar registro de histórico: {res_log.status_code} - {res_log.text}")

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
            
