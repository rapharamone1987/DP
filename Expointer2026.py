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
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "expointer2026")

if ADMIN_PASSWORD == "expointer2026":
  st.warning(
      "Usando senha admin padrão embutida. Considere configurar ADMIN_PASSWORD"
      " em st.secrets."
  )

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
    api_url = (
        f"https://api.github.com/repos/{GITHUB_REPO}/contents/{encoded_path}"
    )

    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
      headers["Authorization"] = f"token {GITHUB_TOKEN}"

    res = requests.get(api_url, headers=headers, timeout=15)
    if not res.ok:
      st.error(
          f"⚠️ Erro HTTP {res.status_code} ao buscar '{FILE_CSV_PATH}' no"
          f" GitHub: {res.text}"
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

    current_space = "Auditório Espaço Gov"
    current_day = "Sábado 29/08"

    eventos = []

    for _, row in df_raw.iterrows():
      row_list = [str(v).strip() if pd.notna(v) else "" for v in row.values]

      if all((not x or x.lower() == "nan") for x in row_list):
        continue

      full_line = " ".join([x for x in row_list if x and x.lower() != "nan"])

      found_space = detect_space_from_string(full_line)
      if (
          found_space
          and not clean_time_string(row_list[0])
          and sum(1 for x in row_list if x and x.lower() != "nan") <= 2
      ):
        current_space = found_space
        continue

      found_day = detect_day_from_string(full_line)
      if (
          found_day
          and not clean_time_string(row_list[0])
          and sum(1 for x in row_list if x and x.lower() != "nan") <= 2
      ):
        current_day = found_day
        continue

      c_espaco = row_list[0] if len(row_list) > 0 else ""
      c_data = row_list[1] if len(row_list) > 1 else ""
      c_horario = row_list[2] if len(row_list) > 2 else ""
      c_tema = row_list[3] if len(row_list) > 3 else ""
      c_sec = row_list[4] if len(row_list) > 4 else ""
      c_resp = row_list[5] if len(row_list) > 5 else ""

      horario_limpo = clean_time_string(c_horario)

      if not horario_limpo and clean_time_string(c_espaco):
        horario_limpo = clean_time_string(c_espaco)
        c_tema = c_data
        c_sec = c_horario
        c_resp = c_tema
        c_espaco = current_space
        c_data = current_day

      if not horario_limpo:
        continue

      espaco_final = (
          detect_space_from_string(c_espaco) or c_espaco or current_space
      )
      data_final = detect_day_from_string(c_data) or c_data or current_day

      if c_tema.lower() in ["tema", "atividade", "evento", "descrição"]:
        continue

      is_vago = (
          not c_tema
          or c_tema.lower()
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
          or c_tema.startswith("🔓")
      )

      eventos.append({
          "Espaço": espaco_final,
          "Data": data_final,
          "Horário": horario_limpo,
          "Tema": "🔓 HORÁRIO VAGO" if is_vago else c_tema,
          "Secretaria": c_sec if not is_vago else "",
          "Responsável": c_resp if not is_vago else "",
      })

    df_final = pd.DataFrame(eventos)
    if df_final.empty:
      st.error(
          "⚠️ O arquivo CSV foi lido, mas nenhuma linha com horário válido foi"
          " identificada."
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
    repo_api = f"https://api.github.com/repos/{GITHUB_REPO}"
    repo_res = requests.get(repo_api, headers=headers, timeout=10)
    default_branch = (
        repo_res.json().get("default_branch", "main")
        if repo_res.ok
        else "main"
    )

    csv_buffer = io.StringIO()
    updated_df.to_csv(csv_buffer, index=False, sep=";")
    csv_b64 = base64.b64encode(csv_buffer.getvalue().encode("utf-8")).decode(
        "utf-8"
    )

    encoded_filename = urllib.parse.quote(FILE_CSV_PATH)
    get_file_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{encoded_filename}"
    res = requests.get(get_file_url, headers=headers, timeout=10)

    sha = res.json().get("sha", "") if res.ok else ""

    update_data = {
        "message": f"Atualização da grade CSV ({timestamp})",
        "content": csv_b64,
        "branch": default_branch,
    }
    if sha:
      update_data["sha"] = sha

    res_put = requests.put(
        get_file_url, headers=headers, json=update_data, timeout=15
    )
    if not res_put.ok:
      st.error(
          f"Falha ao atualizar '{FILE_CSV_PATH}' no GitHub:"
          f" {res_put.status_code} - {res_put.text}"
      )
      return False

    max_events_for_log = 2000
    eventos_for_log = updated_df.to_dict(orient="records")
    truncated_msg = (
        f" (truncated: original {len(updated_df)} eventos)"
        if len(eventos_for_log) > max_events_for_log
        else ""
    )
    if len(eventos_for_log) > max_events_for_log:
      eventos_for_log = eventos_for_log[:1000]

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
    requests.put(log_file_url, headers=headers, json=log_data, timeout=15)

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

banner_html = """
<div class="rs-banner-card">
    <div class="rs-banner-title">EXPOINTER 2026 — Programação Institucional - Espaços Gov RS</div>
</div>
"""
st.markdown(banner_html, unsafe_allow_html=True)

df_data = load_csv_from_github()

if df_data.empty:
  st.warning(
      "⚠️ Nenhum dado foi carregado. Verifique o arquivo 'Grade Expointer 2026.csv'"
      " no GitHub."
  )
  st.stop()

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

df_filtered["Hora_Sort"] = df_filtered["Horário"].apply(extract_start_time)
df_filtered["Data_Cat"] = pd.Categorical(
    df_filtered["Data"], categories=ORDEM_DIAS, ordered=True
)
df_filtered = df_filtered.sort_values(
    by=["Data_Cat", "Hora_Sort"]
).drop(columns=["Data_Cat", "Hora_Sort"])

df_agendados = df_filtered[df_filtered["Tema"] != "🔓 HORÁRIO VAGO"]
df_vagos_totais = df_filtered[df_filtered["Tema"] == "🔓 HORÁRIO VAGO"]

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

  if senha == ADMIN_PASSWORD:
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
              "✅ Arquivo CSV atualizado e novo registro salvo no GitHub!"
          )
          st.cache_data.clear()
          st.rerun()

  elif senha:
    st.error("❌ Senha incorreta.")
