import streamlit as st
import pandas as pd
import re
import io
from datetime import datetime

# ReportLab para geração de PDF
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ----------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA & CSS INSTITUCIONAL
# ----------------------------------------------------
st.set_page_config(
    page_title="Sistema Integrado de Consulta Patrimonial - SEAPI/RS",
    page_icon="🏛️",
    layout="wide"
)

# Estilização visual inspirada na identidade SEAPI
st.markdown("""
<style>
    /* Cor primária institucional */
    :root {
        --seapi-green: #1E4D2B;
        --seapi-dark: #13331C;
        --seapi-light: #F4F8F4;
    }
    
    /* Top banner */
    .header-box {
        background: linear-gradient(135deg, #1E4D2B 0%, #13331C 100%);
        color: white;
        padding: 24px;
        border-radius: 12px;
        margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    .header-box h1 {
        color: #FFFFFF !important;
        margin: 0;
        font-size: 26px;
        font-weight: 700;
    }
    .header-box p {
        color: #DCE8DD;
        margin: 6px 0 0 0;
        font-size: 14px;
    }

    /* Cards de Métricas / KPIs */
    .kpi-container {
        display: flex;
        gap: 15px;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #FFFFFF;
        border-radius: 10px;
        padding: 16px 20px;
        border-left: 5px solid #1E4D2B;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        border-top: 1px solid #EAEAEA;
        border-right: 1px solid #EAEAEA;
        border-bottom: 1px solid #EAEAEA;
    }
    .metric-card .title {
        font-size: 12px;
        font-weight: 600;
        color: #555555;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-card .value {
        font-size: 24px;
        font-weight: 700;
        color: #1E4D2B;
        margin-top: 4px;
    }
    .metric-card .subtitle {
        font-size: 11px;
        color: #888888;
        margin-top: 3px;
    }
</style>
""", unsafe_allow_html=True)

SPREADSHEET_ID = "1cnQTahu9K3UGLtmE8pdc8EnbyUxPdB2POdm3csRhZwg"

# ----------------------------------------------------
# 2. FUNÇÕES DE PROCESSAMENTO E CLASSIFICAÇÃO
# ----------------------------------------------------
def converter_moeda_br(coluna):
    """Converte formato 'R$ 1.234,56' para float."""
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

    # ARMÁRIOS E ARQUIVOS
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

    # MESAS
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

    # INFORMÁTICA
    if re.search(r"\b(NOTEBOOK|LAPTOP)\b", desc):
        return "Informática & TI", "Computador", "Notebook"
    if re.search(r"\b(MICROCOMPUTADOR|COMPUTADOR|DESKTOP|CPU|SERVIDOR)\b", desc):
        subtipo = "Servidor" if "SERVIDOR" in desc else "Desktop"
        return "Informática & TI", "Computador", subtipo
    if re.search(r"\b(MONITOR|TELA|DISPLAY)\b", desc):
        return "Informática & TI", "Monitor / Tela", "Não Especificado"
    if re.search(r"\b(IMPRESSORA|MULTIFUNCIONAL|PLOTTER|SCANNER)\b", desc):
        subtipo = "Multifuncional" if "MULTIFUNCIONAL" in desc else "Impressora Laser/Jato"
        return "Informática & TI", "Impressora & Imagem", subtipo
    if re.search(r"\b(NOBREAK|NO-BREAK|ESTABILIZADOR)\b", desc):
        return "Informática & TI", "Proteção de Energia", "Nobreak / Estabilizador"

    # VEÍCULOS & MÁQUINAS
    if re.search(r"\b(CAMINHONETE|CAMIONETE|PICKUP|CAMINHAO|CAMINHÃO)\b", desc):
        subtipo = "Caminhão" if "CAMINH" in desc else "Caminhonete"
        return "Veículos & Transporte", "Utilitário / Carga", subtipo
    if re.search(r"\b(AUTOMOVEL|AUTOMÓVEL|CARRO|VEICULO|VEÍCULO)\b", desc):
        return "Veículos & Transporte", "Veículo Leve", "Passeio"
    if re.search(r"\b(TRATOR|RETROESCAVADEIRA|COLHEITADEIRA|PULVERIZADOR|SEMEADORA)\b", desc):
        return "Maquinário & Equip. Agrícolas", "Máquina Agrícola", "Pesada / Implemento"

    # CLIMATIZAÇÃO
    if re.search(r"\b(CONDICIONADOR DE AR|AR CONDICIONADO|SPLIT|VENTILADOR)\b", desc):
        subtipo = "Split / AC" if "SPLIT" in desc or "AR" in desc else "Ventilador"
        return "Climatização & Eletro", "Climatização", subtipo
    if re.search(r"\b(REFRIGERADOR|GELADEIRA|FREEZER|BEBEDOURO|MICRO-ONDAS|CAFETEIRA)\b", desc):
        return "Climatização & Eletro", "Eletrodoméstico / Copa", "Padrão"

    return "Outros / Diversos", "Não Classificado", "Não Especificado"

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

    return df_total

# ----------------------------------------------------
# 4. FUNÇÃO DE GERAÇÃO DE RELATÓRIO PDF EM MEMÓRIA
# ----------------------------------------------------
def gerar_relatorio_pdf(df_dados, filtros_desc):
    """Gera um PDF formatado com layout executivo e retorna os bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=30,
        rightMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    elementos = []
    styles = getSampleStyleSheet()

    # Estilos customizados
    titulo_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#1E4D2B'),
        spaceAfter=4
    )
    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#555555'),
        spaceAfter=15
    )
    secao_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#1E4D2B'),
        spaceBefore=12,
        spaceAfter=6
    )

    # Cabeçalho
    elementos.append(Paragraph("SISTEMA INTEGRADO DE GESTÃO E CONSULTA PATRIMONIAL", titulo_style))
    elementos.append(Paragraph(
        f"Secretaria da Agricultura, Pecuária, Produção Sustentável e Irrigação • SEAPI/RS | Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        sub_style
    ))

    # Filtros Aplicados
    filtro_p = Paragraph(f"<b>Parâmetros do Filtro:</b> {filtros_desc}", ParagraphStyle('Filtros', fontSize=8, textColor=colors.HexColor('#333333')))
    elementos.append(filtro_p)
    elementos.append(Spacer(1, 10))

    # 1. Tabela de KPIs Principais
    qtd_total = len(df_dados)
    val_total = df_dados["Valor_Contabil"].sum()
    val_medio = (val_total / qtd_total) if qtd_total > 0 else 0.0

    kpi_data = [
        ["QUANTIDADE DE BENS", "VALOR PATRIMONIAL TOTAL", "TICKET MÉDIO CONTÁBIL"],
        [f"{qtd_total:,}".replace(",", "."), f"R$ {val_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), f"R$ {val_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")]
    ]
    t_kpi = Table(kpi_data, colWidths=[240, 260, 240])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E4D2B')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#F4F8F4')),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,1), (-1,1), 14),
        ('TEXTCOLOR', (0,1), (-1,1), colors.HexColor('#1E4D2B')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#1E4D2B')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
    ]))
    elementos.append(t_kpi)
    elementos.append(Spacer(1, 12))

    # 2. Resumo por Departamento
    elementos.append(Paragraph("Distribuição Consolidada por Departamento Oficial", secao_style))
    agrup_dep = df_dados.groupby("Departamento")["Valor_Contabil"].agg(["count", "sum"]).reset_index()
    agrup_dep.columns = ["Departamento", "Qtd", "Valor"]
    agrup_dep = agrup_dep.sort_values(by="Qtd", ascending=False).head(8)

    t_dep_data = [["Departamento Oficial", "Qtd. Bens", "Part. (%)", "Valor Total (R$)"]]
    for _, r in agrup_dep.iterrows():
        pct = (r["Qtd"] / qtd_total * 100) if qtd_total > 0 else 0
        t_dep_data.append([
            str(r["Departamento"]),
            f"{int(r['Qtd']):,}".replace(",", "."),
            f"{pct:.1f}%",
            f"R$ {r['Valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        ])

    t_dep = Table(t_dep_data, colWidths=[260, 140, 140, 200])
    t_dep.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2E693D')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FBF9')])
    ]))
    elementos.append(t_dep)
    elementos.append(Spacer(1, 12))

    # 3. Amostra dos Primeiros 25 Bens Listados
    elementos.append(Paragraph(f"Detalhamento dos Itens Filtrados (Primeiros {min(qtd_total, 25)} registros)", secao_style))
    amostra = df_dados.head(25)
    t_itens_data = [["Tombamento", "Descrição do Bem", "Depto.", "Unidade de Guarda", "Status", "Valor (R$)"]]
    for _, r in amostra.iterrows():
        t_itens_data.append([
            str(r["Tombamento"]),
            str(r["Descricao"])[:35],
            str(r["Departamento"])[:10],
            str(r["Unidade"])[:28],
            str(r["Status"])[:15],
            f"R$ {r['Valor_Contabil']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        ])

    t_itens = Table(t_itens_data, colWidths=[70, 210, 70, 200, 100, 90])
    t_itens.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E4D2B')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7),
        ('ALIGN', (-1,0), (-1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#DDDDDD')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#FAFAFA')])
    ]))
    elementos.append(t_itens)

    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

# ----------------------------------------------------
# 5. CARREGAMENTO DOS DADOS NO APP
# ----------------------------------------------------
with st.spinner("Conectando ao Google Sheets e consolidando bases de dados..."):
    try:
        df = carregar_dados_sistema()
    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha: {e}")
        st.stop()

# ----------------------------------------------------
# 6. HEADER VISUAL EXECUTIVO
# ----------------------------------------------------
st.markdown("""
<div class="header-box">
    <h1>🏛️ Sistema Integrado de Consulta e Pesquisa Patrimonial</h1>
    <p>Secretaria da Agricultura, Pecuária, Produção Sustentável e Irrigação • Estado do Rio Grande do Sul</p>
</div>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# 7. BARRA LATERAL COM FILTROS MULTISSELEÇÃO
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
st.sidebar.subheader("📦 Tipologia do Bem")

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

st.sidebar.markdown("---")
status_lista = sorted(df["Status"].unique().tolist())
status_selecionados = st.sidebar.multiselect("Situação / Status:", status_lista, placeholder="Todos os status")

# ----------------------------------------------------
# 8. FILTRAGEM DO DATAFRAME
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
if status_selecionados:
    df_filtrado = df_filtrado[df_filtrado["Status"].isin(status_selecionados)]

# ----------------------------------------------------
# 9. CARDS DE KPIS COM DESIGN SEAPI
# ----------------------------------------------------
qtd_total = len(df_filtrado)
valor_total = df_filtrado["Valor_Contabil"].sum()
ticket_medio = (valor_total / qtd_total) if qtd_total > 0 else 0.0

col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

with col_kpi1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="title">Quantidade de Bens</div>
        <div class="value">{qtd_total:,}</div>
        <div class="subtitle">Itens no escopo ativo</div>
    </div>
    """.replace(",", "."), unsafe_allow_html=True)

with col_kpi2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="title">Valor Patrimonial Total</div>
        <div class="value">R$ {valor_total:,.2f}</div>
        <div class="subtitle">Base contábil apurada</div>
    </div>
    """.replace(",", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

with col_kpi3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="title">Ticket Médio Contábil</div>
        <div class="value">R$ {ticket_medio:,.2f}</div>
        <div class="subtitle">Valor médio por ativo</div>
    </div>
    """.replace(",", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

with col_kpi4:
    filtros_ativos = bool(termo_busca or bases_selecionadas or deptos_selecionados or unidades_selecionadas or familias_selecionadas or tipos_selecionados or subtipos_selecionados or status_selecionados)
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: {'#2A75D3' if filtros_ativos else '#666666'};">
        <div class="title">Status dos Filtros</div>
        <div class="value" style="color: {'#2A75D3' if filtros_ativos else '#666666'};">{'🔵 Ativo(s)' if filtros_ativos else '⚪ Base Toda'}</div>
        <div class="subtitle">{'Filtros personalizados' if filtros_ativos else 'Nenhum filtro aplicado'}</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# ----------------------------------------------------
# 10. ABAS DE NAVEGAÇÃO E ANÁLISE
# ----------------------------------------------------
tab_dash, tab_itens, tab_pdf, tab_ficha = st.tabs([
    "📊 Painel Executivo / Dashboard",
    "📋 Itens Pesquisados",
    "📄 Gerar Relatório PDF",
    "🔍 Ficha Individual do Bem"
])

# ABA 1: DASHBOARD
with tab_dash:
    if qtd_total > 0:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Distribuição por Departamento Oficial")
            agrup_depto = df_filtrado.groupby("Departamento")["Valor_Contabil"].agg(["count", "sum"]).reset_index()
            agrup_depto.columns = ["Departamento", "Qtd. Bens", "Valor Total (R$)"]
            agrup_depto = agrup_depto.sort_values(by="Qtd. Bens", ascending=False)
            st.dataframe(agrup_depto, use_container_width=True, hide_index=True)
            st.bar_chart(agrup_depto.set_index("Departamento")["Qtd. Bens"])

        with c2:
            st.subheader("Distribuição por Tipo de Bem")
            agrup_tipo = df_filtrado.groupby("Tipo_Bem")["Valor_Contabil"].agg(["count", "sum"]).reset_index()
            agrup_tipo.columns = ["Tipo do Bem", "Qtd. Bens", "Valor Total (R$)"]
            agrup_tipo = agrup_tipo.sort_values(by="Qtd. Bens", ascending=False).head(10)
            st.dataframe(agrup_tipo, use_container_width=True, hide_index=True)
            st.bar_chart(agrup_tipo.set_index("Tipo do Bem")["Qtd. Bens"])
    else:
        st.info("Nenhum registro encontrado para alimentar os gráficos.")

# ABA 2: ITENS PESQUISADOS
with tab_itens:
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
                "Subtipo": "Subtipo",
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

# ABA 3: EXPORTAÇÃO PDF
with tab_pdf:
    st.subheader("Gerador de Relatório Patrimonial Oficial (PDF)")
    st.write("Gere um documento executivo com os totais, resumos por departamento e listagem dos bens de acordo com os filtros selecionados na barra lateral.")

    texto_filtros = []
    if termo_busca: texto_filtros.append(f"Busca: '{termo_busca}'")
    if deptos_selecionados: texto_filtros.append(f"Deptos: {', '.join(deptos_selecionados)}")
    if unidades_selecionadas: texto_filtros.append(f"Unidades: {len(unidades_selecionadas)} selecionada(s)")
    if familias_selecionadas: texto_filtros.append(f"Famílias: {', '.join(familias_selecionadas)}")
    if tipos_selecionados: texto_filtros.append(f"Tipos: {', '.join(tipos_selecionados)}")
    if status_selecionados: texto_filtros.append(f"Status: {', '.join(status_selecionados)}")
    desc_final = " | ".join(texto_filtros) if texto_filtros else "Base Completa (Sem restrições)"

    if qtd_total > 0:
        if st.button("📄 Gerar e Compilar Relatório PDF"):
            with st.spinner("Compilando dados e formatando PDF executivo..."):
                pdf_bytes = gerar_relatorio_pdf(df_filtrado, desc_final)
                st.success("Relatório PDF gerado com sucesso!")
                st.download_button(
                    label="⬇️ Baixar Relatório em PDF",
                    data=pdf_bytes,
                    file_name=f"Relatorio_Patrimonial_SEAPI_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf"
                )
    else:
        st.warning("Não há dados filtrados para gerar o relatório em PDF.")

# ABA 4: FICHA INDIVIDUAL
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
