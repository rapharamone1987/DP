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

# ID ÚNICO DA SUA PLANILHA NO GOOGLE SHEETS
SHEET_ID = "1WfuAKCRfdGx2jPV_Y0bJYDfolRCJTqyE"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

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


# Leitura Rápida e Sem Erros via CSV Publicado
@st.cache_data(ttl=30)
def load_data_from_google_sheets():
  try:
    df = pd.read_csv(CSV_URL)
    df = df.dropna(how="all").fillna("")

    df_clean = []
    for idx, row in df.iterrows():
      cols = [str(c) for c in row.values]

      horario_raw = str(
          row.get("Horário", cols[2] if len(cols) > 2 else "")
      ).strip()
      tema = str(row.get("Tema", cols[3] if len(cols) > 3 else "")).strip()
      espaco = str(row.get("Espaço", cols[0] if len(cols) > 0 else "")).strip()
      data = str(row.get("Data", cols[1] if len(cols) > 1 else "")).strip()
      sec = str(row.get("Secretaria", cols[4] if len(cols) > 4 else "")).strip()
      resp = str(
          row.get("Responsável", cols[5] if len(cols) > 5 else "")
      ).strip()

      if any(
          d.lower() in horario_raw.lower()
          for d in [
              "sábado",
              "domingo",
              "segunda",
              "terça",
              "quarta",
              "quinta",
              "sexta",
              "29/08",
              "30/08",
              "31/08",
              "01/09",
              "02/09",
              "03/09",
              "04/09",
              "05/09",
              "06/09",
          ]
      ):
        continue

      horario_limpo = clean_time_string(horario_raw)

      if horario_limpo and horario_raw.lower() != "horário":
        is_vago = (
            not tema
            or tema.lower()
            in [
                "livre",
                "vago",
                "disponível",
                "horário vago",
                "nan",
                "none",
                "",
            ]
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


# Estilização CSS
custom_css = """
<style>
    .stApp { background-color: #f8fafc !important; font-family: 'Segoe UI', system-ui, sans-serif; }
    .header-banner { background: linear-gradient(135deg, #064e3b 0%, #15803d 100%) !important; border-radius: 16px; padding: 28px 20px; text-align: center; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); margin-bottom: 24px; border-bottom: 5px solid #eab308; }
    .header-logo-title { font-size: 2.1rem !important; font-weight: 900 !important; color: #ffffff !important; margin: 0 !important; }
    .header-subtitle { color: #dcfce7 !important; font-size: 1.05rem !important; margin-top: 8px !important; font-weight: 600 !important; }
    label, .stSelectbox label, .stMultiSelect label, .stTextInput label, div[data-testid="stMarkdownContainer"] p { color: #0f172a !important; font-weight: 700 !important; }
    div[data-baseweb="tab-highlight"] { background-color: #15803d !important; }
    .event-card-vago { background-color: rgba(248, 250, 252, 0.95) !important; border-radius: 10px; padding: 14px; margin-bottom: 12px; border-left: 6px solid #d97706 !important; border: 1px dashed #f59e0b; }
    .card-time-vago { color: #d97706 !important; font-weight: 800 !important; font-size: 0.9rem !important; }
    .cal-header { background-color: #064e3b !important; color: #ffffff !important; text-align: center; padding: 10px; font-weight: 800; border-radius: 8px; margin-bottom: 12px; font-size: 0.95rem; }
    .cal-event-box { background-color: rgba(255, 255, 255, 0.95) !important; border: 1px solid #cbd5e1 !important; border-left: 5px solid #15803d !important; padding: 10px; margin-bottom: 10px; border-radius: 6px; font-size: 0.85rem; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# Carregamento dos dados
df_data = load_data_from_google_sheets()

# Banner
banner_html = """
<div class="header-banner">
    <div class="header-logo-title">EXPOINTER 2026 — Programação Institucional - Espaços Gov RS</div>
    <div class="header-subtitle">Painel Interativo de Eventos & Gestão de Horários</div>
</div>
"""
st.markdown(banner_html, unsafe_allow_html=True)

if df_data.empty:
  st.warning(
      "⚠️ Nenhum dado carregado. Verifique se a planilha está aberta para leitura"
      " pública."
  )
  st.stop()

todos_dias = [d for d in ORDEM_DIAS if d in df_data["Data"].unique()]
todos_espacos = sorted(list(df_data["Espaço"].unique()))
todas_sec = sorted(
    [
        s
        for s in df_data["Secretaria"].unique()
        if s and str(s).strip() != "🔓 HORÁRIO VAGO"
    ]
)

# Filtros Gerais
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
    dias_para_exibir = [d for d in ORDEM_DIAS if d in df_grid["Data"].unique()]
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
      " feitas diretamente no Google Sheets para evitar conflitos."
  )

  st.link_button(
      "🔗 Abrir Planilha Oficial no Google Sheets",
      f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit",
  )

  st.divider()
  st.markdown("#### Tabela de Dados Atualizada em Tempo Real")
  st.dataframe(df_data, use_container_width=True)
