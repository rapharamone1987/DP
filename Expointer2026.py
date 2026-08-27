import base64
import io
import re
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
import streamlit as st

# 1. Configuração da Página
st.set_page_config(
    page_title="EXPOINTER 2026 — Agenda Institucional",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# LINK RAW DA SUA IMAGEM NO GITHUB
URL_IMAGEM_FUNDO = "https://raw.githubusercontent.com/raphaelsilveiraduarte/dp/main/bg_expointer.jpg"

# ID DA PLANILHA NO GOOGLE SHEETS
SHEET_ID = "1WfuAKCRfdGx2jPV_Y0bJYDfolRCJTqyE"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

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
    "Outros",
]


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


# Leitura Flexível do CSV
@st.cache_data(ttl=15)
def load_data_from_google_sheets():
  try:
    df = pd.read_csv(CSV_URL)
    if df.empty:
      return pd.DataFrame()

    df = df.dropna(how="all").fillna("")

    col_map = {}
    for c in df.columns:
      c_clean = str(c).strip().lower()
      if "espaço" in c_clean or "espaco" in c_clean or "local" in c_clean:
        col_map["Espaço"] = c
      elif "data" in c_clean or "dia" in c_clean:
        col_map["Data"] = c
      elif "horário" in c_clean or "horario" in c_clean or "hora" in c_clean:
        col_map["Horário"] = c
      elif (
          "tema" in c_clean
          or "atividade" in c_clean
          or "evento" in c_clean
          or "programação" in c_clean
      ):
        col_map["Tema"] = c
      elif "secretaria" in c_clean or "entidade" in c_clean or "org" in c_clean:
        col_map["Secretaria"] = c
      elif "responsável" in c_clean or "responsavel" in c_clean:
        col_map["Responsável"] = c

    cols_orig = list(df.columns)
    col_espaco = col_map.get("Espaço", cols_orig[0] if len(cols_orig) > 0 else "")
    col_data = col_map.get("Data", cols_orig[1] if len(cols_orig) > 1 else "")
    col_horario = col_map.get(
        "Horário", cols_orig[2] if len(cols_orig) > 2 else ""
    )
    col_tema = col_map.get("Tema", cols_orig[3] if len(cols_orig) > 3 else "")
    col_sec = col_map.get(
        "Secretaria", cols_orig[4] if len(cols_orig) > 4 else ""
    )
    col_resp = col_map.get(
        "Responsável", cols_orig[5] if len(cols_orig) > 5 else ""
    )

    df_clean = []
    for idx, row in df.iterrows():
      espaco = str(row[col_espaco]).strip() if col_espaco else ""
      data = str(row[col_data]).strip() if col_data else ""
      horario_raw = str(row[col_horario]).strip() if col_horario else ""
      tema = str(row[col_tema]).strip() if col_tema else ""
      sec = str(row[col_sec]).strip() if col_sec else ""
      resp = str(row[col_resp]).strip() if col_resp else ""

      if (
          horario_raw.lower() in ["horário", "horario", "hora"]
          or data.lower() == "data"
      ):
        continue

      horario_limpo = clean_time_string(horario_raw)
      if not horario_limpo:
        horario_limpo = horario_raw

      is_vago = (
          not tema
          or tema.lower()
          in ["livre", "vago", "disponível", "horário vago", "nan", "none", ""]
          or tema.startswith("🔓")
      )

      df_clean.append({
          "Espaço": espaco,
          "Data": data,
          "Horário": horario_limpo,
          "Tema": "🔓 HORÁRIO VAGO" if is_vago else tema,
          "Secretaria": sec if not is_vago else "",
          "Responsável": resp if not is_vago else "",
      })

    return pd.DataFrame(df_clean)

  except Exception as e:
    st.error(f"⚠️ Erro ao carregar dados do Google Sheets: {e}")
    return pd.DataFrame()


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


# Estilização CSS com Imagem do GitHub no Fundo
custom_css = f"""
<style>
    .stApp {{
        background: url("{URL_IMAGEM_FUNDO}") no-repeat center center fixed !important;
        background-size: cover !important;
        font-family: 'Segoe UI', system-ui, sans-serif;
    }}

    .header-banner {{
        background: linear-gradient(135deg, rgba(6, 78, 59, 0.95) 0%, rgba(21, 128, 61, 0.95) 100%) !important;
        border-radius: 16px;
        padding: 32px 20px;
        text-align: center;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        margin-bottom: 24px;
        border-bottom: 5px solid #eab308;
        backdrop-filter: blur(4px);
    }}
    
    .header-logo-title {{
        font-size: 2.2rem !important;
        font-weight: 900 !important;
        color: #ffffff !important;
        margin: 0 !important;
        text-shadow: 0 2px 4px rgba(0,0,0,0.5);
    }}

    div[data-baseweb="select"] > div, input {{
        background-color: rgba(255, 255, 255, 0.92) !important;
        color: #0f172a !important;
        border-radius: 8px !important;
    }}

    label, .stSelectbox label, .stMultiSelect label, .stTextInput label, div[data-testid="stMarkdownContainer"] p {{
        color: #ffffff !important;
        font-weight: 800 !important;
        text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
    }}

    .cal-event-box {{
        background-color: rgba(255, 255, 255, 0.95) !important;
        border: 1px solid #cbd5e1 !important;
        border-left: 5px solid #15803d !important;
        padding: 12px;
        margin-bottom: 10px;
        border-radius: 8px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.15);
    }}

    .event-card-vago {{
        background-color: rgba(255, 255, 255, 0.95) !important;
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 12px;
        border-left: 6px solid #d97706 !important;
        border: 1px dashed #f59e0b;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.15);
    }}

    .cal-header {{
        background-color: rgba(6, 78, 59, 0.95) !important;
        color: #ffffff !important;
        text-align: center;
        padding: 10px;
        font-weight: 800;
        border-radius: 8px;
        margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# Carregamento dos dados
df_data = load_data_from_google_sheets()

# Banner Principal Sem o Subtítulo
banner_html = """
<div class="header-banner">
    <div class="header-logo-title">EXPOINTER 2026 — Programação Institucional - Espaços Gov RS</div>
</div>
"""
st.markdown(banner_html, unsafe_allow_html=True)

if df_data.empty:
  st.warning(
      "⚠️ Nenhum dado carregado. Certifique-se de que a planilha está pública em"
      " 'Compartilhar' -> 'Qualquer pessoa com o link'."
  )
  st.stop()

# Filtros e Mapeamentos
dias_encontrados = list(df_data["Data"].unique())
todos_dias = [
    d for d in ORDEM_DIAS if d in dias_encontrados
] + [d for d in dias_encontrados if d not in ORDEM_DIAS and d]
todos_espacos = sorted([e for e in df_data["Espaço"].unique() if e])
todas_sec = sorted(
    [
        s
        for s in df_data["Secretaria"].unique()
        if s and str(s).strip() != "🔓 HORÁRIO VAGO"
    ]
)

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

# Ordenação
df_filtered["Hora_Sort"] = df_filtered["Horário"].apply(extract_start_time)
df_filtered["Data_Cat"] = pd.Categorical(
    df_filtered["Data"], categories=ORDEM_DIAS, ordered=True
)
df_filtered = df_filtered.sort_values(
    by=["Data_Cat", "Hora_Sort"]
).drop(columns=["Data_Cat", "Hora_Sort"])

df_agendados = df_filtered[df_filtered["Tema"] != "🔓 HORÁRIO VAGO"]
df_vagos_totais = df_filtered[df_filtered["Tema"] == "🔓 HORÁRIO VAGO"]

# Menu Lateral
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
    "🔒 Edição & Visualização",
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
    dias_para_exibir = [
        d for d in todos_dias if d in df_grid["Data"].unique()
    ]
    num_dias = len(dias_para_exibir)

    if num_dias == 0:
      st.info("Nenhum dia correspondente para os filtros selecionados.")
    else:
      grid_cols = st.columns(num_dias)
      for idx, d in enumerate(dias_para_exibir):
        with grid_cols[idx]:
          st.markdown(
              f'<div class="cal-header">{d}</div>', unsafe_allow_html=True
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
                    <span style="color:#15803d; font-weight:800; display:block; margin-bottom:4px;">⏰ {ev['Horário']}</span>
                    <div style="font-weight:700; color:#0f172a; margin-bottom:4px;">{ev['Tema']}</div>
                    <div style="color:#0369a1; font-weight:700; font-size:0.8rem;">📍 {ev['Espaço']}</div>
                    {sec_display}
                    {resp_display}
                </div>
                """,
                unsafe_allow_html=True,
            )

# ABA 2: HORÁRIOS VAGOS
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

# ABA 3: EDIÇÃO E LINK DIRETO
with tab_edit:
  st.markdown("### 🔒 Gestão & Edição da Planilha")
  st.info(
      "Como os dados estão sincronizados em tempo real, as edições devem ser"
      " feitas diretamente no Google Sheets."
  )

  st.link_button(
      "🔗 Abrir Planilha Oficial no Google Sheets",
      f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit",
  )

  st.divider()
  st.markdown("#### Tabela de Dados Carregada")
  st.dataframe(df_data, use_container_width=True)
