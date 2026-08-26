
  import base64
import io
import re
from google.oauth2.service_account import Credentials
import gspread
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

# NOME DA SUA PLANILHA NO GOOGLE DRIVE / SHEETS
GOOGLE_SHEET_NAME = "Grade Expointer 2026"

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

SPACE_MAPPING = {
    "Agenda Auditório ADMINISTRAÇÃO": "Auditório Administração",
    "Agenda Auditório ESPAÇO GOV": "Auditório Espaço Gov",
    "Agenda Arena ESPAÇO GOV": "Arena Espaço Gov",
    "Agenda Bancada ESPAÇO GOV": "Bancada Espaço Gov",
    "Agenda Estande FIERGS": "Estande FIERGS",
    "Sala de reunião 1 ESPAÇO GOV ": "Sala Reunião 1",
    "Sala de reunião 2 ESPAÇO GOV": "Sala Reunião 2",
    "Sala de reunião 3 ESPAÇO GOV": "Sala Reunião 3",
    "ESTANDE SEAPI E SEMA": "Estande SEAPI/SEMA",
    "Agenda FUNDESA": "Agenda FUNDESA",
}


# Conexão com Google Sheets via Streamlit Secrets
@st.cache_resource
def get_gspread_client():
  scope = [
      "https://www.googleapis.com/auth/spreadsheets",
      "https://www.googleapis.com/auth/drive",
  ]
  credentials = Credentials.from_service_account_info(
      st.secrets["gcp_service_account"], scopes=scope
  )
  return gspread.authorize(credentials)


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


def load_data_from_sheets():
  try:
    gc = get_gspread_client()
    sh = gc.open(GOOGLE_SHEET_NAME)

    raw_events = []

    for worksheet in sh.worksheets():
      sheet_title = worksheet.title
      if sheet_title not in SPACE_MAPPING:
        continue

      space_name = SPACE_MAPPING[sheet_title]
      rows = worksheet.get_all_values()

      current_date = "Outros"

      for row in rows:
        row_str = " ".join([str(val) for val in row if val])

        # Identifica mudança de dia na grade
        for day_code in [
            "29/08",
            "30/08",
            "31/08",
            "01/09",
            "02/09",
            "03/09",
            "04/09",
            "05/09",
            "06/09",
        ]:
          if day_code in row_str and any(
              w in row_str
              for w in [
                  "Sábado",
                  "Domingo",
                  "Segunda",
                  "Terça",
                  "Quarta",
                  "Quinta",
                  "Sexta",
                  "2026",
              ]
          ):
            if "29/08" in day_code:
              current_date = "Sábado 29/08"
            elif "30/08" in day_code:
              current_date = "Domingo 30/08"
            elif "31/08" in day_code:
              current_date = "Segunda 31/08"
            elif "01/09" in day_code:
              current_date = "Terça 01/09"
            elif "02/09" in day_code:
              current_date = "Quarta 02/09"
            elif "03/09" in day_code:
              current_date = "Quinta 03/09"
            elif "04/09" in day_code:
              current_date = "Sexta 04/09"
            elif "05/09" in day_code:
              current_date = "Sábado 05/09"
            elif "06/09" in day_code:
              current_date = "Domingo 06/09"
            break

        horario_raw = str(row[0]).strip() if len(row) > 0 and row[0] else ""
        tema = str(row[1]).strip() if len(row) > 1 and row[1] else ""
        sec = str(row[2]).strip() if len(row) > 2 and row[2] else ""
        resp = str(row[3]).strip() if len(row) > 3 and row[3] else ""

        # LIMPEZA DE CABEÇALHOS SUJOS E DUPLICADOS DE DATA
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

        if (
            horario_limpo
            and horario_raw.lower() != "horário"
            and not ("características" in horario_raw.lower())
        ):
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

          raw_events.append({
              "Espaço": space_name,
              "Data": current_date,
              "Horário": horario_limpo,
              "Tema": "🔓 HORÁRIO VAGO" if is_vago else tema,
              "Secretaria": (
                  ""
                  if is_vago
                  else (sec if sec.lower() not in ["nan", "none"] else "")
              ),
              "Responsável": (
                  ""
                  if is_vago
                  else (resp if resp.lower() not in ["nan", "none"] else "")
              ),
          })

    df_events = pd.DataFrame(raw_events)
    if df_events.empty:
      return df_events

    consolidated = []
    for (space, date), group in df_events.groupby(
        ["Espaço", "Data"], sort=False
    ):
      group = group.reset_index(drop=True)
      i = 0
      while i < len(group):
        row = group.iloc[i]
        title, time_start, org, resp = (
            row["Tema"],
            row["Horário"],
            row["Secretaria"],
            row["Responsável"],
        )
        j = i + 1
        time_end = time_start
        while (
            j < len(group)
            and group.iloc[j]["Tema"] == title
            and title != "🔓 HORÁRIO VAGO"
        ):
          time_end = group.iloc[j]["Horário"]
          j += 1

        time_disp = time_start
        if time_end != time_start and "-" not in time_start:
          time_disp = f"{time_start} - {time_end}"

        consolidated.append({
            "Espaço": space,
            "Data": date,
            "Horário": time_disp,
            "Tema": title,
            "Secretaria": org,
            "Responsável": resp,
        })
        i = j

    df_result = pd.DataFrame(consolidated)
    df_result["Data_Cat"] = pd.Categorical(
        df_result["Data"], categories=ORDEM_DIAS, ordered=True
    )
    return df_result.sort_values("Data_Cat").drop(columns=["Data_Cat"])

  except Exception as e:
    st.error(f"⚠️ Erro ao carregar dados do Google Sheets: {e}")
    return pd.DataFrame()


def save_data_to_sheets(df_to_save):
  try:
    gc = get_gspread_client()
    sh = gc.open(GOOGLE_SHEET_NAME)

    # Atualiza a primeira aba geral com a visualização editada
    worksheet = sh.sheet1
    worksheet.clear()

    data = [df_to_save.columns.values.tolist()] + df_to_save.values.tolist()
    worksheet.update(data)
    return True
  except Exception as e:
    st.error(f"⚠️ Erro ao salvar alterações no Google Sheets: {e}")
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

# 2. Execução do Carregamento de Dados
df_data = load_data_from_sheets()

# Banner
banner_html = """
<div class="header-banner">
    <div class="header-logo-title">EXPOINTER 2026 — Programação Institucional - Espaços Gov RS</div>
    <div class="header-subtitle">Painel Interativo de Eventos & Gestão Conectado ao Google Sheets</div>
</div>
"""
st.markdown(banner_html, unsafe_allow_html=True)

if df_data.empty:
  st.warning(
      "⚠️ Nenhum dado carregado. Verifique a conexão com o Google Sheets."
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

# 3. Painel de Filtros Gerais
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

# Estrutura de Abas
tab_calendar, tab_vagos, tab_edit = st.tabs([
    "📅 Visão Calendário",
    "🔓 Horários Livres / Vagos",
    "🔒 Área de Edição (Google Sheets)",
])

# --- ABA 1: VISÃO CALENDÁRIO ---
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
    grid_cols = st.columns(len(dias_para_exibir))

    for idx, d in enumerate(dias_para_exibir):
      with grid_cols[idx]:
        st.markdown(f'<div class="cal-header">{d}</div>', unsafe_allow_html=True)
        evs_dia = df_grid[df_grid["Data"] == d]
        for _, ev in evs_dia.iterrows():
          sec_val = (
              str(ev["Secretaria"]).strip() if pd.notna(ev["Secretaria"]) else ""
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

# --- ABA 2: HORÁRIOS LIVRES / VAGOS ---
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

# --- ABA 3: ÁREA DE EDIÇÃO DIRETA NO GOOGLE SHEETS ---
with tab_edit:
  st.markdown("### 🔒 Edição Direta no Google Sheets")
  senha = st.text_input("Digite a senha de administrador:", type="password")

  if senha == "expointer2026":
    st.success(
        "🔓 Acesso liberado! Edições salvas aqui serão gravadas diretamente no"
        " Google Sheets."
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
                "Dia", options=todos_dias, required=True
            ),
            "Horário": st.column_config.TextColumn("Horário", required=True),
            "Tema": st.column_config.TextColumn(
                "Atividade / Tema (ou 🔓 HORÁRIO VAGO)", required=True
            ),
            "Secretaria": st.column_config.TextColumn("Secretaria / Entidade"),
            "Responsável": st.column_config.TextColumn("Responsável"),
        },
        key="editor_sheets",
    )

    if st.button("💾 Salvar Diretamente no Google Sheets"):
      if save_data_to_sheets(edited_df):
        st.success("✅ Google Sheets atualizado com sucesso!")
        st.cache_resource.clear()
        st.rerun()

  elif senha:
    st.error("❌ Senha incorreta.")
