import streamlit as st
import pandas as pd

# Configuração da página
st.set_page_config(
    page_title="Sistema de Gestão Patrimonial - SEAPI/RS",
    page_icon="🏛️",
    layout="wide"
)

st.title("🏛️ Sistema de Pesquisa e Análise Patrimonial")
st.caption("Secretaria da Agricultura, Pecuária, Produção Sustentável e Irrigação • RS")

# 1. Carregamento dos Dados com Cache
@st.cache_data(ttl=600)
def carregar_dados():
    # Você pode carregar de um CSV local ou diretamente via link de exportação do Google Sheets:
    # url = "https://docs.google.com/spreadsheets/d/SEU_ID/export?format=csv&gid=GID_DA_ABA"
    # df = pd.read_csv(url)
    df = pd.read_csv("cadastro_bens.csv")
    return df

try:
    df = carregar_dados()
except Exception as e:
    st.warning("Carregue o arquivo de dados ou configure a conexão com o Google Sheets.")
    st.stop()

# 2. Sidebar com Filtros
st.sidebar.header("🔍 Painel de Filtros")

termo_busca = st.sidebar.text_input("Nº de Tombamento ou Descrição:")

departamentos = ["Todos"] + sorted(df["Departamento"].dropna().unique().tolist())
depto_selecionado = st.sidebar.selectbox("Departamento Oficial:", departamentos)

# Filtro dinâmico de Unidades baseado no Departamento
if depto_selecionado != "Todos":
    unidades_disponiveis = sorted(df[df["Departamento"] == depto_selecionado]["Unidade"].dropna().unique().tolist())
else:
    unidades_disponiveis = sorted(df["Unidade"].dropna().unique().tolist())

unidades = ["Todas"] + unidades_disponiveis
unidade_selecionada = st.sidebar.selectbox("Unidade de Guarda / Local:", unidades)

status_opcoes = ["Todos"] + sorted(df["Status"].dropna().unique().tolist())
status_selecionado = st.sidebar.selectbox("Situação / Status:", status_opcoes)

# 3. Aplicação dos Filtros
df_filtrado = df.copy()

if termo_busca:
    df_filtrado = df_filtrado[
        df_filtrado["Tombamento"].astype(str).str.contains(termo_busca, case=False, na=False) |
        df_filtrado["Descricao"].astype(str).str.contains(termo_busca, case=False, na=False)
    ]

if depto_selecionado != "Todos":
    df_filtrado = df_filtrado[df_filtrado["Departamento"] == depto_selecionado]

if unidade_selecionada != "Todas":
    df_filtrado = df_filtrado[df_filtrado["Unidade"] == unidade_selecionada]

if status_selecionado != "Todos":
    df_filtrado = df_filtrado[df_filtrado["Status"] == status_selecionado]

# 4. KPIs Principais
kpi1, kpi2, kpi3 = st.columns(3)
total_bens = len(df_filtrado)
valor_total = df_filtrado["Valor_Contabil"].sum()
valor_medio = valor_total / total_bens if total_bens > 0 else 0

kpi1.metric("Quantidade de Bens", f"{total_bens:,.0f}".replace(",", "."))
kpi2.metric("Valor Patrimonial Total", f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
kpi3.metric("Ticket Médio", f"R$ {valor_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

st.divider()

# 5. Visualização e Abas
tab_busca, tab_graficos = st.tabs(["📋 Resultados da Consulta", "📊 Análise Gráfica"])

with tab_busca:
    st.subheader(f"Registros Localizados ({total_bens})")
    st.dataframe(
        df_filtrado[["Tombamento", "Descricao", "Departamento", "Unidade", "Status", "Valor_Contabil"]],
        use_container_width=True,
        hide_index=True
    )
    
    # Exportação
    csv = df_filtrado.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Exportar Dados Filtrados (CSV)",
        data=csv,
        file_name="consulta_patrimonial.csv",
        mime="text/csv",
    )

with tab_graficos:
    if total_bens > 0:
        st.subheader("Distribuição do Valor por Departamento")
        depto_summary = df_filtrado.groupby("Departamento")["Valor_Contabil"].sum().sort_values(ascending=False).head(10)
        st.bar_chart(depto_summary)
    else:
        st.info("Nenhum dado para exibir gráficos com os filtros atuais.")
