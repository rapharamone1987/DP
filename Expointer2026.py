import base64
import io
import os
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

# Ordem Cronológica Oficial dos Dias
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

# MAPEAMENTO GLOBAL (No topo para evitar NameError)
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


# Função para extrair a imagem do banner em Base64
def get_banner_image_b64():
  possible_images = [
      "Screenshot_20260825-095320~2.jpg",
      "esferas.jpg",
      "esferas.jpeg",
      "esferas.png",
      "logo.jpg",
      "logo.png",
  ]
  for img in possible_images:
    if os.path.exists(img):
      ext = img.split(".")[-1].lower()
      mime_type = "image/jpeg" if ext in ["jpg", "jpeg"] else "image/png"
      with open(img, "rb") as img_f:
        b64_str = base64.b64encode(img_f.read()).decode()
      return f"data:{mime_type};base64,{b64_str}", img
  return None, None


img_b64_url, found_img_path = get_banner_image_b64()

if img_b64_url:
  bg_style = f"""
    .stApp {{
        background: linear-gradient(rgba(248, 250, 252, 0.35), rgba(248, 250, 252, 0.45)), url("{img_b64_url}") !important;
        background-size: cover !important;
        background-position: center !important;
        background-repeat: no-repeat !important;
        background-attachment: fixed !important;
        font-family: 'Segoe UI', system-ui, sans-serif;
    }}
    """
else:
  bg_style = """
    .stApp {
        background-color: #f8fafc !important;
        font-family: 'Segoe UI', system-ui, sans-serif;
    }
    """


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


# 2. Estilização CSS Personalizada
custom_css = f"""
<style>
    {bg_style}
    .header-banner {{ background: linear-gradient(135deg, #064e3b 0%, #15803d 100%) !important; border-radius: 16px; padding: 28px 20px; text-align: center; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); margin-bottom: 24px; border-bottom: 5px solid #eab308; }}
    .spheres-box {{ display: inline-flex; align-items: flex-end; justify-content: center; gap: 6px; margin-bottom: 12px; }}
    .s-green {{ width: 20px; height: 20px; border-radius: 50%; background: radial-gradient(circle at 35% 35%, #4ade80, #15803d); box-shadow: 0 2px 4px rgba(0,0,0,0.3); }}
    .s-red {{ width: 30px; height: 30px; border-radius: 50%; background: radial-gradient(circle at 35% 35%, #f87171, #b91c1c); box-shadow: 0 2px 4px rgba(0,0,0,0.3); }}
    .s-yellow {{ width: 18px; height: 18px; border-radius: 50%; background: radial-gradient(circle at 35% 35%, #fde047, #a16207); box-shadow: 0 2px 4px rgba(0,0,0,0.3); }}
    .header-logo-title {{ font-size: 2.1rem !important; font-weight: 900 !important; color: #ffffff !important; margin: 0 !important; padding: 0 !important; letter-spacing: -0.5px; line-height: 1.2; }}
    .header-subtitle {{ color: #dcfce7 !important; font-size: 1.05rem !important; margin-top: 8px !important; font-weight: 600 !important; }}
    label, .stSelectbox label, .stMultiSelect label, .stTextInput label, div[data-testid="stMarkdownContainer"] p {{ color: #0f172a !important; font-weight: 700 !important; }}
    div[data-baseweb="tab-highlight"] {{ background-color: #15803d !important; }}
    .stTabs button {{ background-color: rgba(226, 232, 240, 0.8) !important; border-radius: 8px 8px 0px 0px !important; padding: 10px 20px !important; }}
    .stTabs button p, .stTabs button span, .stTabs [data-baseweb="tab"] * {{ color: #0f172a !important; font-weight: 700 !important; font-size: 1rem !important; }}
    .stTabs [aria-selected="true"] p, .stTabs [aria-selected="true"] span, .stTabs [aria-selected="true"] * {{ color: #15803d !important; font-weight: 800 !important; }}
    .event-card {{ background-color: rgba(255, 255, 255, 0.95) !important; border-radius: 10px; padding: 16px; margin-bottom: 12px; border-left: 6px solid #15803d !important; border: 1px solid #cbd5e1; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.08); }}
    .event-card-vago {{ background-color: rgba(248, 250, 252, 0.92) !important; border-radius: 10px; padding: 14px; margin-bottom: 12px; border-left: 6px solid #64748b !important; border: 1px dashed #94a3b8; box-shadow: 0 2px 4px rgba(0,0,0,0.04); }}
    .card-space-tag {{ color: #0369a1 !important; font-weight: 800 !important; font-size: 0.9rem !important; }}
    .card-time-tag {{ color: #15803d !important; font-weight: 800 !important; font-size: 0.9rem !important; }}
    .card-time-vago {{ color: #475569 !important; font-weight: 800 !important; font-size: 0.9rem !important; }}
    .card-meta-text {{ color: #1e293b !important; font-weight: 700 !important; font-size: 0.88rem !important; }}
    .cal-header {{ background-color: #064e3b !important; color: #ffffff !important; text-align: center; padding: 10px; font-weight: 800; border-radius: 8px; margin-bottom: 12px; font-size: 0.95rem; }}
    .cal-event-box {{ background-color: rgba(255, 255, 255, 0.95) !important; border: 1px solid #cbd5e1 !important; border-left: 5px solid #15803d !important; padding: 10px; margin-bottom: 10px; border-radius: 6px; font-size: 0.85rem; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
    .cal-event-vago {{ background-color: rgba(248, 250, 252, 0.92) !important; border: 1px dashed #cbd5e1 !important; border-left: 5px solid #94a3b8 !important; padding: 10px; margin-bottom: 10px; border-radius: 6px; font-size: 0.85rem; }}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)


# 3. Carregamento e Processamento
@st.cache_data(ttl=60)
def load_and_process_data(excel_path="Grade Expointer 2026.xlsx"):
  if not os.path.exists(excel_path):
    return pd.DataFrame()

  xls = pd.ExcelFile(excel_path)
  raw_events = []

  for sheet in xls.sheet_names:
    if sheet not in SPACE_MAPPING and not sheet.startswith("Agenda "):
      continue

    space_name = SPACE_MAPPING.get(sheet, sheet.replace("Agenda ", "").strip())
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

      horario_raw = str(row[0]).strip() if pd.notna(row[0]) else ""
      tema = str(row[1]).strip() if len(row) > 1 and pd.notna(row[1]) else ""
      sec = str(row[2]).strip() if len(row) > 2 and pd.notna(row[2]) else ""
      resp = str(row[3]).strip() if len(row) > 3 and pd.notna(row[3]) else ""

      horario_limpo = clean_time_string(horario_raw)

      if (
          horario_limpo
          and horario_raw.lower() != "horário"
          and not ("características" in horario_raw.lower())
      ):
        is_vago = (
            not tema
            or tema.lower()
            in ["livre", "vago", "disponível", "horário vago", "nan", "none", ""]
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
  for (space, date), group in df_events.groupby(["Espaço", "Data"], sort=False):
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


# 4. Execução do Carregamento de Dados
df_data = load_and_process_data()

# 5. Banner Institucional
if img_b64_url:
  image_html = f'<img src="{img_b64_url}" style="max-height:75px; margin-bottom:10px; border-radius:6px;" />'
else:
  image_html = """
    <div class="spheres-box">
        <div class="s-green"></div>
        <div class="s-red"></div>
        <div class="s-yellow"></div>
    </div>
    """

banner_complete = f"""
<div class="header-banner">
    {image_html}
    <div class="header-logo-title">EXPOINTER 2026 — Programação Institucional - Espaços Gov RS</div>
    <div class="header-subtitle">Painel Interativo de Eventos & Gestão de Horários</div>
</div>
"""
st.markdown(banner_complete, unsafe_allow_html=True)

if df_data is None or df_data.empty:
  st.warning("⚠️ Carregando dados ou nenhum evento encontrado na planilha.")
  st.stop()

todos_dias = [d for d in ORDEM_DIAS if d in df_data["Data"].unique()]
todos_espacos = sorted(list(df_data["Espaço"].unique()))
todas_sec = sorted(
    [s for s in df_data["Secretaria"].unique() if s and s != "🔓 HORÁRIO VAGO"]
)

# 6. Painel de Filtros Direto na Página Principal
st.markdown("### 🔍 Pesquisar e Filtrar Eventos")
with st.container():
  col_busca, col_dias, col_vagos = st.columns([2, 2, 1])
  with col_busca:
    busca = st.text_input(
        "🔎 Palavra-chave:", "", placeholder="Digite tema, palavra ou local..."
    )
  with col_dias:
    dias_sel = st.multiselect("📅 Filtrar por Dia(s):", todos_dias, default=[])
  with col_vagos:
    exibir_vagos = st.checkbox("🔓 Mostrar Horários Vagos", value=True)

  col_espaco, col_sec = st.columns(2)
  with col_espaco:
    espacos_sel = st.multiselect(
        "📍 Filtrar por Espaço / Auditório:", todos_espacos, default=[]
    )
  with col_sec:
    sec_sel = st.multiselect(
        "🏢 Filtrar por Secretaria / Entidade:", todas_sec, default=[]
    )

df_filtered = df_data.copy()
if not exibir_vagos:
  df_filtered = df_filtered[df_filtered["Tema"] != "🔓 HORÁRIO VAGO"]
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

df_filtered["Data_Cat"] = pd.Categorical(
    df_filtered["Data"], categories=ORDEM_DIAS, ordered=True
)
df_filtered = df_filtered.sort_values("Data_Cat").drop(columns=["Data_Cat"])

# Menu Lateral
st.sidebar.header("📄 Exportação & Gestão")
if st.sidebar.button("⚙️ Gerar Relatório PDF"):
  if not df_filtered.empty:
    info_str = "Seleção Personalizada"
    if espacos_sel:
      info_str = f"Espaços: {', '.join(espacos_sel)}"
    elif dias_sel:
      info_str = f"Dias: {', '.join(dias_sel)}"
    pdf_bytes = generate_pdf_report(df_filtered, info_str)
    st.sidebar.download_button(
        label="📥 Baixar PDF",
        data=pdf_bytes,
        file_name="agenda_expointer.pdf",
        mime="application/pdf",
    )
  else:
    st.sidebar.error("Nenhum evento selecionado.")

st.sidebar.divider()

tab_cards, tab_calendar, tab_edit = st.tabs(
    ["📋 Visão em Cards", "📅 Visão Calendário", "🔒 Área de Edição"]
)

# --- ABA 1: VISÃO EM CARDS ---
with tab_cards:
  if df_filtered.empty:
    st.info("Nenhum evento encontrado.")
  else:
    for data, grupo in df_filtered.groupby("Data", sort=False):
      st.markdown(f"#### 📅 {data}")
      cols = st.columns(2)
      for idx, (_, row) in enumerate(grupo.iterrows()):
        is_vago = row["Tema"] == "🔓 HORÁRIO VAGO"
        card_class = "event-card-vago" if is_vago else "event-card"
        time_class = "card-time-vago" if is_vago else "card-time-tag"
        sec_info = f"🏢 {row['Secretaria']}" if row["Secretaria"] else ""
        resp_info = (
            f" | Resp: {row['Responsável']}" if row["Responsável"] else ""
        )
        meta_line = f"{sec_info}{resp_info}".strip()

        card_html = f"""
                <div class="{card_class}">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span class="{time_class}">⏰ {row['Horário']}</span>
                    </div>
                    <div style="font-weight:800; font-size:1.02rem; color:{'#475569' if is_vago else '#0f172a'}; margin-bottom:8px;">
                        {row['Tema']}
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                        <span class="card-space-tag">📍 {row['Espaço']}</span>
                        <span class="card-meta-text">{meta_line}</span>
                    </div>
                </div>
                """
        cols[idx % 2].markdown(card_html, unsafe_allow_html=True)

# --- ABA 2: VISÃO EM CALENDÁRIO GRID ---
with tab_calendar:
  dia_grid_sel = st.selectbox(
      "📆 Destacar dia na grade:", ["Exibir Todos Selecionados"] + todos_dias
  )
  df_grid = df_filtered.copy()
  if dia_grid_sel != "Exibir Todos Selecionados":
    df_grid = df_grid[df_grid["Data"] == dia_grid_sel]

  if df_grid.empty:
    st.info("Nenhum evento para exibir.")
  else:
    dias_para_exibir = [d for d in ORDEM_DIAS if d in df_grid["Data"].unique()]
    grid_cols = st.columns(len(dias_para_exibir))

    for idx, d in enumerate(dias_para_exibir):
      with grid_cols[idx]:
        st.markdown(f'<div class="cal-header">{d}</div>', unsafe_allow_html=True)
        evs_dia = df_grid[df_grid["Data"] == d]
        for _, ev in evs_dia.iterrows():
          is_vago = ev["Tema"] == "🔓 HORÁRIO VAGO"
          box_class = "cal-event-vago" if is_vago else "cal-event-box"
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
              <div class="{box_class}">
                  <span style="color:#15803d; font-weight:800; display:block; margin-bottom:4px;">⏰ {ev['Horário']}</span>
                  <div style="font-weight:700; color:{'#475569' if is_vago else '#0f172a'}; margin-bottom:4px;">{ev['Tema']}</div>
                  <div style="color:#0369a1; font-weight:700; font-size:0.8rem;">📍 {ev['Espaço']}</div>
                  {sec_display}
                  {resp_display}
              </div>
              """,
              unsafe_allow_html=True,
          )

# --- ABA 3: ÁREA DE EDIÇÃO PROTEGIDA ---
with tab_edit:
  st.markdown("### 🔒 Edição Restrita da Planilha")
  senha = st.text_input("Digite a senha de administrador:", type="password")

  if senha == "expointer2026":
    st.success("🔓 Acesso liberado!")
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
            "Horário": st.column_config.TextColumn("Horário", required=True),
            "Tema": st.column_config.TextColumn(
                "Atividade / Tema (ou 🔓 HORÁRIO VAGO)", required=True
            ),
            "Secretaria": st.column_config.TextColumn("Secretaria / Entidade"),
            "Responsável": st.column_config.TextColumn("Responsável"),
        },
    )

    if st.button("💾 Salvar Alterações na Planilha"):
      excel_path = "Grade Expointer 2026.xlsx"
      try:
        inv_map = {v.lower(): k for k, v in SPACE_MAPPING.items()}
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
          sheets_written = 0
          for space_name in todos_espacos:
            group = edited_df[edited_df["Espaço"] == space_name]
            orig_sheet = inv_map.get(
                str(space_name).lower(), f"Agenda {space_name}"
            )
            clean_sheet_title = re.sub(r"[\\/*?:\[\]]", "_", orig_sheet)[:31]

            if not group.empty:
              group.to_excel(
                  writer, sheet_name=clean_sheet_title, index=False
              )
            else:
              pd.DataFrame(
                  columns=[
                      "Horário",
                      "Atividade / Tema",
                      "Secretaria",
                      "Responsável",
                  ]
              ).to_excel(writer, sheet_name=clean_sheet_title, index=False)
            sheets_written += 1

          if sheets_written == 0:
            pd.DataFrame({"Info": ["Vazia"]}).to_excel(
                writer, sheet_name="Geral", index=False
            )

        st.success("✅ Alterações salvas com sucesso!")
        st.cache_data.clear()
        st.rerun()
      except Exception as e:
        st.error(f"⚠️ Erro ao salvar planilha: {e}")
  elif senha:
    st.error("❌ Senha incorreta.")
