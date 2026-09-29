import streamlit as st
import pandas as pd
import re

# ----------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ----------------------------------------------------
st.set_page_config(
    page_title="Sistema de Consulta Patrimonial - SEAPI/RS",
    page_icon="🏛️",
    layout="wide"
)

SPREADSHEET_ID = "1cnQTahu9K3UGLtmE8pdc8EnbyUxPdB2POdm3csRhZwg"

# ----------------------------------------------------
# FUNÇÃO AUXILIAR DE LIMPEZA DE MOEDA
# ----------------------------------------------------
def converter_moeda_br(coluna):
    """Converte valores no formato 'R$ 1.234,56' ou '1234,56' para float."""
    return (
        coluna.astype(str)
        .str.replace("R$", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
    )

# ----------------------------------------------------
# CARREGAMENTO DOS DADOS COM CACHE (CSV EXPORT)
# ----------------------------------------------------
@st.cache_data(ttl=600)
def carregar_aba(sheet_name: str):
    """Baixa o CSV diretamente de uma aba da planilha do Google Sheets."""
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    return pd.read_csv(url, dtype=str)

@st.cache_data(ttl=600)
def carregar_dados_sistema():
    # 1. Carrega base de Unidades/Departamentos
    df_estrutura = carregar_aba("Estrutura_Custos")
    mapa_unidades = {}
    if not df_estrutura.empty and "Código" in df_estrutura.columns and "Título" in df_estrutura.columns:
        for _, row in df_estrutura.iterrows():
            cod = str(row["Código"]).strip()
            depto = str(row["Título"]).strip()
            if cod and cod != "nan":
                mapa_unidades[cod] = depto

    # 2. Carrega Termos de Responsabilidade (~30k linhas)
    df_termos_raw = carregar_aba("Termo_Responsabilidade")
    df_termos = pd.DataFrame()
    if not df_termos_raw.empty:
        df_termos = pd.DataFrame({
            "Base": "Termos de Responsabilidade",
            "Tombamento": df_termos_raw["bit_registroPat5"].fillna("").astype(str),
            "Descricao": df_termos_raw["bem_descricao5"].fillna("").astype(str),
            "Unidade": df_termos_raw["Textbox29"].fillna("").str.replace(r"^UNIDADE:\s*", "", regex=True).str.strip(),
            "Data_Incorp": df_termos_raw["bem_dataEntrada5"].fillna("").astype(str),
            "Valor_Contabil": converter_moeda_br(df_termos_raw["bit_valorLiquido5"]),
            "Responsavel": df_termos_raw["Textbox92"].fillna("").str.replace(r"^TITULAR:\s*", "", regex=True).str.strip(),
            "Status": "Em Uso Direto"
        })

    # 3. Carrega Bens Cedidos (~3.3k linhas)
    df_cedidos_raw = carregar_aba("Bens_Cedidos")
    df_cedidos = pd.DataFrame()
    if not df_cedidos_raw.empty:
        df_cedidos = pd.DataFrame({
            "Base": "Bens Cedidos",
            "Tombamento": df_cedidos_raw["Nº Patrimônio (Tombamento)"].fillna("").astype(str),
            "Descricao": df_cedidos_raw["Descrição do Bem"].fillna("").astype(str),
            "Unidade": df_cedidos_raw["Unidade Administrativa"].fillna("").astype(str),
            "Data_Incorp": df_cedidos_raw["Data de Incorporação"].fillna("").astype(str),
            "Valor_Contabil": converter_moeda_br(df_cedidos_raw["Valor Contábil (R$)"]),
            "Responsavel": df_cedidos_raw["Titular / Responsável"].fillna("").astype(str),
            "Status": "Bens Cedidos"
        })

    # 4. Carrega Bens Não Localizados (~430 linhas)
    df_nao_loc_raw = carregar_aba("Bens_Nao_Localizados")
    df_nao_loc = pd.DataFrame()
    if not df_nao_loc_raw.empty:
        df_nao_loc = pd.DataFrame({
            "Base": "Bens Não Localizados",
            "Tombamento": df_nao_loc_raw["Nº Patrimônio (Tombamento)"].fillna("").astype(str),
            "Descricao": df_nao_loc_raw["Descrição do Bem"].fillna("").astype(str),
            "Unidade": df_nao_loc_raw["Unidade Administrativa"].fillna("").astype(str),
            "Data_Incorp": df_nao_loc_raw["Data de Incorporação"].fillna("").astype(str),
            "Valor_Contabil": converter_moeda_br(df_nao_loc_raw["Valor Contábil (R$)"]),
            "Responsavel": "Pendente de Localização",
            "Status": "Bens Não Localizados"
        })

    # Concatena em uma base unificada
    df_total = pd.concat([df_termos, df_cedidos, df_nao_loc], ignore_index=True)

    # Função para extrair departamento oficial via código ou mapeamento
    def extrair_departamento(texto_unidade):
        match = re.search(r"(\d{5})", str(texto_unidade))
        if match:
            cod = match.group(1)
            if cod in mapa_unidades:
                return mapa_unidades[cod]
        return "Demais / Não Identificado"

    df_total["Departamento"] = df_total["Unidade"].apply(extrair_departamento)
    return df_total

# ----------------------------------------------------
# CARREGAMENTO DA BASE
# ----------------------------------------------------
with st.spinner("Conectando ao Google Sheets e carregando bases patrimoniais..."):
    try:
        df = carregar_dados_sistema()
    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha: {e}")
        st.info("Verifique se o compartilhamento da planilha está com permissão de leitura para quem possui o link.")
        st.stop()

# ----------------------------------------------------
# CABEÇALHO INSTITUCIONAL
# ----------------------------------------------------
st.title("🏛️ Sistema Integrado de Consulta e Pesquisa Patrimonial")
st.caption("Secretaria da Agricultura, Pecuária, Produção Sustentável e Irrigação • Estado do Rio Grande do Sul")

# ----------------------------------------------------
# BARRA LATERAL: FILTROS INTERATIVOS
# ----------------------------------------------------
st.sidebar.header("🔍 Painel de Filtros")

# 1. Termo de Busca
termo_busca = st.sidebar.text_input(
    "Nº Tombamento / Descrição:",
    placeholder="Ex: 203388, Notebook, Austin..."
).strip()

# 2. Base de Dados
bases_disponiveis = ["Todas as Bases"] + sorted(df["Base"].unique().tolist())
base_selecionada = st.sidebar.selectbox("Base de Dados:", bases_disponiveis)

# 3. Departamento Oficial
deptos_disponiveis = ["Todos os Departamentos"] + sorted(df["Departamento"].unique().tolist())
depto_selecionado = st.sidebar.selectbox("Departamento Oficial:", deptos_disponiveis)

# 4. Unidade de Guarda (dinâmica conforme departamento)
df_escopo_unidade = df.copy()
if depto_selecionado != "Todos os Departamentos":
    df_escopo_unidade = df_escopo_unidade[df_escopo_unidade["Departamento"] == depto_selecionado]

unidades_lista = ["Todas as Unidades"] + sorted([u for u in df_escopo_unidade["Unidade"].unique() if u])
unidade_selecionada = st.sidebar.selectbox("Unidade de Guarda / Local:", unidades_lista)

# 5. Status / Situação
status_lista = ["Todos os Status"] + sorted(df["Status"].unique().tolist())
status_selecionado = st.sidebar.selectbox("Situação / Status:", status_lista)

# ----------------------------------------------------
# APLICAÇÃO DOS FILTROS
# ----------------------------------------------------
df_filtrado = df.copy()

if termo_busca:
    df_filtrado = df_filtrado[
        df_filtrado["Tombamento"].str.contains(termo_busca, case=False, na=False) |
        df_filtrado["Descricao"].str.contains(termo_busca, case=False, na=False)
    ]

if base_selecionada != "Todas as Bases":
    df_filtrado = df_filtrado[df_filtrado["Base"] == base_selecionada]

if depto_selecionado != "Todos os Departamentos":
    df_filtrado = df_filtrado[df_filtrado["Departamento"] == depto_selecionado]

if unidade_selecionada != "Todas as Unidades":
    df_filtrado = df_filtrado[df_filtrado["Unidade"] == unidade_selecionada]

if status_selecionado != "Todos os Status":
    df_filtrado = df_filtrado[df_filtrado["Status"] == status_selecionado]

# ----------------------------------------------------
# CARDS DE INDICADORES (KPIs)
# ----------------------------------------------------
qtd_total = len(df_filtrado)
valor_total = df_filtrado["Valor_Contabil"].sum()
ticket_medio = (valor_total / qtd_total) if qtd_total > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)

col1.metric("Quantidade de Bens", f"{qtd_total:,}".replace(",", "."))
col2.metric("Valor Patrimonial Total", f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col3.metric("Ticket Médio Contábil", f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col4.metric("Filtros Ativos", "🔵 Ativo(s)" if (termo_busca or base_selecionada != "Todas as Bases" or depto_selecionado != "Todos os Departamentos" or unidade_selecionada != "Todas as Unidades" or status_selecionado != "Todos os Status") else "⚪ Nenhum")

st.divider()

# ----------------------------------------------------
# ABAS DE VISUALIZAÇÃO
# ----------------------------------------------------
tab_resultados, tab_distribuicao, tab_ficha = st.tabs([
    "📋 Itens Pesquisados",
    "📊 Resumo Analítico",
    "🔍 Ficha Detalhada do Bem"
])

with tab_resultados:
    st.subheader(f"Resultados Encontrados ({qtd_total})")
    
    if qtd_total > 0:
        # Formatação do valor para visualização amigável
        df_exibicao = df_filtrado.copy()
        df_exibicao["Valor_Contabil_Formatado"] = df_exibicao["Valor_Contabil"].apply(
            lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        colunas_tabela = [
            "Tombamento", "Descricao", "Departamento", "Unidade", 
            "Data_Incorp", "Status", "Valor_Contabil_Formatado", "Responsavel"
        ]
        
        st.dataframe(
            df_exibicao[colunas_tabela].rename(columns={
                "Tombamento": "Nº Tombamento",
                "Descricao": "Descrição do Bem",
                "Departamento": "Departamento",
                "Unidade": "Unidade de Guarda",
                "Data_Incorp": "Data Incorp.",
                "Status": "Situação",
                "Valor_Contabil_Formatado": "Valor Contábil",
                "Responsavel": "Titular / Responsável"
            }),
            use_container_width=True,
            hide_index=True
        )

        # Botão para Download
        csv_download = df_filtrado.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Baixar Resultados Filtrados (CSV)",
            data=csv_download,
            file_name="consulta_patrimonial_seapi.csv",
            mime="text/csv"
        )
    else:
        st.warning("Nenhum bem patrimonial localizado para os filtros informados.")

with tab_distribuicao:
    if qtd_total > 0:
        col_graf1, col_graf2 = st.columns(2)
        
        with col_graf1:
            st.subheader("Bens por Departamento")
            agrup_depto = df_filtrado.groupby("Departamento")["Valor_Contabil"].agg(["count", "sum"]).reset_index()
            agrup_depto.columns = ["Departamento", "Qtd. Bens", "Valor Total (R$)"]
            agrup_depto = agrup_depto.sort_values(by="Qtd. Bens", ascending=False)
            st.dataframe(agrup_depto, use_container_width=True, hide_index=True)
            st.bar_chart(data=agrup_depto.set_index("Departamento")["Qtd. Bens"])
            
        with col_graf2:
            st.subheader("Bens por Situação / Status")
            agrup_status = df_filtrado.groupby("Status")["Valor_Contabil"].agg(["count", "sum"]).reset_index()
            agrup_status.columns = ["Status", "Qtd. Bens", "Valor Total (R$)"]
            st.dataframe(agrup_status, use_container_width=True, hide_index=True)
            st.bar_chart(data=agrup_status.set_index("Status")["Valor Total (R$)"])
    else:
        st.info("Sem dados disponíveis para gerar gráficos.")

with tab_ficha:
    st.subheader("Consulta de Bem Individual")
    tombamento_ficha = st.text_input("Informe o Número de Tombamento Exato:", placeholder="Ex: 203388")
    
    if tombamento_ficha:
        item = df[df["Tombamento"] == tombamento_ficha.strip()]
        if not item.empty:
            dado = item.iloc[0]
            st.success(f"Bem Localizado: **{dado['Tombamento']} - {dado['Descricao']}**")
            
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Departamento:** {dado['Departamento']}")
                st.write(f"**Unidade de Guarda:** {dado['Unidade']}")
                st.write(f"**Base de Origem:** {dado['Base']}")
                st.write(f"**Data de Incorporação:** {dado['Data_Incorp']}")
            with c2:
                st.write(f"**Situação / Status:** {dado['Status']}")
                st.write(f"**Responsável / Titular:** {dado['Responsavel']}")
                st.write(f"**Valor Contábil:** R$ {dado['Valor_Contabil']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        else:
            st.error(f"Nenhum registro encontrado com o tombamento '{tombamento_ficha}'.")tuais.")
