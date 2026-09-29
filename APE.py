import streamlit as st
import pandas as pd
import re

# ----------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA
# ----------------------------------------------------
st.set_page_config(
    page_title="Sistema Integrado de Consulta Patrimonial - SEAPI/RS",
    page_icon="🏛️",
    layout="wide"
)

SPREADSHEET_ID = "1cnQTahu9K3UGLtmE8pdc8EnbyUxPdB2POdm3csRhZwg"

# ----------------------------------------------------
# 2. FUNÇÕES DE PROCESSAMENTO E CLASSIFICAÇÃO
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

def classificar_bem_patrimonial(descricao: str):
    """
    Classifica a descrição do bem em 3 camadas:
    (Macro_Familia, Tipo_Bem, Subtipo)
    """
    desc = str(descricao).upper().strip()

    # 1. CADEIRAS E ASSENTOS
    if re.search(r"\b(CADEIRA|POLTRONA|LONGARINA|BANQUETA|BANCO)\b", desc):
        familia = "Mobiliário em Geral"
        tipo = "Cadeira / Assento"

        if re.search(r"\b(RODIZIO|RODÍZIO|GIRATORIA|GIRATÓRIA|RODAS|RODINHAS)\b", desc):
            subtipo = "Giratória / Rodízio"
        elif re.search(r"\b(FIXA|FIXO|4 PES|4 PÉS|APROXIMACAO|APROXIMAÇÃO|INTERLOCUTOR)\b", desc):
            subtipo = "Fixa"
        elif "LONGARINA" in desc:
            subtipo = "Longarina"
        elif "POLTRONA" in desc:
            subtipo = "Poltrona Executiva/Conforto"
        else:
            subtipo = "Não Especificado"
        return familia, tipo, subtipo

    # 2. ARMÁRIOS E ARQUIVOS
    if re.search(r"\b(ARMARIO|ARMÁRIO|ARQUIVO|ROUPEIRO)\b", desc):
        familia = "Mobiliário em Geral"
        tipo = "Armário / Arquivo"
        if re.search(r"\b(BAIXO|BAIXA|BALCAO|BALCÃO|CREDENZA)\b", desc):
            subtipo = "Baixo"
        elif re.search(r"\b(ALTO|ALTA)\b", desc):
            subtipo = "Alto"
        elif re.search(r"\b(MEDIO|MÉDIO)\b", desc):
            subtipo = "Médio"
        elif re.search(r"\b(ACO|AÇO)\b", desc):
            subtipo = "Aço (Sem altura especificada)"
        else:
            subtipo = "Não Especificado"
        return familia, tipo, subtipo

    # 3. MESAS E ESTAÇÕES DE TRABALHO
    if re.search(r"\b(MESA|ESTACAO DE TRABALHO|ESTAÇÃO DE TRABALHO|ESCRIVANINHA)\b", desc):
        familia = "Mobiliário em Geral"
        tipo = "Mesa / Estação de Trabalho"
        if re.search(r"\b(REUNIAO|REUNIÃO)\b", desc):
            subtipo = "Reunião"
        elif re.search(r"\b(EM L|ANGULAR|CANTO)\b", desc):
            subtipo = "Em L / Canto"
        elif re.search(r"\b(RETA|ESCRITORIO|ESCRITÓRIO|DIGITADOR)\b", desc):
            subtipo = "Reta / Operacional"
        else:
            subtipo = "Não Especificado"
        return familia, tipo, subtipo

    # 4. INFORMÁTICA & TECNOLOGIA
    if re.search(r"\b(NOTEBOOK|LAPTOP)\b", desc):
        return "Informática & TI", "Computador", "Notebook"
    if re.search(r"\b(MICROCOMPUTADOR|COMPUTADOR|DESKTOP|CPU|SERVIDOR)\b", desc):
        subtipo = "Servidor" if "SERVIDOR" in desc else "Desktop"
        return "Informática & TI", "Computador", subtipo
    if re.search(r"\b(MONITOR|TELA|DISPLAY)\b", desc):
        return "Informática & TI", "Monitor / Tela", "Não Especificado"
    if re.search(r"\b(IMPRESSORA|MULTIFUNCIONAL|PLOTTER|SCANNER)\b", desc):
        if "MULTIFUNCIONAL" in desc:
            subtipo = "Multifuncional"
        elif "SCANNER" in desc:
            subtipo = "Scanner"
        else:
            subtipo = "Impressora Térmica/Laser/Jato"
        return "Informática & TI", "Impressora & Imagem", subtipo
    if re.search(r"\b(NOBREAK|NO-BREAK|ESTABILIZADOR)\b", desc):
        return "Informática & TI", "Proteção de Energia", "Nobreak / Estabilizador"

    # 5. VEÍCULOS & MÁQUINAS
    if re.search(r"\b(CAMINHONETE|CAMIONETE|PICKUP|CAMINHAO|CAMINHÃO)\b", desc):
        subtipo = "Caminhão" if "CAMINH" in desc else "Caminhonete"
        return "Veículos & Transporte", "Utilitário / Carga", subtipo
    if re.search(r"\b(AUTOMOVEL|AUTOMÓVEL|CARRO|VEICULO|VEÍCULO)\b", desc):
        return "Veículos & Transporte", "Veículo Leve", "Passeio"
    if re.search(r"\b(TRATOR|RETROESCAVADEIRA|COLHEITADEIRA|PULVERIZADOR|SEMEADORA)\b", desc):
        return "Maquinário & Equip. Agrícolas", "Máquina Agrícola", "Pesada / Implemento"

    # 6. CLIMATIZAÇÃO & ELETRODOMÉSTICOS
    if re.search(r"\b(CONDICIONADOR DE AR|AR CONDICIONADO|SPLIT|VENTILADOR)\b", desc):
        subtipo = "Split / AC" if "SPLIT" in desc or "AR" in desc else "Ventilador"
        return "Climatização & Eletro", "Climatização", subtipo
    if re.search(r"\b(REFRIGERADOR|GELADEIRA|FREEZER|BEBEDOURO|MICRO-ONDAS|CAFETEIRA)\b", desc):
        return "Climatização & Eletro", "Eletrodoméstico / Copa", "Padrão"

    # 7. COMUNICAÇÃO & ÁUDIO/VÍDEO
    if re.search(r"\b(TELEFONE|TELEFONICO|RADIO|RÁDIO|TELEVISOR|TV|PROJETOR)\b", desc):
        return "Comunicação & Áudio/Vídeo", "Aparelho de Mídia/Comunicação", "Não Especificado"

    # 8. OUTROS
    return "Outros / Diversos", "Não Classificado", "Não Especificado"

# ----------------------------------------------------
# 3. CARREGAMENTO DOS DADOS COM CACHE
# ----------------------------------------------------
@st.cache_data(ttl=600)
def carregar_aba(sheet_name: str):
    """Baixa a aba da planilha em formato CSV via GViz."""
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    return pd.read_csv(url, dtype=str)

@st.cache_data(ttl=600)
def carregar_dados_sistema():
    # 1. Carrega Estrutura de Custos para mapear Departamentos
    df_estrutura = carregar_aba("Estrutura_Custos")
    mapa_por_codigo = {}
    mapa_por_nome = {}

    if not df_estrutura.empty:
        for _, row in df_estrutura.iterrows():
            depto = str(row.get("Título", "")).strip()
            cod = str(row.get("Código", "")).strip()
            unid_texto = str(row.get("UNIDADE DE GUARDA", "")).strip()

            if cod and cod != "nan" and depto and depto != "nan":
                mapa_por_codigo[cod] = depto

            if unid_texto and unid_texto != "nan" and depto and depto != "nan":
                nome_limpo = re.sub(r"^\d+\s*-\s*", "", unid_texto).upper().strip()
                mapa_por_nome[nome_limpo] = depto

    def identificar_departamento(texto_unidade):
        txt = str(texto_unidade).upper().strip()
        if not txt or txt == "NAN":
            return "Não Informado"

        # Tenta casar código de 5 dígitos (ex: 000090001 -> 90001)
        match_cod = re.search(r"0*([1-9]\d{4})", txt)
        if match_cod:
            cod_5d = match_cod.group(1)
            if cod_5d in mapa_por_codigo:
                return mapa_por_codigo[cod_5d]

        # Tenta casar nome textual
        txt_sem_prefixo = re.sub(r"^UNIDADE:\s*", "", txt)
        txt_sem_prefixo = re.sub(r"^ECC\.\d+\.\d+\s*-\s*", "", txt_sem_prefixo).strip()
        for nome_ref, depto_ref in mapa_por_nome.items():
            if nome_ref in txt_sem_prefixo or txt_sem_prefixo in nome_ref:
                return depto_ref

        # Regras diretas da SEAPI
        if "GABINETE" in txt:
            return "GABINETE SEAPI"
        elif "PATRIMÔNIO" in txt or "DIVISÃO DE PATRIMÔNIO" in txt:
            return "DA"
        elif "ANIMAL" in txt or "DIPOA" in txt or "DSA" in txt:
            return "DDA"
        elif "VEGETAL" in txt or "DEFESA VEGETAL" in txt:
            return "DDV"
        elif "PESQUISA" in txt or "DDPA" in txt:
            return "DDPA"
        elif "INFRAESTRUTURA" in txt or "DINFRA" in txt:
            return "DINFRA"

        return "Demais (DEFIN, DGSP, DG)"

    # 2. Termos de Responsabilidade (~30k linhas)
    df_termos_raw = carregar_aba("Termo_Responsabilidade")
    df_termos = pd.DataFrame()
    if not df_termos_raw.empty:
        unidade_limpa = (
            df_termos_raw["Textbox29"].fillna("")
            .str.replace(r"^UNIDADE:\s*", "", regex=True)
            .str.replace(r"^ECC\.\d+\.\d+\s*-\s*", "", regex=True)
            .str.strip()
        )
        df_termos = pd.DataFrame({
            "Base": "Termos de Responsabilidade",
            "Tombamento": df_termos_raw["bit_registroPat5"].fillna("").astype(str),
            "Tombamento_Anterior": df_termos_raw["bit_nroSerie5"].fillna("").astype(str),
            "Descricao": df_termos_raw["bem_descricao5"].fillna("").astype(str),
            "Unidade": unidade_limpa,
            "Unidade_Raw": df_termos_raw["Textbox29"].fillna("").astype(str),
            "Data_Incorp": df_termos_raw["bem_dataEntrada5"].fillna("").astype(str),
            "Valor_Contabil": converter_moeda_br(df_termos_raw["bit_valorLiquido5"]),
            "Responsavel": df_termos_raw["Textbox92"].fillna("").str.replace(r"^TITULAR:\s*", "", regex=True).str.strip(),
            "Status": "Em Uso Direto"
        })

    # 3. Bens Cedidos (~3.3k linhas)
    df_cedidos_raw = carregar_aba("Bens_Cedidos")
    df_cedidos = pd.DataFrame()
    if not df_cedidos_raw.empty:
        df_cedidos = pd.DataFrame({
            "Base": "Bens Cedidos",
            "Tombamento": df_cedidos_raw["Nº Patrimônio (Tombamento)"].fillna("").astype(str),
            "Tombamento_Anterior": df_cedidos_raw["Patrimônio Anterior"].fillna("").astype(str),
            "Descricao": df_cedidos_raw["Descrição do Bem"].fillna("").astype(str),
            "Unidade": df_cedidos_raw["Unidade Administrativa"].fillna("").astype(str).str.strip(),
            "Unidade_Raw": df_cedidos_raw["Unidade Administrativa"].fillna("").astype(str),
            "Data_Incorp": df_cedidos_raw["Data de Incorporação"].fillna("").astype(str),
            "Valor_Contabil": converter_moeda_br(df_cedidos_raw["Valor Contábil (R$)"]),
            "Responsavel": df_cedidos_raw["Titular / Responsável"].fillna("").astype(str),
            "Status": "Bens Cedidos"
        })

    # 4. Bens Não Localizados (~430 linhas)
    df_nao_loc_raw = carregar_aba("Bens_Nao_Localizados")
    df_nao_loc = pd.DataFrame()
    if not df_nao_loc_raw.empty:
        df_nao_loc = pd.DataFrame({
            "Base": "Bens Não Localizados",
            "Tombamento": df_nao_loc_raw["Nº Patrimônio (Tombamento)"].fillna("").astype(str),
            "Tombamento_Anterior": df_nao_loc_raw["Patrimônio Anterior"].fillna("").astype(str),
            "Descricao": df_nao_loc_raw["Descrição do Bem"].fillna("").astype(str),
            "Unidade": df_nao_loc_raw["Unidade Administrativa"].fillna("").astype(str).str.strip(),
            "Unidade_Raw": df_nao_loc_raw["Unidade Administrativa"].fillna("").astype(str),
            "Data_Incorp": df_nao_loc_raw["Data de Incorporação"].fillna("").astype(str),
            "Valor_Contabil": converter_moeda_br(df_nao_loc_raw["Valor Contábil (R$)"]),
            "Responsavel": "Pendente de Localização",
            "Status": "Bens Não Localizados"
        })

    # Concatenação e limpeza
    df_total = pd.concat([df_termos, df_cedidos, df_nao_loc], ignore_index=True)
    df_total["Departamento"] = df_total["Unidade_Raw"].apply(identificar_departamento)

    # Classificação em 3 camadas de cada bem com base na Descrição
    classificacoes = df_total["Descricao"].apply(classificar_bem_patrimonial)
    df_total["Macro_Familia"] = [c[0] for c in classificacoes]
    df_total["Tipo_Bem"] = [c[1] for c in classificacoes]
    df_total["Subtipo"] = [c[2] for c in classificacoes]

    return df_total

# ----------------------------------------------------
# 4. CARREGAMENTO DOS DADOS NO APP
# ----------------------------------------------------
with st.spinner("Conectando ao Google Sheets e carregando dados patrimoniais..."):
    try:
        df = carregar_dados_sistema()
    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha: {e}")
        st.info("Certifique-se de que a planilha está compartilhada com 'Qualquer pessoa com o link' em modo Leitor.")
        st.stop()

# ----------------------------------------------------
# 5. CABEÇALHO DO SISTEMA
# ----------------------------------------------------
st.title("🏛️ Sistema Integrado de Consulta e Pesquisa Patrimonial")
st.caption("Secretaria da Agricultura, Pecuária, Produção Sustentável e Irrigação • Estado do Rio Grande do Sul")

# ----------------------------------------------------
# 6. BARRA LATERAL (FILTROS INTERATIVOS)
# ----------------------------------------------------
st.sidebar.header("🔍 Painel de Filtros")

# 1. Campo Livre de Busca
termo_busca = st.sidebar.text_input(
    "Nº Tombamento (Atual/Anterior) ou Descrição:",
    placeholder="Ex: 203388, 10542, Cadeira, Dell..."
).strip()

# 2. Filtro de Base de Origem
bases_disponiveis = ["Todas as Bases"] + sorted(df["Base"].unique().tolist())
base_selecionada = st.sidebar.selectbox("Base de Dados:", bases_disponiveis)

st.sidebar.markdown("---")
st.sidebar.subheader("🏢 Localização & Lotação")

# 3. Departamento Oficial
deptos_disponiveis = ["Todos os Departamentos"] + sorted(df["Departamento"].unique().tolist())
depto_selecionado = st.sidebar.selectbox("Departamento Oficial:", deptos_disponiveis)

# 4. Unidade de Guarda (Dependente do Departamento)
df_escopo_unidade = df.copy()
if depto_selecionado != "Todos os Departamentos":
    df_escopo_unidade = df_escopo_unidade[df_escopo_unidade["Departamento"] == depto_selecionado]

unidades_lista = ["Todas as Unidades"] + sorted([u for u in df_escopo_unidade["Unidade"].unique() if u])
unidade_selecionada = st.sidebar.selectbox("Unidade de Guarda / Local:", unidades_lista)

st.sidebar.markdown("---")
st.sidebar.subheader("📦 Tipologia do Bem")

# 5. Macro-Família
familias_disponiveis = ["Todas as Famílias"] + sorted(df["Macro_Familia"].unique().tolist())
familia_selecionada = st.sidebar.selectbox("Macro-Família:", familias_disponiveis)

# 6. Tipo do Bem (Dependente da Família)
df_escopo_tipo = df.copy()
if familia_selecionada != "Todas as Famílias":
    df_escopo_tipo = df_escopo_tipo[df_escopo_tipo["Macro_Familia"] == familia_selecionada]

tipos_lista = ["Todos os Tipos"] + sorted(df_escopo_tipo["Tipo_Bem"].unique().tolist())
tipo_selecionado = st.sidebar.selectbox("Tipo de Bem:", tipos_lista)

# 7. Subtipo / Variação (Dependente do Tipo)
df_escopo_subtipo = df_escopo_tipo.copy()
if tipo_selecionado != "Todos os Tipos":
    df_escopo_subtipo = df_escopo_subtipo[df_escopo_subtipo["Tipo_Bem"] == tipo_selecionado]

subtipos_lista = ["Todos os Subtipos"] + sorted(df_escopo_subtipo["Subtipo"].unique().tolist())
subtipo_selecionado = st.sidebar.selectbox("Variação / Subtipo:", subtipos_lista)

st.sidebar.markdown("---")
# 8. Status
status_lista = ["Todos os Status"] + sorted(df["Status"].unique().tolist())
status_selecionado = st.sidebar.selectbox("Situação / Status:", status_lista)

# ----------------------------------------------------
# 7. FILTRAGEM DO DATAFRAME
# ----------------------------------------------------
df_filtrado = df.copy()

if termo_busca:
    df_filtrado = df_filtrado[
        df_filtrado["Tombamento"].str.contains(termo_busca, case=False, na=False) |
        df_filtrado["Tombamento_Anterior"].str.contains(termo_busca, case=False, na=False) |
        df_filtrado["Descricao"].str.contains(termo_busca, case=False, na=False)
    ]

if base_selecionada != "Todas as Bases":
    df_filtrado = df_filtrado[df_filtrado["Base"] == base_selecionada]

if depto_selecionado != "Todos os Departamentos":
    df_filtrado = df_filtrado[df_filtrado["Departamento"] == depto_selecionado]

if unidade_selecionada != "Todas as Unidades":
    df_filtrado = df_filtrado[df_filtrado["Unidade"] == unidade_selecionada]

if familia_selecionada != "Todas as Famílias":
    df_filtrado = df_filtrado[df_filtrado["Macro_Familia"] == familia_selecionada]

if tipo_selecionado != "Todos os Tipos":
    df_filtrado = df_filtrado[df_filtrado["Tipo_Bem"] == tipo_selecionado]

if subtipo_selecionado != "Todos os Subtipos":
    df_filtrado = df_filtrado[df_filtrado["Subtipo"] == subtipo_selecionado]

if status_selecionado != "Todos os Status":
    df_filtrado = df_filtrado[df_filtrado["Status"] == status_selecionado]

# ----------------------------------------------------
# 8. CARDS DE INDICADORES (KPIs)
# ----------------------------------------------------
qtd_total = len(df_filtrado)
valor_total = df_filtrado["Valor_Contabil"].sum()
ticket_medio = (valor_total / qtd_total) if qtd_total > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)

col1.metric("Quantidade de Bens", f"{qtd_total:,}".replace(",", "."))
col2.metric("Valor Patrimonial Total", f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col3.metric("Ticket Médio Contábil", f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

filtros_ativos = bool(
    termo_busca or 
    base_selecionada != "Todas as Bases" or 
    depto_selecionado != "Todos os Departamentos" or 
    unidade_selecionada != "Todas as Unidades" or 
    familia_selecionada != "Todas as Famílias" or 
    tipo_selecionado != "Todos os Tipos" or 
    subtipo_selecionado != "Todos os Subtipos" or 
    status_selecionado != "Todos os Status"
)
col4.metric("Status dos Filtros", "🔵 Filtro(s) Ativo(s)" if filtros_ativos else "⚪ Base Completa")

st.divider()

# ----------------------------------------------------
# 9. ABAS DE VISUALIZAÇÃO E ANÁLISE
# ----------------------------------------------------
tab_resultados, tab_distribuicao, tab_ficha = st.tabs([
    "📋 Itens Pesquisados",
    "📊 Resumos & Gráficos",
    "🔍 Ficha Individual do Bem"
])

with tab_resultados:
    st.subheader(f"Registros Localizados ({qtd_total})")

    if qtd_total > 0:
        df_exibicao = df_filtrado.copy()
        df_exibicao["Valor_Formatado"] = df_exibicao["Valor_Contabil"].apply(
            lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        colunas_tabela = [
            "Tombamento", "Tombamento_Anterior", "Descricao", "Macro_Familia",
            "Tipo_Bem", "Subtipo", "Departamento", "Unidade", "Status", "Valor_Formatado"
        ]

        st.dataframe(
            df_exibicao[colunas_tabela].rename(columns={
                "Tombamento": "Nº Atual",
                "Tombamento_Anterior": "Nº Anterior",
                "Descricao": "Descrição do Bem",
                "Macro_Familia": "Família",
                "Tipo_Bem": "Tipo",
                "Subtipo": "Subtipo/Variação",
                "Departamento": "Departamento",
                "Unidade": "Unidade de Guarda",
                "Status": "Situação",
                "Valor_Formatado": "Valor Contábil"
            }),
            use_container_width=True,
            hide_index=True
        )

        # Exportação CSV
        csv_download = df_filtrado.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Baixar Dados Filtrados (CSV)",
            data=csv_download,
            file_name="consulta_patrimonial_seapi.csv",
            mime="text/csv"
        )
    else:
        st.warning("Nenhum bem patrimonial encontrado para a combinação de filtros selecionada.")

with tab_distribuicao:
    if qtd_total > 0:
        c_g1, c_g2 = st.columns(2)

        with c_g1:
            st.subheader("Distribuição por Tipo de Bem")
            agrup_tipo = df_filtrado.groupby("Tipo_Bem")["Valor_Contabil"].agg(["count", "sum"]).reset_index()
            agrup_tipo.columns = ["Tipo do Bem", "Quantidade", "Valor Total (R$)"]
            agrup_tipo = agrup_tipo.sort_values(by="Quantidade", ascending=False).head(10)
            st.dataframe(agrup_tipo, use_container_width=True, hide_index=True)
            st.bar_chart(agrup_tipo.set_index("Tipo do Bem")["Quantidade"])

        with c_g2:
            st.subheader("Distribuição por Departamento Oficial")
            agrup_dep = df_filtrado.groupby("Departamento")["Valor_Contabil"].agg(["count", "sum"]).reset_index()
            agrup_dep.columns = ["Departamento", "Quantidade", "Valor Total (R$)"]
            agrup_dep = agrup_dep.sort_values(by="Quantidade", ascending=False)
            st.dataframe(agrup_dep, use_container_width=True, hide_index=True)
            st.bar_chart(agrup_dep.set_index("Departamento")["Quantidade"])
    else:
        st.info("Sem dados para exibição de resumos analíticos.")

with tab_ficha:
    st.subheader("Consulta Detalhada por Tombamento")
    tomb_busca = st.text_input("Digite o Número de Tombamento (Atual ou Anterior):", placeholder="Ex: 203388").strip()

    if tomb_busca:
        registro = df[
            (df["Tombamento"] == tomb_busca) |
            (df["Tombamento_Anterior"] == tomb_busca)
        ]
        if not registro.empty:
            item = registro.iloc[0]
            st.success(f"Bem Localizado: **{item['Tombamento']} - {item['Descricao']}**")

            f1, f2 = st.columns(2)
            with f1:
                st.write(f"**Nº Tombamento Atual:** {item['Tombamento']}")
                st.write(f"**Nº Patrimônio Anterior:** {item['Tombamento_Anterior'] if item['Tombamento_Anterior'] else 'Não Informado'}")
                st.write(f"**Macro-Família:** {item['Macro_Familia']}")
                st.write(f"**Tipo / Subtipo:** {item['Tipo_Bem']} ({item['Subtipo']})")
                st.write(f"**Departamento Oficial:** {item['Departamento']}")
                st.write(f"**Unidade de Guarda:** {item['Unidade']}")
            with f2:
                st.write(f"**Base de Origem:** {item['Base']}")
                st.write(f"**Data de Incorporação:** {item['Data_Incorp']}")
                st.write(f"**Situação / Status:** {item['Status']}")
                st.write(f"**Responsável / Titular:** {item['Responsavel']}")
                st.write(f"**Valor Contábil:** R$ {item['Valor_Contabil']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        else:
            st.error(f"Nenhum registro localizado com o tombamento '{tomb_busca}'.")
