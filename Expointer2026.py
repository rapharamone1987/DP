import os
import pandas as pd
import streamlit as st

# 1. Configuração Inicial do Serviço e da Página
st.set_page_config(
    page_title="EXPOINTER 2026 — Grade Oficial",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Estilização CSS Personalizada (Custom Theme)
custom_css = """
<style>
    /* Fundo da aplicação e tipografia */
    .stApp {
        background-color: #f8fafc;
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    }
    
    /* Cabeçalho principal com as cores da Expointer */
    .header-box {
        background-color: #0f172a;
        color: #ffffff;
        padding: 24px;
        border-radius: 12px;
        border-bottom: 5px solid #16a34a;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .header-title {
        font-size: 1.8rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .header-subtitle {
        color: #94a3b8;
        font-size: 0.95rem;
        margin-top: 6px;
        margin-bottom: 0;
    }

    /* Cards de Eventos */
    .event-card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
        border-left: 5px solid #2563eb;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
        transition: transform 0.15s ease;
    }
    .event-card-desfile {
        border-left-color: #d97706 !important;
        background-color: #fffbeb !important;
    }
    .card-title {
        font-size: 1rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 8px;
    }
    .badge-space {
        background-color: #e0f2fe;
        color: #0369a1;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .badge-time {
        background-color: #dcfce7;
        color: #15803d;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .card-meta {
        color: #64748b;
        font-size: 0.8rem;
        margin-top: 8px;
        border-top: 1px dashed #e2e8f0;
        padding-top: 8px;
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)


# 3. Função com Cache para Carregar e Consolidar a Planilha
@st.cache_data(ttl=300)  # Recarrega automaticamente a cada 5 minutos
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

  # Consolidação de horários contínuos da mesma atividade
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


# Carrega os dados
df_data = load_and_process_data()

# 4. Cabeçalho Principal
st.markdown(
    """
<div class="header-box">
    <div class="header-title">🌾 EXPOINTER 2026 — Programação Geral</div>
    <div class="header-subtitle">Painel Interativo de Consulta e Filtro de Espaços e Atividades</div>
</div>
""",
    unsafe_allow_html=True,
)

if df_data.empty:
  st.warning(
      "Nenhum dado encontrado na planilha 'Grade Expointer 2026.xlsx'."
      " Certifique-se de que o arquivo está na mesma pasta do script."
  )
  st.stop()

# 5. Barra Lateral de Filtros (Sidebar)
st.sidebar.header("🔍 Filtros da Agenda")

# Filtro de Busca por Texto
busca = st.sidebar.text_input(
    "Buscar por tema, palestrante ou palavra-chave:", ""
)

# Filtro de Data
dias_disponiveis = ["Todos os Dias"] + list(df_data["Data"].unique())
dia_selecionado = st.sidebar.selectbox("Filtrar por Dia:", dias_disponiveis)

# Filtro de Espaço
espacos_disponiveis = ["Todos os Espaços"] + list(df_data["Espaço"].unique())
espaco_selecionado = st.sidebar.selectbox(
    "Filtrar por Espaço / Auditório:", espacos_disponiveis
)

# Filtro de Secretaria
secretarias = [s for s in df_data["Secretaria"].unique() if s]
secretarias_disponiveis = ["Todas as Entidades"] + sorted(secretarias)
sec_selecionada = st.sidebar.selectbox(
    "Filtrar por Secretaria / Organização:", secretarias_disponiveis
)

# Botão para Resetar Filtros
if st.sidebar.button("🧹 Limpar Filtros"):
  st.rerun()

# 6. Aplicação dos Filtros nos Dados
df_filtrado = df_data.copy()

if busca:
  termo = busca.lower()
  df_filtrado = df_filtrado[
      df_filtrado["Tema"].str.lower().str.contains(termo)
      | df_filtrado["Responsável"].str.lower().str.contains(termo)
      | df_filtrado["Secretaria"].str.lower().str.contains(termo)
      | df_filtrado["Espaço"].str.lower().str.contains(termo)
  ]

if dia_selecionado != "Todos os Dias":
  df_filtrado = df_filtrado[df_filtrado["Data"] == dia_selecionado]

if espaco_selecionado != "Todos os Espaços":
  df_filtrado = df_filtrado[df_filtrado["Espaço"] == espaco_selecionado]

if sec_selecionada != "Todas as Entidades":
  df_filtrado = df_filtrado[df_filtrado["Secretaria"] == sec_selecionada]

# 7. Exibição de Estatísticas Rápidas
col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Total de Atividades", len(df_filtrado))
col_m2.metric("Espaços Ativos", df_filtrado["Espaço"].nunique())
col_m3.metric(
    "Entidades Envolvidas",
    df_filtrado["Secretaria"].replace("", None).nunique(),
)

st.divider()

# 8. Renderização da Lista de Eventos em Cards
if df_filtrado.empty:
  st.info("Nenhuma atividade encontrada para os filtros selecionados.")
else:
  # Agrupa por data para exibição organizada
  for data, grupo_dia in df_filtrado.groupby("Data", sort=False):
    st.subheader(f"📅 {data}")

    # Grid de 2 colunas para os cards
    cols = st.columns(2)
    idx = 0

    for _, row in grupo_dia.iterrows():
      is_desfile = "DESFILE" in str(row["Tema"]).upper()
      card_class = (
          "event-card event-card-desfile" if is_desfile else "event-card"
      )

      resp_str = (
          f" | Resp.: {row['Responsável']}" if row["Responsável"] else ""
      )
      sec_str = f"🏢 {row['Secretaria']}" if row["Secretaria"] else ""
      meta_str = f"{sec_str}{resp_str}".strip(" |")

      card_html = f"""
            <div class="{card_class}">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span class="badge-space">📍 {row['Espaço']}</span>
                    <span class="badge-time">⏰ {row['Horário']}</span>
                </div>
                <div class="card-title">{row['Tema']}</div>
                {"<div class='card-meta'>" + meta_str + "</div>" if meta_str else ""}
            </div>
            """

      cols[idx % 2].markdown(card_html, unsafe_allow_html=True)
      idx += 1

    st.write("")

# 9. Opção para Download dos Dados Filtrados
st.sidebar.divider()
csv_data = df_filtrado.to_csv(index=False).encode("utf-8")
st.sidebar.download_button(
    label="📥 Baixar Agenda Filtrada (CSV)",
    data=csv_data,
    file_name="agenda_expointer_2026.csv",
    mime="text/csv",
)
