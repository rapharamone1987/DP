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

FILE_CSV_PATH = "Grade Expointer.csv"
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


# 2. Leitura e Processamento do CSV
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
          " GitHub."
      )
      return pd.DataFrame()

    content_b64 = res.json().get("content", "")
    if not content_b64:
      return pd.DataFrame()

    content_bytes = base64.b64decode(content_b64)

    df = pd.read_csv(
        io.BytesIO(content_bytes), sep=";", encoding="utf-8-sig", dtype=str
    )
    df = df.fillna("")

    df["Tema"] = df["Tema"].apply(
        lambda x: "🔓 HORÁRIO VAGO"
        if not str(x).strip()
        or str(x).strip().lower() in ["vago", "livre", "nan", "none", "", "-"]
        else str(x).strip()
    )

    return df

  except Exception as e:
    st.error(f"⚠️ Erro ao carregar arquivo CSV: {e}")
    return pd.DataFrame()


# Funções Auxiliares para Agrupamento e Ordenação
def extract_time_val(time_str):
  """Extrai o horário inicial como int (ex: '09:30' -> 930) para ordenação precisa."""
  if not time_str:
    return 9999
  m = re.search(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b", str(time_str))
  if m:
    h, mins = m.group(0).split(":")
    return int(h) * 100 + int(mins)
  return 9999


def merge_consecutive_events(df):
  """Consolida horários subsequentes para eventos idênticos."""
  if df.empty:
    return df

  merged_rows = []

  for (espaco, data), group in df.groupby(["Espaço", "Data"], sort=False):
    group = group.copy()
    group["Time_Key"] = group["Horário"].apply(extract_time_val)
    group = group.sort_values(by="Time_Key")

    current_event = None

    for _, row in group.iterrows():
      if current_event is None:
        current_event = dict(row)
        current_event["Hora_Inicio"] = str(row["Horário"]).strip()
        current_event["Hora_Fim"] = str(row["Horário"]).strip()
      else:
        same_theme = (
            str(current_event.get("Tema")).strip().lower()
            == str(row.get("Tema")).strip().lower()
        )
        same_sec = (
            str(current_event.get("Secretaria")).strip().lower()
            == str(row.get("Secretaria")).strip().lower()
        )
        same_resp = (
            str(current_event.get("Responsável")).strip().lower()
            == str(row.get("Responsável")).strip().lower()
        )
        not_vago = row.get("Tema") != "🔓 HORÁRIO VAGO"

        if same_theme and same_sec and same_resp and not_vago:
          current_event["Hora_Fim"] = str(row["Horário"]).strip()
        else:
          if (
              current_event["Hora_Inicio"]
              and current_event["Hora_Fim"]
              and current_event["Hora_Inicio"] != current_event["Hora_Fim"]
          ):
            current_event["Horário"] = (
                f"{current_event['Hora_Inicio']} - {current_event['Hora_Fim']}"
            )
          else:
            current_event["Horário"] = current_event["Hora_Inicio"]

          merged_rows.append(current_event)

          current_event = dict(row)
          current_event["Hora_Inicio"] = str(row["Horário"]).strip()
          current_event["Hora_Fim"] = str(row["Horário"]).strip()

    if current_event:
      if (
          current_event["Hora_Inicio"]
          and current_event["Hora_Fim"]
          and current_event["Hora_Inicio"] != current_event["Hora_Fim"]
      ):
        current_event["Horário"] = (
            f"{current_event['Hora_Inicio']} - {current_event['Hora_Fim']}"
        )
      else:
        current_event["Horário"] = current_event["Hora_Inicio"]

      merged_rows.append(current_event)

  res_df = pd.DataFrame(merged_rows)
  cols_to_drop = [
      c for c in ["Time_Key", "Hora_Inicio", "Hora_Fim"] if c in res_df.columns
  ]
  return res_df.drop(columns=cols_to_drop)


# 3. Commit de Alterações para o GitHub
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
    encoded_filename = urllib.parse.quote(FILE_CSV_PATH)
    get_file_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{encoded_filename}"
    res = requests.get(get_file_url, headers=headers, timeout=10)

    sha = res.json().get("sha", "") if res.ok else ""

    csv_buffer = io.StringIO()
    updated_df.to_csv(csv_buffer, index=False, sep=";")
    csv_b64 = base64.b64encode(csv_buffer.getvalue().encode("utf-8")).decode(
        "utf-8"
    )

    update_data = {
        "message": f"Atualização de grade via App ({timestamp})",
        "content": csv_b64,
        "branch": "main",
    }
    if sha:
      update_data["sha"] = sha

    res_put = requests.put(
        get_file_url, headers=headers, json=update_data, timeout=15
    )
    if not res_put.ok:
      st.error(f"Falha ao atualizar arquivo no GitHub: {res_put.text}")
      return False

    log_content = {
        "data_alteracao": timestamp,
        "observacoes": change_log_notes,
        "total_linhas": len(updated_df),
        "eventos": updated_df.to_dict(orient="records"),
    }
    log_b64 = base64.b64encode(
        json.dumps(log_content, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("utf-8")

    log_file_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/historico_alteracoes/alteracao_{timestamp}.json"
    requests.put(
        log_file_url,
        headers=headers,
        json={
            "message": f"Histórico de alteração ({timestamp})",
            "content": log_b64,
            "branch": "main",
        },
        timeout=15,
    )

    return True

  except Exception as e:
    st.error(f"⚠️ Erro ao salvar alterações no GitHub: {e}")
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


# ESTILIZAÇÃO CSS (Bandeira RS com amarelo corrigido e tom opaco/fosco elegante)
bg_url_css = f"data:image/jpeg;base64,{img_b64}" if img_b64 else ""

custom_css = f"""
<style>
    .stApp {{
        background: linear-gradient(rgba(15, 23, 42, 0.45), rgba(15, 23, 42, 0.45)), url("{bg_url_css}") no-repeat center center fixed !important;
        background-size: cover !important;
        font-family: 'Segoe UI', system-ui, sans-serif !important;
    }}

    .rs-banner-card {{
        background: linear-gradient(135deg, rgba(21, 101, 52, 0.72) 0%, rgba(22, 128, 61, 0.70) 32%, rgba(185, 28, 28, 0.70) 65%, rgba(234, 179, 8, 0.72) 100%) !important;
        border-radius: 16px;
        padding: 28px 20px;
        text-align: center;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.45);
        margin-bottom: 24px;
        border-bottom: 5px solid #facc15;
        position: relative;
    }}

    .rs-banner-title-1 {{
        font-size: 2.2rem !important;
        font-weight: 900 !important;
        color: #ffffff !important;
        margin: 0 0 6px 0 !important;
        text-shadow: 0 2px 6px rgba(0, 0, 0, 0.85);
        letter-spacing: 1px;
    }}

    .rs-banner-title-2 {{
        font-size: 1.25rem !important;
        font-weight: 700 !important;
        color: #fef08a !important;
        margin: 0 !important;
        text-shadow: 0 2px 5px rgba(0, 0, 0, 0.85);
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

# Banner em duas linhas centralizado
banner_html = """
<div class="rs-banner-card">
    <div class="rs-banner-title-1">EXPOINTER 2026</div>
    <div class="rs-banner-title-2">Programação Institucional — Espaços Gov RS</div>
</div>
"""
st.markdown(banner_html, unsafe_allow_html=True)

df_data = load_csv_from_github()

if df_data.empty:
  st.warning(
      "⚠️ Nenhum dado foi carregado. Verifique o arquivo 'Grade Expointer.csv' no"
      " GitHub."
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
    df_pdf = merge_consecutive_events(df_agendados)
    pdf_bytes = generate_pdf_report(df_pdf, info_str)
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
    df_grid_merged = merge_consecutive_events(df_grid)

    dias_unicos = [
        d for d in ORDEM_DIAS if d in df_grid_merged["Data"].unique()
    ]

    if len(dias_unicos) == 0:
      st.info("Nenhum dia correspondente para os filtros selecionados.")
    else:
      grid_cols = st.columns(len(dias_unicos))
      for idx, d in enumerate(dias_unicos):
        with grid_cols[idx]:
          st.markdown(
              f'<div class="cal-header">📅 {d}</div>', unsafe_allow_html=True
          )
          evs_dia = df_grid_merged[df_grid_merged["Data"] == d].copy()

          # Ordenação estrita crescente por horário
          evs_dia["Order_Key"] = evs_dia["Horário"].apply(extract_time_val)
          evs_dia = evs_dia.sort_values(by="Order_Key")

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

    df_vagos_sorted = df_vagos_totais.copy()
    df_vagos_sorted["Order_Key"] = df_vagos_sorted["Horário"].apply(
        extract_time_val
    )
    df_vagos_sorted = df_vagos_sorted.sort_values(by="Order_Key")

    for data in [
        d for d in ORDEM_DIAS if d in df_vagos_sorted["Data"].unique()
    ]:
      grupo = df_vagos_sorted[df_vagos_sorted["Data"] == data]
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

# ABA 3: EDIÇÃO COM FILTROS E VERSIONAMENTO
with tab_edit:
  st.markdown("### 🔒 Edição & Versionamento Automático")
  senha = st.text_input("Digite a senha de administrador:", type="password")

  if senha == ADMIN_PASSWORD:
    st.success(
        "🔓 Acesso liberado! Utilize os filtros abaixo para localizar e editar"
        " rapidamente qualquer dia ou espaço."
    )

    # Filtros para a tabela de edição
    col_f1, col_f2 = st.columns(2)
    with col_f1:
      edit_filter_dia = st.selectbox(
          "📅 Filtrar tabela por Dia:", ["Todos"] + todos_dias, index=0
      )
    with col_f2:
      edit_filter_espaco = st.selectbox(
          "📍 Filtrar tabela por Espaço:", ["Todos"] + todos_espacos, index=0
      )

    # Prepara sub-conjunto filtrado para edição rápida
    df_to_edit = df_data.copy()
    if edit_filter_dia != "Todos":
      df_to_edit = df_to_edit[df_to_edit["Data"] == edit_filter_dia]
    if edit_filter_espaco != "Todos":
      df_to_edit = df_to_edit[df_to_edit["Espaço"] == edit_filter_espaco]

    notes = st.text_input(
        "Motivo / Descrição da Alteração (Auditoria):",
        placeholder="Ex: Inclusão do painel SEDUC no dia 31/08",
    )

    edited_subset = st.data_editor(
        df_to_edit,
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
      with st.spinner("Mesclando alterações e salvando no GitHub..."):
        # Mescla as alterações feitas no subconjunto de volta ao dataframe principal
        df_final_save = df_data.copy()

        # Remove as linhas antigas que pertencem aos filtros selecionados e insere as editadas
        if edit_filter_dia != "Todos" and edit_filter_espaco != "Todos":
          cond = (df_final_save["Data"] == edit_filter_dia) & (
              df_final_save["Espaço"] == edit_filter_espaco
          )
        elif edit_filter_dia != "Todos":
          cond = df_final_save["Data"] == edit_filter_dia
        elif edit_filter_espaco != "Todos":
          cond = df_final_save["Espaço"] == edit_filter_espaco
        else:
          cond = None

        if cond is not None:
          df_final_save = df_final_save[~cond]
          df_final_save = pd.concat(
              [df_final_save, edited_subset], ignore_index=True
          )
        else:
          df_final_save = edited_subset

        if commit_changes_to_github(df_final_save, notes):
          st.success(
              "✅ Arquivo CSV atualizado e novo registro salvo no GitHub!"
          )
          st.cache_data.clear()
          st.rerun()

  elif senha:
    st.error("❌ Senha incorreta.")
    
