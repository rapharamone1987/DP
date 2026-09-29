import streamlit as st
import pandas as pd
import numpy as np
import re
import io
from datetime import datetime

# Bibliotecas de Gráficos e PDF
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ----------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA & CSS ADAPTATIVO (COLOR-MIX)
# ----------------------------------------------------
st.set_page_config(
    page_title="Sistema Integrado de Consulta Patrimonial - SEAPI/RS",
    page_icon="🏛️",
    layout="wide"
)

# Estilização adaptativa via color-mix combinando tons institucionais da SEAPI
st.markdown("""
<style>
    /* ==========================================================
       CSS ADAPTATIVO NATIVO:
       Usa a cor de fundo do tema ativo misturada com verde SEAPI
       ========================================================== */
    
    /* Fundo da aplicação: tonalidade de verde sobre o fundo atual */
    .stApp {
        background-color: color-mix(in srgb, #1E4D2B 7%, var(--background-color)) !important;
        color: var(--text-color) !important;
    }

    /* Barra lateral com verde ligeiramente mais acentuado */
    [data-testid="stSidebar"] {
        background-color: color-mix(in srgb, #1E4D2B 14%, var(--secondary-background-color)) !important;
        border-right: 1px solid color-mix(in srgb, #1E4D2B 25%, var(--border-color, #CCCCCC)) !important;
    }

    /* Banner Superior Institucional (Verde executivo elegante) */
    .header-box {
        background: linear-gradient(135deg, #1A4726 0%, #0F2B17 100%);
        color: #FFFFFF !important;
        padding: 22px 28px;
        border-radius: 12px;
        margin-bottom: 22px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.18);
        border: 1px solid #2D6B3E;
    }
    .header-box h1 {
        color: #FFFFFF !important;
        margin: 0;
        font-size: 24px;
        font-weight: 700;
        letter-spacing: -0.3px;
    }
    .header-box p {
        color: #CBE3CE !important;
        margin: 5px 0 0 0;
        font-size: 13px;
    }

    /* Cards de Métricas / KPIs que se adaptam perfeitamente */
    .metric-card {
        background-color: color-mix(in srgb, #1E4D2B 10%, var(--secondary-background-color)) !important;
        color: var(--text-color) !important;
        border-radius: 10px;
        padding: 13px 17px;
        border-left: 5px solid #2E7D32 !important;
        border-top: 1px solid color-mix(in srgb, #1E4D2B 20%, var(--border-color, #CCCCCC)) !important;
        border-right: 1px solid color-mix(in srgb, #1E4D2B 20%, var(--border-color, #CCCCCC)) !important;
        border-bottom: 1px solid color-mix(in srgb, #1E4D2B 20%, var(--border-color, #CCCCCC)) !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        margin-bottom: 10px;
    }
    .metric-card .title {
        font-size: 11px;
        font-weight: 600;
        color: var(--text-color) !important;
        opacity: 0.8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-card .value {
        font-size: 21px;
        font-weight: 700;
        color: color-mix(in srgb, #2E7D32 75%, var(--text-color)) !important;
        margin-top: 2px;
    }
    .metric-card .subtitle {
        font-size: 10.5px;
        color: var(--text-color) !important;
        opacity: 0.7;
        margin-top: 2px;
    }

    /* Abas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        border-bottom: 1px solid color-mix(in srgb, #1E4D2B 20%, var(--border-color, #CCCCCC));
    }
    .stTabs [aria-selected="true"] {
        color: color-mix(in srgb, #2E7D32 80%, var(--text-color)) !important;
        font-weight: bold;
        border-bottom: 3px solid #2E7D32 !important;
    }

    /* Tabelas e Dataframes */
    [data-testid="stDataFrame"] {
        background-color: color-mix(in srgb, #1E4D2B 8%, var(--secondary-background-color)) !important;
        border-radius: 8px;
        border: 1px solid color-mix(in srgb, #1E4D2B 20%, var(--border-color, #CCCCCC));
    }
</style>
""", unsafe_allow_html=True)

SPREADSHEET_ID = "1cnQTahu9K3UGLtmE8pdc8EnbyUxPdB2POdm3csRhZwg"

# ----------------------------------------------------
# 2. FUNÇÕES DE PROCESSAMENTO E CLASSIFICAÇÃO
# ----------------------------------------------------
def converter_moeda_br(coluna):
    """Converte 'R$ 1.234,56' para float."""
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
    """Classifica a descrição em (Macro_Familia, Tipo_Bem, Subtipo)."""
    desc = str(descricao).upper().strip()

    # CADEIRAS E ASSENTOS
    if re.search(r"\b(CADEIRA|POLTRONA|LONGARINA|BANQUETA|BANCO)\b", desc):
        familia = "Mobiliário em Geral"
        tipo = "Cadeiras"

        if re.search(r"\b(RODIZIO|RODÍZIO|GIRATORIA|GIRATÓRIA|RODAS|RODINHAS)\b", desc):
            subtipo = "Giratória / Rodízio"
        elif re.search(r"\b(FIXA|FIXO|4 PES|4 PÉS|APROXIMACAO|APROXIMAÇÃO|INTERLOCUTOR)\b", desc):
            subtipo = "Fixa"
        elif "LONGARINA" in desc:
            subtipo = "Longarina"
        elif "POLTRONA" in desc:
            subtipo = "Poltrona Executiva"
        else:
            subtipo = "Não Especificado"
        return familia, tipo, subtipo

    # ARMÁRIOS E ARQUIVOS
    if re.search(r"\b(ARMARIO|ARMÁRIO|ARQUIVO|ROUPEIRO)\b", desc):
        familia = "Mobiliário em Geral"
        tipo = "Armários"
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

    # MESAS
    if re.search(r"\b(MESA|ESTACAO DE TRABALHO|ESTAÇÃO DE TRABALHO|ESCRIVANINHA)\b", desc):
        familia = "Mobiliário em Geral"
        tipo = "Mesas"
        if re.search(r"\b(REUNIAO|REUNIÃO)\b", desc):
            subtipo = "Reunião"
        elif re.search(r"\b(EM L|ANGULAR|CANTO)\b", desc):
            subtipo = "Em L / Canto"
        elif re.search(r"\b(RETA|ESCRITORIO|ESCRITÓRIO|DIGITADOR)\b", desc):
            subtipo = "Reta / Operacional"
        else:
            subtipo = "Não Especificado"
        return familia, tipo, subtipo

    # INFORMÁTICA
    if re.search(r"\b(NOTEBOOK|LAPTOP)\b", desc):
        return "Informática & TI", "Notebooks", "Notebook"
    if re.search(r"\b(MICROCOMPUTADOR|COMPUTADOR|DESKTOP|CPU|SERVIDOR)\b", desc):
        subtipo = "Servidor" if "SERVIDOR" in desc else "Desktop"
        return "Informática & TI", "Computador", subtipo
    if re.search(r"\b(MONITOR|TELA|DISPLAY)\b", desc):
        return "Informática & TI", "Monitores", "Não Especificado"
    if re.search(r"\b(IMPRESSORA|MULTIFUNCIONAL|PLOTTER|SCANNER)\b", desc):
        subtipo = "Multifuncional" if "MULTIFUNCIONAL" in desc else "Impressora"
        return "Informática & TI", "Impressora", subtipo
    if re.search(r"\b(NOBREAK|NO-BREAK|ESTABILIZADOR|TECLADO|MOUSE|PERIFERICO)\b", desc):
        return "Informática & TI", "Periféricos", "Não Especificado"

    # VEÍCULOS & MÁQUINAS
    if re.search(r"\b(CAMINHONETE|CAMIONETE|PICKUP|CAMINHAO|CAMINHÃO)\b", desc):
        subtipo = "Caminhão" if "CAMINH" in desc else "Caminhonete"
        return "Veículos & Transporte", "Veículos", subtipo
    if re.search(r"\b(AUTOMOVEL|AUTOMÓVEL|CARRO|VEICULO|VEÍCULO)\b", desc):
        return "Veículos & Transporte", "Veículos", "Passeio"
    if re.search(r"\b(TRATOR|RETROESCAVADEIRA|COLHEITADEIRA|PULVERIZADOR|SEMEADORA)\b", desc):
        return "Maquinário & Equip. Agrícolas", "Máquina Agrícola", "Pesada / Implemento"

    # CLIMATIZAÇÃO
    if re.search(r"\b(CONDICIONADOR DE AR|AR CONDICIONADO|SPLIT|VENTILADOR)\b", desc):
        return "Climatização & Eletro", "Climatização", "Climatizador / Split"
    if re.search(r"\b(REFRIGERADOR|GELADEIRA|FREEZER|BEBEDOURO|MICRO-ONDAS|CAFETEIRA)\b", desc):
        return "Climatização & Eletro", "Eletrodomésticos", "Padrão"

    return "Outros / Diversos", "Outros", "Não Especificado"

def calcular_idade_anos(data_str):
    """Extrai ano de incorporação e calcula a idade em anos."""
    if not data_str or str(data_str).strip() in ["nan", "None", ""]:
        return np.nan
    ano_match = re.search(r"(19\d{2}|20\d{2})", str(data_str))
    if ano_match:
        ano = int(ano_match.group(1))
        ano_atual = datetime.now().year
        idade = ano_atual - ano
        return max(0, idade)
    return np.nan

def classificar_faixa_etaria(idade):
    """Categoriza a idade do acervo em faixas do ciclo de vida."""
    if pd.isna(idade):
        return "Não Informado"
    if idade <= 2:
        return "0 a 2 anos (Novos)"
    elif idade <= 5:
        return "3 a 5 anos (Intermediários)"
    elif idade <= 10:
        return "6 a 10 anos (Amortizados)"
    else:
        return "Mais de 10 anos (Históricos)"

# ----------------------------------------------------
# 3. CARREGAMENTO DOS DADOS COM CACHE
# ----------------------------------------------------
@st.cache_data(ttl=600)
def carregar_aba(sheet_name: str):
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    return pd.read_csv(url, dtype=str)

@st.cache_data(ttl=600)
def carregar_dados_sistema():
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
        match_cod = re.search(r"0*([1-9]\d{4})", txt)
        if match_cod:
            cod_5d = match_cod.group(1)
            if cod_5d in mapa_por_codigo:
                return mapa_por_codigo[cod_5d]

        txt_sem_prefixo = re.sub(r"^UNIDADE:\s*", "", txt)
        txt_sem_prefixo = re.sub(r"^ECC\.\d+\.\d+\s*-\s*", "", txt_sem_prefixo).strip()
        for nome_ref, depto_ref in mapa_por_nome.items():
            if nome_ref in txt_sem_prefixo or txt_sem_prefixo in nome_ref:
                return depto_ref

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

    # Base Termos de Responsabilidade
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

    # Base Bens Cedidos
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

    # Base Bens Não Localizados
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

    df_total = pd.concat([df_termos, df_cedidos, df_nao_loc], ignore_index=True)
    df_total["Departamento"] = df_total["Unidade_Raw"].apply(identificar_departamento)

    classificacoes = df_total["Descricao"].apply(classificar_bem_patrimonial)
    df_total["Macro_Familia"] = [c[0] for c in classificacoes]
    df_total["Tipo_Bem"] = [c[1] for c in classificacoes]
    df_total["Subtipo"] = [c[2] for c in classificacoes]

    df_total["Idade_Anos"] = df_total["Data_Incorp"].apply(calcular_idade_anos)
    df_total["Faixa_Etaria"] = df_total["Idade_Anos"].apply(classificar_faixa_etaria)

    return df_total

# ----------------------------------------------------
# 4. CARREGAMENTO DOS DADOS NO APP
# ----------------------------------------------------
with st.spinner("Conectando ao Google Sheets e consolidando acervo patrimonial..."):
    try:
        df = carregar_dados_sistema()
    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha: {e}")
        st.stop()

TOTAL_BENS_GERAL = len(df)
TOTAL_VALOR_GERAL = df["Valor_Contabil"].sum()

# ----------------------------------------------------
# 5. HEADER INSTITUCIONAL SEAPI
# ----------------------------------------------------
st.markdown("""
<div class="header-box">
    <h1>🏛️ Sistema Integrado de Consulta e Pesquisa Patrimonial</h1>
    <p>Secretaria da Agricultura, Pecuária, Produção Sustentável e Irrigação • Estado do Rio Grande do Sul</p>
</div>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# 6. BARRA LATERAL COM FILTROS MULTISSELEÇÃO
# ----------------------------------------------------
st.sidebar.header("🔍 Painel de Filtros")

termo_busca = st.sidebar.text_input(
    "Nº Tombamento ou Descrição:",
    placeholder="Ex: 203388, Cadeira, Hilux..."
).strip()

bases_disponiveis = sorted(df["Base"].unique().tolist())
bases_selecionadas = st.sidebar.multiselect("Base de Dados:", bases_disponiveis, placeholder="Todas as bases")

st.sidebar.markdown("---")
st.sidebar.subheader("🏢 Localização & Lotação")

deptos_disponiveis = sorted(df["Departamento"].unique().tolist())
deptos_selecionados = st.sidebar.multiselect("Departamento Oficial:", deptos_disponiveis, placeholder="Todos os departamentos")

df_escopo_unidade = df.copy()
if deptos_selecionados:
    df_escopo_unidade = df_escopo_unidade[df_escopo_unidade["Departamento"].isin(deptos_selecionados)]

unidades_lista = sorted([u for u in df_escopo_unidade["Unidade"].unique() if u])
unidades_selecionadas = st.sidebar.multiselect("Unidade de Guarda / Local:", unidades_lista, placeholder="Todas as unidades")

st.sidebar.markdown("---")
st.sidebar.subheader("📦 Tipologia & Ciclo de Vida")

familias_disponiveis = sorted(df["Macro_Familia"].unique().tolist())
familias_selecionadas = st.sidebar.multiselect("Macro-Família:", familias_disponiveis, placeholder="Todas as famílias")

df_escopo_tipo = df.copy()
if familias_selecionadas:
    df_escopo_tipo = df_escopo_tipo[df_escopo_tipo["Macro_Familia"].isin(familias_selecionadas)]

tipos_lista = sorted(df_escopo_tipo["Tipo_Bem"].unique().tolist())
tipos_selecionados = st.sidebar.multiselect("Tipo de Bem:", tipos_lista, placeholder="Todos os tipos")

df_escopo_subtipo = df_escopo_tipo.copy()
if tipos_selecionados:
    df_escopo_subtipo = df_escopo_subtipo[df_escopo_subtipo["Tipo_Bem"].isin(tipos_selecionados)]

subtipos_lista = sorted(df_escopo_subtipo["Subtipo"].unique().tolist())
subtipos_selecionados = st.sidebar.multiselect("Subtipo / Variação:", subtipos_lista, placeholder="Todos os subtipos")

faixas_ordem = ["0 a 2 anos (Novos)", "3 a 5 anos (Intermediários)", "6 a 10 anos (Amortizados)", "Mais de 10 anos (Históricos)", "Não Informado"]
faixas_selecionadas = st.sidebar.multiselect("Faixa de Idade:", faixas_ordem, placeholder="Todas as faixas")

st.sidebar.markdown("---")
status_lista = ["Em Uso Direto", "Bens Cedidos", "Bens Não Localizados"]
status_selecionados = st.sidebar.multiselect("Alocação / Status:", status_lista, placeholder="Todos os status")

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
if bases_selecionadas:
    df_filtrado = df_filtrado[df_filtrado["Base"].isin(bases_selecionadas)]
if deptos_selecionados:
    df_filtrado = df_filtrado[df_filtrado["Departamento"].isin(deptos_selecionados)]
if unidades_selecionadas:
    df_filtrado = df_filtrado[df_filtrado["Unidade"].isin(unidades_selecionadas)]
if familias_selecionadas:
    df_filtrado = df_filtrado[df_filtrado["Macro_Familia"].isin(familias_selecionadas)]
if tipos_selecionados:
    df_filtrado = df_filtrado[df_filtrado["Tipo_Bem"].isin(tipos_selecionados)]
if subtipos_selecionados:
    df_filtrado = df_filtrado[df_filtrado["Subtipo"].isin(subtipos_selecionados)]
if faixas_selecionadas:
    df_filtrado = df_filtrado[df_filtrado["Faixa_Etaria"].isin(faixas_selecionadas)]
if status_selecionados:
    df_filtrado = df_filtrado[df_filtrado["Status"].isin(status_selecionados)]

# ----------------------------------------------------
# 8. CÁLCULO DAS MÉTRICAS E KPIS EXECUTIVOS
# ----------------------------------------------------
qtd_total = len(df_filtrado)
valor_total = df_filtrado["Valor_Contabil"].sum()
ticket_medio = (valor_total / qtd_total) if qtd_total > 0 else 0.0

idades_validas = df_filtrado["Idade_Anos"].dropna()
idade_media = idades_validas.mean() if not idades_validas.empty else 0.0

pct_bens_total = (qtd_total / TOTAL_BENS_GERAL * 100) if TOTAL_BENS_GERAL > 0 else 0.0
pct_valor_total = (valor_total / TOTAL_VALOR_GERAL * 100) if TOTAL_VALOR_GERAL > 0 else 0.0

# ----------------------------------------------------
# 9. EXIBIÇÃO DOS CARDS EM DUAS LINHAS
# ----------------------------------------------------
col_k1, col_k2, col_k3 = st.columns(3)
with col_k1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="title">Quantidade de Bens Filtrados</div>
        <div class="value">{qtd_total:,}</div>
        <div class="subtitle">Representa <b>{pct_bens_total:.2f}%</b> do acervo geral do Estado</div>
    </div>
    """.replace(",", "."), unsafe_allow_html=True)

with col_k2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="title">Valor Patrimonial Total</div>
        <div class="value">R$ {valor_total:,.2f}</div>
        <div class="subtitle">Representa <b>{pct_valor_total:.2f}%</b> do valor total da SEAPI</div>
    </div>
    """.replace(",", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

with col_k3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="title">Ticket Médio Contábil</div>
        <div class="value">R$ {ticket_medio:,.2f}</div>
        <div class="subtitle">Valor contábil médio por item</div>
    </div>
    """.replace(",", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

col_k4, col_k5, col_k6 = st.columns(3)
with col_k4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="title">Idade Média do Acervo</div>
        <div class="value">{idade_media:.1f} anos</div>
        <div class="subtitle">Tempo médio desde a incorporação</div>
    </div>
    """, unsafe_allow_html=True)

with col_k5:
    qtd_em_uso = len(df_filtrado[df_filtrado["Status"] == "Em Uso Direto"])
    qtd_cedidos = len(df_filtrado[df_filtrado["Status"] == "Bens Cedidos"])
    qtd_nao_loc = len(df_filtrado[df_filtrado["Status"] == "Bens Não Localizados"])
    st.markdown(f"""
    <div class="metric-card">
        <div class="title">Alocação Ativa</div>
        <div class="value" style="font-size: 15px; margin-top: 5px;">
            <span style="color:#2E7D32;"><b>Uso:</b> {qtd_em_uso:,}</span> | 
            <span style="color:#4CAF50;"><b>Ced.:</b> {qtd_cedidos:,}</span> | 
            <span style="color:#E53935;"><b>Não Loc.:</b> {qtd_nao_loc:,}</span>
        </div>
        <div class="subtitle">Distribuição por situação operacional</div>
    </div>
    """.replace(",", "."), unsafe_allow_html=True)

with col_k6:
    filtros_ativos = bool(termo_busca or bases_selecionadas or deptos_selecionados or unidades_selecionadas or familias_selecionadas or tipos_selecionados or subtipos_selecionados or faixas_selecionadas or status_selecionados)
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: {'#1976D2' if filtros_ativos else '#689F38'};">
        <div class="title">Escopo dos Filtros</div>
        <div class="value" style="color: {'#1976D2' if filtros_ativos else '#689F38'}; font-size: 16px; margin-top: 4px;">
            {'🔵 Filtros Personalizados' if filtros_ativos else '⚪ Base Integral (Sem Restrição)'}
        </div>
        <div class="subtitle">{f'{qtd_total:,} de {TOTAL_BENS_GERAL:,} bens totais'.replace(',', '.')}</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# ----------------------------------------------------
# 10. FUNÇÕES DE RENDERIZAÇÃO DE GRÁFICOS (MATPLOTLIB)
# ----------------------------------------------------
def gerar_grafico_donut_status(df_dados, para_pdf=False):
    status_counts = df_dados["Status"].value_counts()
    fig, ax = plt.subplots(figsize=(3.4, 2.7), dpi=200)
    color_map = {"Em Uso Direto": "#1E4D2B", "Bens Cedidos": "#4CAF50", "Bens Não Localizados": "#C62828"}
    cores = [color_map.get(s, "#888888") for s in status_counts.index]
    
    wedges, _ = ax.pie(
        status_counts.values,
        labels=None,
        colors=cores,
        startangle=90,
        wedgeprops=dict(width=0.45, edgecolor='white' if para_pdf else '#1A3322', linewidth=1.2)
    )
    
    ax.legend(
        wedges,
        [f"{s} ({v:,})".replace(",", ".") for s, v in zip(status_counts.index, status_counts.values)],
        loc="center",
        bbox_to_anchor=(0.5, -0.15),
        fontsize=6.5,
        frameon=False
    )
    
    ax.set_title("Distribuição por Alocação Ativa", fontsize=9, fontweight="bold", color="#1E4D2B" if para_pdf else "#2E7D32", pad=6)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=200, transparent=not para_pdf)
    plt.close(fig)
    buf.seek(0)
    return buf

def gerar_grafico_faixa_etaria(df_dados, para_pdf=False):
    ordem = ["0 a 2 anos (Novos)", "3 a 5 anos (Intermediários)", "6 a 10 anos (Amortizados)", "Mais de 10 anos (Históricos)", "Não Informado"]
    faixa_counts = df_dados["Faixa_Etaria"].value_counts().reindex(ordem).fillna(0)
    faixa_counts = faixa_counts[faixa_counts > 0]

    fig, ax = plt.subplots(figsize=(4.5, 2.7), dpi=200)
    barras = ax.bar(faixa_counts.index, faixa_counts.values, color="#2E693D", width=0.55)
    for bar in barras:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + (max(faixa_counts.values)*0.02), f"{int(h):,}".replace(",", "."), ha='center', va='bottom', fontsize=6.5, fontweight='bold', color="#13331C" if para_pdf else "#2E7D32")
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#888888')
    ax.spines['bottom'].set_color('#888888')
    ax.tick_params(axis='both', which='both', labelsize=6, colors="#333333" if para_pdf else "#555555")
    plt.xticks(rotation=15, ha='right')
    ax.set_title("Distribuição por Faixa Etária (Ciclo de Vida)", fontsize=9, fontweight="bold", color="#1E4D2B" if para_pdf else "#2E7D32", pad=6)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=200, transparent=not para_pdf)
    plt.close(fig)
    buf.seek(0)
    return buf

def gerar_grafico_barras_categorias(df_dados, para_pdf=False):
    cat_counts = df_dados["Tipo_Bem"].value_counts().head(8).sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(3.8, 2.7), dpi=200)
    barras = ax.barh(cat_counts.index, cat_counts.values, color="#1E4D2B" if para_pdf else "#2E7D32", height=0.55)
    for bar in barras:
        w = bar.get_width()
        ax.text(w + (max(cat_counts.values) * 0.02), bar.get_y() + bar.get_height()/2, f"{int(w):,}".replace(",", "."), va='center', ha='left', fontsize=6.5, fontweight='bold', color="#13331C" if para_pdf else "#2E7D32")
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#888888')
    ax.spines['bottom'].set_color('#888888')
    ax.tick_params(axis='both', which='both', labelsize=6.5, colors="#333333" if para_pdf else "#555555")
    ax.set_title("Top Tipos de Bens Filtrados", fontsize=9, fontweight="bold", color="#1E4D2B" if para_pdf else "#2E7D32", pad=6)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=200, transparent=not para_pdf)
    plt.close(fig)
    buf.seek(0)
    return buf

# ----------------------------------------------------
# 11. GERAÇÃO DO RELATÓRIO PDF EXECUTIVO
# ----------------------------------------------------
def gerar_dashboard_pdf_oficial(df_dados, filtros_desc):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=25,
        rightMargin=25,
        topMargin=20,
        bottomMargin=20
    )

    elementos = []
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle('DocTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, textColor=colors.HexColor('#1E4D2B'), spaceAfter=2)
    sub_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#555555'), spaceAfter=6)
    secao_style = ParagraphStyle('SectionTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#1E4D2B'), spaceBefore=6, spaceAfter=4)

    # 1. Cabeçalho
    elementos.append(Paragraph("PAINEL EXECUTIVO DE GESTÃO PATRIMONIAL", titulo_style))
    elementos.append(Paragraph(
        f"Secretaria da Agricultura, Pecuária, Produção Sustentável e Irrigação • SEAPI/RS | Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        sub_style
    ))
    elementos.append(Paragraph(f"<b>Filtros Ativos:</b> {filtros_desc}", ParagraphStyle('Filtros', fontSize=7, textColor=colors.HexColor('#333333'))))
    elementos.append(Spacer(1, 6))

    # 2. Scorecard Executivo (KPIs em 2 linhas)
    qtd_t = len(df_dados)
    val_t = df_dados["Valor_Contabil"].sum()
    pct_b = (qtd_t / TOTAL_BENS_GERAL * 100) if TOTAL_BENS_GERAL > 0 else 0
    pct_v = (val_t / TOTAL_VALOR_GERAL * 100) if TOTAL_VALOR_GERAL > 0 else 0
    id_med = df_dados["Idade_Anos"].dropna().mean() if not df_dados["Idade_Anos"].dropna().empty else 0.0

    kpi_headers = ["QUANTIDADE FILTRADA", "% ACERVO GERAL", "VALOR PATRIMONIAL", "% VALOR TOTAL", "TICKET MÉDIO", "IDADE MÉDIA"]
    kpi_valores = [
        f"{qtd_t:,}".replace(",", "."),
        f"{pct_b:.2f}%",
        f"R$ {val_t:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        f"{pct_v:.2f}%",
        f"R$ {(val_t/qtd_t if qtd_t>0 else 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        f"{id_med:.1f} anos"
    ]

    t_kpi = Table([kpi_headers, kpi_valores], colWidths=[125, 125, 130, 125, 125, 120])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E4D2B')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 7),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#F4F8F4')),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,1), (-1,1), 10),
        ('TEXTCOLOR', (0,1), (-1,1), colors.HexColor('#1E4D2B')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#1E4D2B')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#DCE8DD')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elementos.append(t_kpi)
    elementos.append(Spacer(1, 8))

    # 3. Bloco de Gráficos Superiores
    buf_donut = gerar_grafico_donut_status(df_dados, para_pdf=True)
    buf_idade = gerar_grafico_faixa_etaria(df_dados, para_pdf=True)
    buf_cat = gerar_grafico_barras_categorias(df_dados, para_pdf=True)

    img_donut = Image(buf_donut, width=230, height=150)
    img_idade = Image(buf_idade, width=280, height=150)
    img_cat = Image(buf_cat, width=235, height=150)

    linha_graficos = Table([[img_donut, img_idade, img_cat]], colWidths=[240, 285, 245])
    linha_graficos.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    elementos.append(linha_graficos)
    elementos.append(Spacer(1, 6))

    # 4. Matriz Cruzada: Faixa Etária vs. Tipo de Bem
    elementos.append(Paragraph("Distribuição Cruzada: Faixa Etária (Ciclo de Vida) vs. Tipo de Bem", secao_style))
    top_tipos = df_dados["Tipo_Bem"].value_counts().head(6).index.tolist()
    df_cruz = df_dados[df_dados["Tipo_Bem"].isin(top_tipos)]
    crosstab_res = pd.crosstab(df_cruz["Tipo_Bem"], df_cruz["Faixa_Etaria"]).fillna(0).astype(int)

    colunas_matriz = ["Tipo de Bem"] + [c for c in faixas_ordem if c in crosstab_res.columns] + ["Total"]
    linhas_matriz = [colunas_matriz]
    for tipo_item, r in crosstab_res.iterrows():
        linha = [str(tipo_item)]
        total_linha = 0
        for col_f in colunas_matriz[1:-1]:
            val = r.get(col_f, 0)
            linha.append(f"{val:,}".replace(",", "."))
            total_linha += val
        linha.append(f"{total_linha:,}".replace(",", "."))
        linhas_matriz.append(linha)

    t_matriz = Table(linhas_matriz, colWidths=[170] + [95]*(len(colunas_matriz)-2) + [85])
    t_matriz.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2E693D')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 6.5),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FBF9')])
    ]))
    elementos.append(t_matriz)

    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

# ----------------------------------------------------
# 12. ABAS DE NAVEGAÇÃO E ANÁLISE INTERATIVA
# ----------------------------------------------------
tab_dash, tab_cruzada, tab_itens, tab_pdf, tab_ficha = st.tabs([
    "📊 Painel Executivo / Dashboard",
    "🔄 Análise Cruzada (Idade x Tipo)",
    "📋 Itens Pesquisados",
    "📄 Gerar Dashboard em PDF",
    "🔍 Ficha Individual do Bem"
])

# ABA 1: DASHBOARD
with tab_dash:
    if qtd_total > 0:
        c1, c2, c3 = st.columns([1, 1.2, 1])
        with c1:
            st.subheader("Alocação Ativa")
            st.image(gerar_grafico_donut_status(df_filtrado, para_pdf=False), use_container_width=True)

        with c2:
            st.subheader("Ciclo de Vida (Faixa Etária)")
            st.image(gerar_grafico_faixa_etaria(df_filtrado, para_pdf=False), use_container_width=True)

        with c3:
            st.subheader("Top Tipos de Bens")
            st.image(gerar_grafico_barras_categorias(df_filtrado, para_pdf=False), use_container_width=True)

        st.divider()
        st.subheader("Distribuição por Departamento Oficial")
        agrup_dep = df_filtrado.groupby("Departamento")["Valor_Contabil"].agg(["count", "sum"]).reset_index()
        agrup_dep.columns = ["Departamento", "Qtd. Bens", "Valor Total (R$)"]
        agrup_dep["% Participação"] = (agrup_dep["Qtd. Bens"] / qtd_total * 100).apply(lambda p: f"{p:.1f}%")
        agrup_dep = agrup_dep.sort_values(by="Qtd. Bens", ascending=False)
        st.dataframe(agrup_dep, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum registro encontrado para alimentar o painel executivo.")

# ABA 2: ANÁLISE CRUZADA
with tab_cruzada:
    st.subheader("Matriz Cruzada: Faixa Etária vs. Tipo de Bem")
    if qtd_total > 0:
        st.write("##### Quantidade de Bens por Faixa de Idade")
        df_count = pd.crosstab(df_filtrado["Tipo_Bem"], df_filtrado["Faixa_Etaria"], margins=True, margins_name="Total")
        st.dataframe(df_count, use_container_width=True)

        st.write("##### Distribuição Visual Proporcional")
        crosstab_plot = pd.crosstab(df_filtrado["Tipo_Bem"], df_filtrado["Faixa_Etaria"])
        top_plot = crosstab_plot.loc[df_filtrado["Tipo_Bem"].value_counts().head(8).index]
        st.bar_chart(top_plot)
    else:
        st.info("Sem dados suficientes para cruzamento.")

# ABA 3: ITENS PESQUISADOS
with tab_itens:
    st.subheader(f"Registros Localizados ({qtd_total})")
    if qtd_total > 0:
        df_exibicao = df_filtrado.copy()
        df_exibicao["Valor_Formatado"] = df_exibicao["Valor_Contabil"].apply(
            lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
        colunas_tabela = [
            "Tombamento", "Tombamento_Anterior", "Descricao", "Macro_Familia",
            "Tipo_Bem", "Subtipo", "Faixa_Etaria", "Departamento", "Unidade", "Status", "Valor_Formatado"
        ]
        st.dataframe(
            df_exibicao[colunas_tabela].rename(columns={
                "Tombamento": "Nº Atual",
                "Tombamento_Anterior": "Nº Anterior",
                "Descricao": "Descrição do Bem",
                "Macro_Familia": "Família",
                "Tipo_Bem": "Tipo",
                "Subtipo": "Subtipo",
                "Faixa_Etaria": "Faixa Etária",
                "Departamento": "Departamento",
                "Unidade": "Unidade de Guarda",
                "Status": "Situação",
                "Valor_Formatado": "Valor Contábil"
            }),
            use_container_width=True,
            hide_index=True
        )

        csv_download = df_filtrado.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Exportar Dados para CSV",
            data=csv_download,
            file_name="consulta_patrimonial_seapi.csv",
            mime="text/csv"
        )
    else:
        st.warning("Nenhum bem patrimonial localizado para os filtros informados.")

# ABA 4: EXPORTAÇÃO PDF
with tab_pdf:
    st.subheader("Gerador de Dashboard Executivo Oficial (PDF)")
    st.write("Gere um documento executivo em PDF no formato paisagem contendo todos os indicadores de representatividade, idade média, ciclo de vida e matriz cruzada de bens.")

    texto_filtros = []
    if termo_busca: texto_filtros.append(f"Busca: '{termo_busca}'")
    if deptos_selecionados: texto_filtros.append(f"Deptos: {', '.join(deptos_selecionados)}")
    if unidades_selecionadas: texto_filtros.append(f"Unidades: {len(unidades_selecionadas)} selecionada(s)")
    if familias_selecionadas: texto_filtros.append(f"Famílias: {', '.join(familias_selecionadas)}")
    if tipos_selecionados: texto_filtros.append(f"Tipos: {', '.join(tipos_selecionados)}")
    if faixas_selecionadas: texto_filtros.append(f"Faixas: {', '.join(faixas_selecionadas)}")
    if status_selecionados: texto_filtros.append(f"Status: {', '.join(status_selecionados)}")
    desc_final = " | ".join(texto_filtros) if texto_filtros else "Base Completa (Sem restrições)"

    if qtd_total > 0:
        if st.button("📄 Gerar e Compilar Dashboard em PDF"):
            with st.spinner("Compilando gráficos vetoriais, cálculos de representatividade e matriz cruzada..."):
                pdf_bytes = gerar_dashboard_pdf_oficial(df_filtrado, desc_final)
                st.success("Dashboard PDF gerado com sucesso!")
                st.download_button(
                    label="⬇️ Baixar Dashboard Executivo em PDF",
                    data=pdf_bytes,
                    file_name=f"Dashboard_Executivo_SEAPI_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf"
                )
    else:
        st.warning("Não há dados filtrados para gerar o relatório em PDF.")

# ABA 5: FICHA INDIVIDUAL
with tab_ficha:
    st.subheader("Consulta de Ficha Individual de Tombamento")
    tomb_busca = st.text_input("Informe o Número de Tombamento (Atual ou Anterior):", placeholder="Ex: 203388").strip()

    if tomb_busca:
        registro = df[(df["Tombamento"] == tomb_busca) | (df["Tombamento_Anterior"] == tomb_busca)]
        if not registro.empty:
            item = registro.iloc[0]
            st.success(f"Bem Localizado: **{item['Tombamento']} - {item['Descricao']}**")
            f1, f2 = st.columns(2)
            with f1:
                st.write(f"**Nº Tombamento Atual:** {item['Tombamento']}")
                st.write(f"**Nº Patrimônio Anterior:** {item['Tombamento_Anterior'] if item['Tombamento_Anterior'] else 'Não Informado'}")
                st.write(f"**Macro-Família:** {item['Macro_Familia']}")
                st.write(f"**Tipo / Subtipo:** {item['Tipo_Bem']} ({item['Subtipo']})")
                st.write(f"**Faixa Etária / Ciclo:** {item['Faixa_Etaria']} ({item['Idade_Anos']:.0f} anos)" if not pd.isna(item['Idade_Anos']) else "**Faixa Etária:** Não Informada")
                st.write(f"**Departamento Oficial:** {item['Departamento']}")
                st.write(f"**Unidade de Guarda:** {item['Unidade']}")
            with f2:
                st.write(f"**Base de Origem:** {item['Base']}")
                st.write(f"**Data de Incorporação:** {item['Data_Incorp']}")
                st.write(f"**Situação / Status:** {item['Status']}")
                st.write(f"**Responsável / Titular:** {item['Responsavel']}")
                st.write(f"**Valor Contábil:** R$ {item['Valor_Contabil']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        else:
            st.error(f"Nenhum registro localizado para o tombamento '{tomb_busca}'.")
