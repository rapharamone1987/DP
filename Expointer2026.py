import io
import os
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
import streamlit as st

# 1. Configuração da Página
st.set_page_config(
    page_title="EXPOINTER 2026 — Agenda Verde",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ordem Cronológica Oficial dos Dias da Expointer 2026
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

# 2. Estilização CSS Personalizada (Forçando contraste absoluto)
custom_css = """
<style>
    .stApp {
        background-color: #f1f5f9 !important;
        font-family: 'Segoe UI', system-ui, sans-serif;
    }
    .header-box {
        background: linear-gradient(135deg, #064e3b 0%, #15803d 100%);
        color: #ffffff !important;
        padding: 24px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
    }
    .header-title { font-size: 1.8rem; font-weight: 800; margin: 0; color: #ffffff !important; }
    .header-subtitle { color: #dcfce7 !important; font-size: 0.95rem; margin-top: 4px; font-weight: 500; }

    /* CONTRASTE DE RÓTULOS E TEXTOS DE LABELS DO STREAMLIT */
    label, .stSelectbox label, .stMultiSelect label, .stTextInput label, div[data-testid="stMarkdownContainer"] p {
        color: #0f172a !important;
        font-weight: 700 !important;
    }

    /* CORREÇÃO DAS ABAS (TABS) EM QUALQUER DISPOSITIVO */
    div[data-baseweb="tab-highlight"] {
        background-color: #15803d !important;
    }
    .stTabs button {
        background-color: #e2e8f0 !important;
        border-radius: 8px 8px 0px 0px !important;
        padding: 8px 16px !important;
    }
    .stTabs button p, .stTabs button span, .stTabs [data-baseweb="tab"] *, .stTabs button * {
        color: #0f172a !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
    }
    .stTabs [aria-selected="true"] p, .stTabs [aria-selected="true"] span, .stTabs [aria-selected="true"] * {
        color: #15803d !important;
        font-weight: 800 !important;
    }

    h1, h2, h3, h4, h5, h6, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #0f172a !important;
        font-weight: 800 !important;
    }

    .event-card {
        background-color: #ffffff !important;
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 12px;
        border-left: 5px solid #15803d !important;
        border: 1px solid #cbd5e1;
        box-shadow: 0 2px 4px rgba(0,0,0,0.06);
    }
    .badge-space {
        background-color: #0369a1 !important;
        color: #ffffff !important;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .badge-time {
        background-color: #15803d !important;
        color: #ffffff !important;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .cal-header {
        background-color: #064e3b !important;
        color: #ffffff !important;
        text-align: center;
        padding: 10px;
        font-weight: 800;
        border-radius: 6px;
        margin-bottom: 12px;
        font-size: 0.95rem;
    }
    .cal-event-box {
        background-color: #ffffff !important;
        border: 1px solid #94a3b8 !important;
        border-left: 5px solid #15803d !important;
        padding: 10px;
        margin-bottom: 10px;
        border-radius: 6px;
        font-size: 0.85rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .cal-event-time {
        color: #15803d !important;
        font-weight: 800 !important;
        display: block;
        margin-bottom: 4px;
    }
    .cal-event-title {
        font-weight: 700 !important;
        color: #0f172a !important;
        margin-bottom: 6px;
    }
    .cal-event-meta {
        color: #334155 !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)


# 3. Processamento de Dados
@st.cache_data(ttl=60)
def load_and_process_data(excel_path="Grade Expointer 2026.xlsx"):
  space_mapping = {
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

  if not os.path.exists(excel_path):
    return pd.DataFrame()

  xls = pd.ExcelFile(excel_path)
  raw_events = []

  for sheet in xls.sheet_names:
    if sheet not in space_mapping:
      continue
    df = pd.read_excel(excel_path, sheet_name=sheet, header=None)
    current_date = "Outros"

    for idx, row in df.iterrows():
      row_str = " ".join([str(val) for val in row.values if pd.notna(val)])
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

      horario = str(row[0]).strip() if pd.notna(row[0]) else ""
      tema = str(row[1]).strip() if len(row) > 1 and pd.notna(row[1]) else ""
      sec = str(row[2]).strip() if len(row) > 2 and pd.notna(row[2]) else ""
      resp = str(row[3]).strip() if len(row) > 3 and pd.notna(row[3]) else ""

      if (
          horario
          and horario.lower() != "horário"
          and tema
          and tema.lower() != "tema"
          and not ("características" in horario.lower())
      ):
        raw_events.append({
            "Espaço": space_mapping[sheet],
            "Data": current_date,
            "Horário": horario,
            "Tema": tema,
            "Secretaria": sec if sec != "nan" else "",
            "Responsável": resp if resp != "nan" else "",
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
      title = row["Tema"]
      time_start = row["Horário"]
      org = row["Secretaria"]
      resp = row["Responsável"]

      j = i + 1
      time_end = time_start
      while j < len(group) and group.iloc[j]["Tema"] == title:
        time_end = group.iloc[j]["Horário"]
        j += 1

      time_disp = time_start[:5] if len(time_start) >= 5 else time_start
      if time_end != time_start:
        end_disp = time_end[:5] if len(time_end) >= 5 else time_end
        time_disp = f"{time_disp} - {end_disp}"

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

  # Ordenação Cronológica Garantida dos Dias
  df_result["Data_Cat"] = pd.Categorical(
      df_result["Data"], categories=ORDEM_DIAS, ordered=True
  )
  df_result = df_result.sort_values("Data_Cat").drop(columns=["Data_Cat"])

  return df_result


# 4. Gerador de PDF Formatado
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
      Paragraph("EXPOINTER 2026 — Programação Oficial", title_style)
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


df_data = load_and_process_data()

# Cabeçalho
st.markdown(
    """
<div class="header-box">
    <div class="header-title">🌾 EXPOINTER 2026 — Programação Oficial</div>
    <div class="header-subtitle">Painel Interativo de Eventos</div>
</div>
""",
    unsafe_allow_html=True,
)

if df_data.empty:
  st.warning("Carregando ou nenhum dado encontrado na planilha.")
  st.stop()

# Lista de dias ordenada cronologicamente
todos_dias = [d for d in ORDEM_DIAS if d in df_data["Data"].unique()]

# Filtros na Barra Lateral
st.sidebar.header("🌲 Filtros de Busca")
busca = st.sidebar.text_input("Buscar palavra-chave:", "")

dias_sel = st.sidebar.multiselect(
    "Filtrar por Dia(s):",
    todos_dias,
    default=[],
    placeholder="Selecione uma ou mais opções...",
)

todos_espacos = sorted(list(df_data["Espaço"].unique()))
espacos_sel = st.sidebar.multiselect(
    "Filtrar por Espaço(s):",
    todos_espacos,
    default=[],
    placeholder="Selecione uma ou mais opções...",
)

todas_sec = sorted([s for s in df_data["Secretaria"].unique() if s])
sec_sel = st.sidebar.multiselect(
    "Filtrar por Secretaria(s):",
    todas_sec,
    default=[],
    placeholder="Selecione uma ou mais opções...",
)

# Aplicação dos Filtros
df_filtered = df_data.copy()
if busca:
  t = busca.lower()
  df_filtered = df_filtered[
      df_filtered["Tema"].str.lower().str.contains(t)
      | df_filtered["Espaço"].str.lower().str.contains(t)
      | df_filtered["Responsável"].str.lower().str.contains(t)
  ]

if dias_sel:
  df_filtered = df_filtered[df_filtered["Data"].isin(dias_sel)]

if espacos_sel:
  df_filtered = df_filtered[df_filtered["Espaço"].isin(espacos_sel)]

if sec_sel:
  df_filtered = df_filtered[df_filtered["Secretaria"].isin(sec_sel)]

# Garantir ordenação cronológica no dataframe filtrado
df_filtered["Data_Cat"] = pd.Categorical(
    df_filtered["Data"], categories=ORDEM_DIAS, ordered=True
)
df_filtered = df_filtered.sort_values("Data_Cat").drop(columns=["Data_Cat"])

# Exportação de PDF
st.sidebar.divider()
st.sidebar.header("📄 Exportar Calendário PDF")
if st.sidebar.button("⚙️ Gerar PDF com Filtros Atuais"):
  if not df_filtered.empty:
    info_str = "Seleção Personalizada"
    if espacos_sel:
      info_str = f"Espaços: {', '.join(espacos_sel)}"
    elif dias_sel:
      info_str = f"Dias: {', '.join(dias_sel)}"

    pdf_bytes = generate_pdf_report(df_filtered, info_str)
    st.sidebar.download_button(
        label="📥 Baixar PDF Gerado",
        data=pdf_bytes,
        file_name="agenda_expointer_selecao.pdf",
        mime="application/pdf",
    )
  else:
    st.sidebar.error("Sem eventos para gerar o PDF.")

# Alternância de Visão por Abas (Com Restrição de Acesso na Aba de Edição)
tab_cards, tab_calendar, tab_edit = st.tabs([
    "📋 Visão em Cards",
    "📅 Visão Calendário",
    "🔒 Editar Dados da Planilha",
])

# --- ABA 1: VISÃO EM CARDS ---
with tab_cards:
  if df_filtered.empty:
    st.info("Nenhum evento encontrado para os filtros selecionados.")
  else:
    for data, grupo in df_filtered.groupby("Data", sort=False):
      st.markdown(f"### 📅 {data}")
      cols = st.columns(2)
      for idx, (_, row) in enumerate(grupo.iterrows()):
        card_html = f"""
                <div class="event-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span class="badge-space">📍 {row['Espaço']}</span>
                        <span class="badge-time">⏰ {row['Horário']}</span>
                    </div>
                    <div style="font-weight:700; color:#0f172a; font-size:1.02rem; margin-top:4px;">{row['Tema']}</div>
                    <div style="color:#334155; font-size:0.83rem; font-weight:600; margin-top:8px;">🏢 {row['Secretaria']} {f" | Resp: {row['Responsável']}" if row['Responsável'] else ""}</div>
                </div>
                """
        cols[idx % 2].markdown(card_html, unsafe_allow_html=True)

# --- ABA 2: VISÃO EM CALENDÁRIO GRID ---
with tab_calendar:
  st.markdown("#### Matriz de Eventos em Grade")
  dia_grid_sel = st.selectbox(
      "📆 Selecione o dia para focar na matriz:",
      ["Exibir Todos Selecionados"] + todos_dias,
  )

  df_grid = df_filtered.copy()
  if dia_grid_sel != "Exibir Todos Selecionados":
    df_grid = df_grid[df_grid["Data"] == dia_grid_sel]

  if df_grid.empty:
    st.info("Nenhum evento para exibir nesta visão.")
  else:
    # Dias a exibir em ordem cronológica estrita
    dias_para_exibir = [d for d in ORDEM_DIAS if d in df_grid["Data"].unique()]
    grid_cols = st.columns(len(dias_para_exibir))

    for idx, d in enumerate(dias_para_exibir):
      with grid_cols[idx]:
        st.markdown(f'<div class="cal-header">{d}</div>', unsafe_allow_html=True)
        evs_dia = df_grid[df_grid["Data"] == d]

        for _, ev in evs_dia.iterrows():
          st.markdown(
              f"""
                    <div class="cal-event-box">
                        <span class="cal-event-time">⏰ {ev['Horário']}</span>
                        <div class="cal-event-title">{ev['Tema']}</div>
                        <div class="cal-event-meta">📍 {ev['Espaço']}</div>
                    </div>
                    """,
              unsafe_allow_html=True,
          )

# --- ABA 3: EDITAR DADOS DIRETO NO APP (COM RESTRIÇÃO / SENHA) ---
with tab_edit:
  st.markdown("### 🔒 Edição Restrita da Agenda")

  # Campo de senha para restrição de acesso
  senha = st.text_input(
      "Digite a senha de administrador para liberar a edição:", type="password"
  )

  # Definir a senha desejada (ex: expointer2026)
  if senha == "expointer2026":
    st.success("🔓 Acesso liberado!")
    st.info(
        "Altere dados, horários ou adicione novas linhas na tabela abaixo. Após"
        " editar, clique em **Salvar Alterações**."
    )

    edited_df = st.data_editor(
        df_data,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Espaço": st.column_config.SelectboxColumn(
                "Espaço / Local", options=todos_espacos, required=True
            ),
            "Data": st.column_config.SelectboxColumn(
                "Dia", options=todos_dias, required=True
            ),
            "Horário": st.column_config.TextColumn(
                "Horário (ex: 09:00 - 10:00)", required=True
            ),
            "Tema": st.column_config.TextColumn(
                "Atividade / Tema", required=True
            ),
            "Secretaria": st.column_config.TextColumn("Secretaria / Entidade"),
            "Responsável": st.column_config.TextColumn("Responsável"),
        },
    )

    if st.button("💾 Salvar Alterações na Planilha"):
      excel_path = "Grade Expointer 2026.xlsx"
      with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        for space_name, group in edited_df.groupby("Espaço"):
          sheet_title = f"Agenda {space_name}"
          if len(sheet_title) > 31:
            sheet_title = sheet_title[:31]
          group.to_excel(writer, sheet_name=sheet_title, index=False)

      st.success("✅ Alterações salvas com sucesso!")
      st.cache_data.clear()
  elif senha:
    st.error("❌ Senha incorreta. Acesso negado.")
  else:
    st.warning("⚠️ Esta área é restrita. Digite a senha acima para continuar.")
