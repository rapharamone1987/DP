import os
import pandas as pd
import streamlit as st

# 1. Configuração da Página
st.set_page_config(
    page_title="EXPOINTER 2026 — Agenda Verde",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Estilização CSS Personalizada (Base de Cores Verdes)
custom_css = """
<style>
    /* Fundo suave e fontes */
    .stApp {
        background-color: #f4f7f5;
        font-family: 'Segoe UI', system-ui, sans-serif;
    }
    
    /* Cabeçalho Verde Expointer */
    .header-box {
        background: linear-gradient(135deg, #064e3b 0%, #15803d 100%);
        color: #ffffff;
        padding: 24px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
    }
    .header-title { font-size: 1.8rem; font-weight: 800; margin: 0; }
    .header-subtitle { color: #a7f3d0; font-size: 0.95rem; margin-top: 4px; }

    /* Cards em Tom Verde */
    .event-card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 12px;
        border-left: 5px solid #16a34a;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }
    .event-card-desfile {
        border-left-color: #d97706 !important;
        background-color: #fffbeb !important;
    }
    .badge-space {
        background-color: #e6f4ea;
        color: #137333;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .badge-time {
        background-color: #15803d;
        color: #ffffff;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    
    /* Estilo do Grid de Calendário */
    .cal-cell {
        background-color: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        padding: 10px;
        min-height: 120px;
    }
    .cal-header {
        background-color: #15803d;
        color: white;
        text-align: center;
        padding: 8px;
        font-weight: bold;
        border-radius: 6px;
        margin-bottom: 10px;
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)


# 3. Processamento de Dados
@st.cache_data(ttl=300)
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

  return pd.DataFrame(consolidated)


df_data = load_and_process_data()

# Cabeçalho
st.markdown(
    """
<div class="header-box">
    <div class="header-title">🌾 EXPOINTER 2026 — Programação Oficial</div>
    <div class="header-subtitle">Painel de Eventos em Cores Verdes Institucionais</div>
</div>
""",
    unsafe_allow_html=True,
)

if df_data.empty:
  st.warning("Carregando ou nenhum dado encontrado na planilha.")
  st.stop()

# Filtros na Barra Lateral
st.sidebar.header("🌲 Filtros da Agenda")
busca = st.sidebar.text_input("Buscar palavra-chave:", "")
dias = ["Todos os Dias"] + list(df_data["Data"].unique())
dia_sel = st.sidebar.selectbox("Filtrar por Dia:", dias)
espacos = ["Todos os Espaços"] + list(df_data["Espaço"].unique())
espaco_sel = st.sidebar.selectbox("Filtrar por Espaço:", espacos)

# Aplicação dos Filtros
df_filtered = df_data.copy()
if busca:
  t = busca.lower()
  df_filtered = df_filtered[
      df_filtered["Tema"].str.lower().str.contains(t)
      | df_filtered["Espaço"].str.lower().str.contains(t)
  ]
if dia_sel != "Todos os Dias":
  df_filtered = df_filtered[df_filtered["Data"] == dia_sel]
if espaco_sel != "Todos os Espaços":
  df_filtered = df_filtered[df_filtered["Espaço"] == espaco_sel]

# Alternância de Visão por Abas
tab_cards, tab_calendar = st.tabs(
    ["📋 Visão em Lista / Cards", "📅 Visão Calendário (Grid)"]
)

# --- ABA 1: VISÃO EM CARDS ---
with tab_cards:
  if df_filtered.empty:
    st.info("Nenhum evento encontrado.")
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
                    <div style="font-weight:bold; color:#0f172a;">{row['Tema']}</div>
                    <div style="color:#4b5563; font-size:0.8rem; margin-top:6px;">🏢 {row['Secretaria']} {f" | Resp: {row['Responsável']}" if row['Responsável'] else ""}</div>
                </div>
                """
        cols[idx % 2].markdown(card_html, unsafe_allow_html=True)

# --- ABA 2: VISÃO EM CALENDÁRIO GRID ---
with tab_calendar:
  st.markdown("#### Matriz de Eventos por Espaço")
  if df_filtered.empty:
    st.info("Nenhum evento para exibir na matriz.")
  else:
    dias_grid = (
        list(df_filtered["Data"].unique())
        if dia_sel == "Todos os Dias"
        else [dia_sel]
    )

    # Exibe em colunas como dias de um calendário
    grid_cols = st.columns(len(dias_grid))

    for idx, d in enumerate(dias_grid):
      with grid_cols[idx]:
        st.markdown(f'<div class="cal-header">{d}</div>', unsafe_allow_html=True)
        evs_dia = df_filtered[df_filtered["Data"] == d]

        for _, ev in evs_dia.iterrows():
          st.markdown(
              f"""
                    <div style="background:#ffffff; border-left:4px solid #16a34a; padding:8px; margin-bottom:8px; border-radius:4px; font-size:0.8rem; box-shadow:0 1px 2px rgba(0,0,0,0.05);">
                        <span style="color:#15803d; font-weight:bold;">{ev['Horário']}</span><br/>
                        <span style="font-weight:600; color:#1e293b;">{ev['Tema']}</span><br/>
                        <span style="color:#64748b; font-size:0.75rem;">📍 {ev['Espaço']}</span>
                    </div>
                    """,
              unsafe_allow_html=True,
          )
