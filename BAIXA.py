import streamlit as st
from groq import Groq
import pandas as pd
import pdfplumber
import json
import re
import io
import os
import base64
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# =========================================================
# CONFIGURAÇÃO GERAL
# =========================================================
st.set_page_config(page_title="Avaliação de Bens Inservíveis - Multi-bens", layout="wide")

# =========================================================
# ESTADO INICIAL
# =========================================================
def init_state():
    if "bens" not in st.session_state or not isinstance(st.session_state.bens, list):
        st.session_state.bens = []

    if "processo" not in st.session_state:
        st.session_state.processo = {
            "proa_sei": "",
            "unidade": "",
            "membros_comissao": "",
            "observacoes_gerais": ""
        }

    if "config" not in st.session_state:
        st.session_state.config = {
            "modelo_texto": st.secrets.get("GROQ_MODEL_TEXT", "llama-3.3-70b-versatile"),
            "modelo_visao": st.secrets.get("GROQ_MODEL_VISION", "llama-3.2-11b-vision-preview")
        }

init_state()

# =========================================================
# IA / GROQ
# =========================================================
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# =========================================================
# FUNÇÕES UTILITÁRIAS
# =========================================================
def agora_rs():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")

def tr(texto):
    if texto is None:
        return ""
    texto = str(texto)
    texto = (
        texto.replace("–", "-")
        .replace("—", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("•", "-")
    )
    return texto

def garantir_float(v, default=0.0):
    try:
        if v is None or str(v).strip() == "":
            return default
        s = str(v).strip()
        s = s.replace("R$", "").replace(" ", "")
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", ".")
        return float(s)
    except:
        return default

def limpar_json(texto):
    if not texto:
        return None
    try:
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        bruto = match.group(0) if match else texto
        return json.loads(bruto)
    except:
        return None

def uploaded_file_to_bytes(uploaded_file):
    if uploaded_file is None:
        return None
    return uploaded_file.getvalue()

def image_bytes_to_data_url(img_bytes, mime="image/jpeg"):
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def normalize_col(col):
    return (
        str(col)
        .strip()
        .lower()
        .replace("ã", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )

def novo_bem():
    return {
        "id": f"bem_{datetime.now().timestamp()}",
        "patrimonio": "",
        "descricao": "",
        "unidade_guarda": "",
        "localizacao": "",
        "ano_aquisicao": "",
        "valor_ape": 0.0,
        "valor_mercado": 0.0,
        "custo_recuperacao": 0.0,
        "estado_conservacao_sugerido": "",
        "analise_visual_ia": "",
        "confianca_ia": "",
        "defeitos_identificados": [],
        "ficha_resumo": "",
        "ficha_arquivo_nome": "",
        "em_condicoes_de_uso": True,
        "esta_sendo_utilizado": True,
        "e_aproveitavel_pelo_orgao": True,
        "atende_exigencias_tecnicas_atuais": True,
        "manutencao_onerosa": False,
        "rendimento_precario": False,
        "perdeu_caracteristicas_essenciais": False,
        "ha_viabilidade_economica_de_recuperacao": True,
        "classificacao_final": "",
        "destinacao_sugerida": "",
        "justificativa_tecnica": "",
        "observacao_comissao": "",
        "fotos": []
    }

# =========================================================
# LEITURA DA FICHA DO BEM (OPCIONAL)
# =========================================================
def extrair_texto_pdf(uploaded_pdf):
    texto = ""
    try:
        with pdfplumber.open(uploaded_pdf) as pdf:
            for pg in pdf.pages[:8]:
                texto += (pg.extract_text() or "") + "\n"
    except:
        return ""
    return texto.strip()

def analisar_ficha_texto_com_ia(texto_ficha):
    if not client or not texto_ficha.strip():
        return None

    prompt = """
Você está extraindo dados de uma ficha de bem patrimonial.
Retorne SOMENTE JSON válido no formato:
{
  "patrimonio": "",
  "descricao": "",
  "unidade_guarda": "",
  "localizacao": "",
  "ano_aquisicao": "",
  "valor_ape": "",
  "resumo": ""
}
Se algum campo não estiver visível, deixe vazio.
"""

    try:
        resp = client.chat.completions.create(
            model=st.session_state.config["modelo_texto"],
            messages=[{"role": "user", "content": f"{prompt}\n\nFICHA:\n{texto_ficha}"}],
            temperature=0.1
        )
        return limpar_json(resp.choices[0].message.content)
    except:
        return None

def analisar_ficha_imagem_com_ia(uploaded_img):
    if not client or uploaded_img is None:
        return None

    file_bytes = uploaded_file_to_bytes(uploaded_img)
    if not file_bytes:
        return None

    mime = uploaded_img.type if uploaded_img.type else "image/jpeg"
    data_url = image_bytes_to_data_url(file_bytes, mime)

    prompt = """
Analise a imagem de uma ficha de bem patrimonial.
Extraia apenas os dados visíveis e retorne SOMENTE JSON válido no formato:
{
  "patrimonio": "",
  "descricao": "",
  "unidade_guarda": "",
  "localizacao": "",
  "ano_aquisicao": "",
  "valor_ape": "",
  "resumo": ""
}
Não invente dados.
"""

    try:
        resp = client.chat.completions.create(
            model=st.session_state.config["modelo_visao"],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ],
            temperature=0.1
        )
        return limpar_json(resp.choices[0].message.content)
    except:
        return None

def processar_ficha_bem(uploaded_file):
    if uploaded_file is None:
        return None

    nome = uploaded_file.name.lower()

    if nome.endswith(".pdf"):
        texto = extrair_texto_pdf(uploaded_file)
        if texto:
            return analisar_ficha_texto_com_ia(texto)
        return None

    if nome.endswith(".txt"):
        try:
            texto = uploaded_file.read().decode("utf-8", errors="ignore")
            return analisar_ficha_texto_com_ia(texto)
        except:
            return None

    if nome.endswith(".jpg") or nome.endswith(".jpeg") or nome.endswith(".png"):
        return analisar_ficha_imagem_com_ia(uploaded_file)

    return None

# =========================================================
# ANÁLISE VISUAL DAS FOTOS DO BEM
# =========================================================
def analisar_fotos_bem_com_ia(fotos, contexto_ficha=""):
    """
    A IA sugere estado de conservação, defeitos visuais e confiança.
    NÃO fecha sozinha a classificação jurídica do decreto.
    """
    if not client or not fotos:
        return None

    content = [
        {
            "type": "text",
            "text": f"""
Você está avaliando fotografias de um bem móvel público.
Faça APENAS análise visual objetiva.

Contexto opcional da ficha:
{contexto_ficha}

Retorne SOMENTE JSON válido no formato:
{{
  "estado_conservacao_sugerido": "Ótimo|Bom|Regular|Ruim|Péssimo",
  "confianca": "Alta|Média|Baixa",
  "indicios_visuais": ["item 1", "item 2"],
  "funcionalidade_aparente": "texto curto",
  "justificativa_visual": "texto curto"
}}

Regras:
- Baseie-se somente no que é visível.
- Não classifique juridicamente o bem como ocioso, obsoleto, antieconômico ou irrecuperável.
- Se as fotos forem insuficientes, reduza a confiança.
"""
        }
    ]

    for foto in fotos[:6]:
        try:
            img_bytes = uploaded_file_to_bytes(foto)
            if not img_bytes:
                continue
            mime = foto.type if foto.type else "image/jpeg"
            data_url = image_bytes_to_data_url(img_bytes, mime)
            content.append({"type": "image_url", "image_url": {"url": data_url}})
        except:
            pass

    try:
        resp = client.chat.completions.create(
            model=st.session_state.config["modelo_visao"],
            messages=[{"role": "user", "content": content}],
            temperature=0.1
        )
        return limpar_json(resp.choices[0].message.content)
    except:
        return None

# =========================================================
# REGRAS DE CLASSIFICAÇÃO (DECRETO)
# =========================================================
def sugerir_classificacao_decreto(bem):
    """
    Regra assistida:
    - Ocioso / em desuso: em condição de uso, mas não aproveitável / não utilizado
    - Obsoleto: em condição de uso, mas não atende exigências técnicas atuais
    - Antieconômico: manutenção onerosa / rendimento precário
    - Irrecuperável: perdeu características / recuperação inviável economicamente
    """
    em_uso = bool(bem.get("esta_sendo_utilizado", True))
    aproveitavel = bool(bem.get("e_aproveitavel_pelo_orgao", True))
    atende = bool(bem.get("atende_exigencias_tecnicas_atuais", True))
    em_condicoes = bool(bem.get("em_condicoes_de_uso", True))
    manutencao_onerosa = bool(bem.get("manutencao_onerosa", False))
    rendimento_precario = bool(bem.get("rendimento_precario", False))
    perdeu = bool(bem.get("perdeu_caracteristicas_essenciais", False))
    viavel = bool(bem.get("ha_viabilidade_economica_de_recuperacao", True))

    valor_mercado = garantir_float(bem.get("valor_mercado", 0))
    custo_rec = garantir_float(bem.get("custo_recuperacao", 0))
    proporcao = (custo_rec / valor_mercado) if valor_mercado > 0 else 0

    if perdeu or (valor_mercado > 0 and proporcao > 0.5) or (not viavel):
        return "Irrecuperável"

    if manutencao_onerosa or rendimento_precario:
        return "Antieconômico"

    if em_condicoes and (not atende):
        return "Obsoleto"

    if em_condicoes and ((not em_uso) or (not aproveitavel)):
        return "Ocioso / em desuso"

    return "Sem enquadramento automático"

def sugerir_destinacao(bem):
    classificacao = bem.get("classificacao_final", "")
    descricao = str(bem.get("descricao", "")).lower()

    if classificacao == "Ocioso / em desuso":
        return "Transferência patrimonial ou doação, conforme interesse público"
    if classificacao == "Obsoleto":
        if any(k in descricao for k in ["computador", "monitor", "impressora", "notebook", "eletr", "cpu"]):
            return "Programa Sustentare ou outra destinação específica para eletroeletrônicos"
        return "Leilão, doação ou outra destinação definida pela administração"
    if classificacao == "Antieconômico":
        if any(k in descricao for k in ["computador", "monitor", "impressora", "notebook", "eletr", "cpu"]):
            return "Programa Sustentare, leilão ou descarte adequado"
        return "Leilão, descarte ou doação, conforme avaliação"
    if classificacao == "Irrecuperável":
        if any(k in descricao for k in ["computador", "monitor", "impressora", "notebook", "eletr", "cpu"]):
            return "Programa Sustentare ou descarte ambientalmente adequado"
        return "Eliminação / descarte adequado ou outra destinação cabível"
    return ""

def gerar_justificativa_tecnica(bem):
    classificacao = bem.get("classificacao_final", "")
    estado = bem.get("estado_conservacao_sugerido", "")
    sinais = bem.get("defeitos_identificados", [])
    justificativa_visual = bem.get("analise_visual_ia", "")
    custo = garantir_float(bem.get("custo_recuperacao", 0))
    valor = garantir_float(bem.get("valor_mercado", 0))

    partes = []

    if estado:
        partes.append(f"O estado de conservação sugerido a partir das evidências fotográficas é '{estado}'.")

    if sinais:
        partes.append("Foram observados os seguintes indícios visuais: " + "; ".join(sinais) + ".")

    if justificativa_visual:
        partes.append(justificativa_visual.strip())

    if classificacao == "Ocioso / em desuso":
        partes.append("Embora o bem possa encontrar-se em condições de uso, verificou-se que ele não está sendo utilizado ou não é aproveitável pelo órgão na sua situação atual.")
    elif classificacao == "Obsoleto":
        partes.append("Embora possa manter alguma condição de uso, o bem não atende mais às exigências técnicas atuais do órgão.")
    elif classificacao == "Antieconômico":
        partes.append("A manutenção do bem foi apontada como onerosa ou o seu rendimento como precário, o que justifica o enquadramento como antieconômico.")
    elif classificacao == "Irrecuperável":
        if valor > 0 and custo > 0:
            partes.append(f"O custo estimado de recuperação informado é de R$ {custo:,.2f} para um valor de mercado de R$ {valor:,.2f}, indicando inviabilidade econômica de recuperação.")
        else:
            partes.append("Verificou-se perda de características essenciais ou inviabilidade econômica de recuperação do bem.")

    return " ".join(partes).strip()

# =========================================================
# IMPORTAÇÃO DE PLANILHA
# =========================================================
def importar_planilha(uploaded_file):
    if uploaded_file is None:
        return []

    nome = uploaded_file.name.lower()

    try:
        if nome.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif nome.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file, engine="openpyxl")
        else:
            return []
    except:
        return []

    if df.empty:
        return []

    cols = {normalize_col(c): c for c in df.columns}

    bens = []
    for _, row in df.iterrows():
        b = novo_bem()

        mapa = {
            "patrimonio": ["patrimonio", "numero patrimonial", "n patrimonial", "tombo", "placa"],
            "descricao": ["descricao", "descrição", "bem", "nome do bem", "denominacao", "denominacao do bem"],
            "unidade_guarda": ["unidade_guarda", "unidade de guarda", "dependencia", "dependencia de guarda"],
            "localizacao": ["localizacao", "localização", "setor", "sala", "local"],
            "ano_aquisicao": ["ano_aquisicao", "ano de aquisicao", "ano aquisicao", "ano"],
            "valor_ape": ["valor_ape", "valor contabil", "valor contábil", "valor"]
        }

        for campo, aliases in mapa.items():
            for a in aliases:
                if a in cols:
                    b[campo] = row[cols[a]]
                    break

        b["valor_ape"] = garantir_float(b["valor_ape"], 0.0)
        bens.append(b)

    return bens

# =========================================================
# PDF
# =========================================================
def temp_image_from_uploaded(uploaded_file):
    try:
        img = Image.open(uploaded_file)
        if img.mode != "RGB":
            img = img.convert("RGB")
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        img.save(temp.name, format="JPEG", quality=80)
        return temp.name
    except:
        return None

def gerar_pdf_relatorio(processo, bens):
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25,
        leftMargin=25,
        topMargin=30,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TituloCentro", parent=styles["Heading1"], alignment=TA_CENTER, fontSize=15, leading=18))
    styles.add(ParagraphStyle(name="SubTitulo", parent=styles["Heading2"], alignment=TA_LEFT, fontSize=11, textColor=colors.darkgreen))
    styles.add(ParagraphStyle(name="NormalJust", parent=styles["BodyText"], fontSize=9, leading=12))
    styles.add(ParagraphStyle(name="CenterSmall", parent=styles["BodyText"], alignment=TA_CENTER, fontSize=8, leading=10))

    story = []

    # Cabeçalho
    story.append(Paragraph("SECRETARIA DA AGRICULTURA, PECUÁRIA, PRODUÇÃO SUSTENTÁVEL E IRRIGAÇÃO", styles["TituloCentro"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("RELATÓRIO DE AVALIAÇÃO DE BENS INSERVÍVEIS", styles["TituloCentro"]))
    story.append(Spacer(1, 12))

    # Processo
    story.append(Paragraph("1. IDENTIFICAÇÃO DO PROCESSO", styles["SubTitulo"]))
    dados_processo = [
        ["PROA / SEI", processo.get("proa_sei", "")],
        ["Unidade", processo.get("unidade", "")],
        ["Membros da Comissão", processo.get("membros_comissao", "")],
        ["Data/Hora", agora_rs()]
    ]
    tabela_proc = Table(dados_processo, colWidths=[120, 380])
    tabela_proc.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(tabela_proc)
    story.append(Spacer(1, 10))

    # Metodologia
    story.append(Paragraph("2. METODOLOGIA", styles["SubTitulo"]))
    metodologia = (
        "A presente avaliação foi realizada a partir das informações cadastrais disponíveis, "
        "das evidências fotográficas juntadas para cada bem, das respostas fornecidas pelos avaliadores "
        "quanto às condições de uso, aproveitamento, adequação técnica, custo de recuperação e viabilidade econômica, "
        "com apoio de análise visual assistida por IA para sugestão do estado de conservação."
    )
    story.append(Paragraph(metodologia, styles["NormalJust"]))
    story.append(Spacer(1, 10))

    # Quadro-resumo
    story.append(Paragraph("3. QUADRO-RESUMO DOS BENS", styles["SubTitulo"]))
    resumo_rows = [["Patrimônio", "Descrição", "Estado sugerido", "Classificação final", "Destinação sugerida"]]
    for b in bens:
        resumo_rows.append([
            tr(b.get("patrimonio", "")),
            tr(b.get("descricao", "")),
            tr(b.get("estado_conservacao_sugerido", "")),
            tr(b.get("classificacao_final", "")),
            tr(b.get("destinacao_sugerida", "")),
        ])

    resumo_table = Table(resumo_rows, colWidths=[70, 150, 90, 90, 110], repeatRows=1)
    resumo_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d9ead3")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    story.append(resumo_table)
    story.append(PageBreak())

    # Laudos individuais
    for idx, b in enumerate(bens, start=1):
        story.append(Paragraph(f"4.{idx} BEM {idx}", styles["SubTitulo"]))

        dados_bem = [
            ["Patrimônio", tr(b.get("patrimonio", "")), "Ano aquisição", tr(b.get("ano_aquisicao", ""))],
            ["Descrição", tr(b.get("descricao", "")), "Valor APE", f"R$ {garantir_float(b.get('valor_ape', 0)):,.2f}"],
            ["Unidade de guarda", tr(b.get("unidade_guarda", "")), "Localização", tr(b.get("localizacao", ""))],
            ["Estado sugerido por IA", tr(b.get("estado_conservacao_sugerido", "")), "Confiança", tr(b.get("confianca_ia", ""))],
            ["Classificação final", tr(b.get("classificacao_final", "")), "Destinação sugerida", tr(b.get("destinacao_sugerida", ""))]
        ]
        tb = Table(dados_bem, colWidths=[95, 160, 95, 150])
        tb.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
        ]))
        story.append(tb)
        story.append(Spacer(1, 8))

        if b.get("ficha_resumo"):
            story.append(Paragraph("<b>Resumo da ficha do bem:</b>", styles["NormalJust"]))
            story.append(Paragraph(tr(b.get("ficha_resumo", "")), styles["NormalJust"]))
            story.append(Spacer(1, 6))

        if b.get("analise_visual_ia"):
            story.append(Paragraph("<b>Análise visual assistida por IA:</b>", styles["NormalJust"]))
            story.append(Paragraph(tr(b.get("analise_visual_ia", "")), styles["NormalJust"]))
            story.append(Spacer(1, 6))

        if b.get("defeitos_identificados"):
            story.append(Paragraph("<b>Indícios / defeitos visuais identificados:</b>", styles["NormalJust"]))
            story.append(Paragraph("• " + "<br/>• ".join([tr(x) for x in b.get("defeitos_identificados", [])]), styles["NormalJust"]))
            story.append(Spacer(1, 6))

        if b.get("justificativa_tecnica"):
            story.append(Paragraph("<b>Justificativa técnica:</b>", styles["NormalJust"]))
            story.append(Paragraph(tr(b.get("justificativa_tecnica", "")), styles["NormalJust"]))
            story.append(Spacer(1, 6))

        if b.get("observacao_comissao"):
            story.append(Paragraph("<b>Observação complementar da comissão:</b>", styles["NormalJust"]))
            story.append(Paragraph(tr(b.get("observacao_comissao", "")), styles["NormalJust"]))
            story.append(Spacer(1, 6))

        fotos = b.get("fotos", [])
        temp_files = []

        if fotos:
            story.append(Paragraph("<b>Evidências fotográficas:</b>", styles["NormalJust"]))
            imgs = []

            for foto in fotos[:4]:
                img_path = temp_image_from_uploaded(foto)
                if img_path:
                    temp_files.append(img_path)
                    try:
                        imgs.append(RLImage(img_path, width=160, height=120))
                    except:
                        pass

            if imgs:
                linhas = []
                linha = []
                for img in imgs:
                    linha.append(img)
                    if len(linha) == 2:
                        linhas.append(linha)
                        linha = []
                if linha:
                    while len(linha) < 2:
                        linha.append("")
                    linhas.append(linha)

                timg = Table(linhas, colWidths=[250, 250])
                story.append(timg)
                story.append(Spacer(1, 8))

        for tf in temp_files:
            try:
                os.unlink(tf)
            except:
                pass

        if idx < len(bens):
            story.append(PageBreak())

    if processo.get("observacoes_gerais"):
        story.append(PageBreak())
        story.append(Paragraph("5. OBSERVAÇÕES GERAIS", styles["SubTitulo"]))
        story.append(Paragraph(tr(processo.get("observacoes_gerais", "")), styles["NormalJust"]))

    doc.build(story)
    buffer.seek(0)
    return buffer

# =========================================================
# INTERFACE
# =========================================================
st.title("📋 Avaliação de Bens Inservíveis - Multi-bens com IA")

with st.sidebar:
    st.markdown("### Configuração da IA")
    st.session_state.config["modelo_texto"] = st.text_input("Modelo de texto", st.session_state.config["modelo_texto"])
    st.session_state.config["modelo_visao"] = st.text_input("Modelo de visão", st.session_state.config["modelo_visao"])
    st.caption("Ajuste aqui caso tua conta use nomes de modelos diferentes.")

    st.markdown("---")
    if st.button("🔄 Reiniciar aplicação"):
        st.session_state.clear()
        st.rerun()

# ---------------------------------------------------------
# Dados do processo
# ---------------------------------------------------------
with st.container(border=True):
    st.subheader("1) Dados do processo")
    c1, c2 = st.columns(2)
    st.session_state.processo["proa_sei"] = c1.text_input("PROA / SEI", value=st.session_state.processo.get("proa_sei", ""))
    st.session_state.processo["unidade"] = c2.text_input("Unidade responsável", value=st.session_state.processo.get("unidade", ""))
    st.session_state.processo["membros_comissao"] = st.text_area(
        "Membros da comissão",
        value=st.session_state.processo.get("membros_comissao", ""),
        height=70,
        placeholder="Ex.: Membro 1, Membro 2, Membro 3"
    )
    st.session_state.processo["observacoes_gerais"] = st.text_area(
        "Observações gerais",
        value=st.session_state.processo.get("observacoes_gerais", ""),
        height=90
    )

# ---------------------------------------------------------
# Importação de planilha
# ---------------------------------------------------------
with st.container(border=True):
    st.subheader("2) Importação opcional de planilha")
    planilha = st.file_uploader("Carregar CSV/XLSX com bens", type=["csv", "xlsx"], key="planilha_bens")
    cimp1, cimp2 = st.columns([1, 3])

    if cimp1.button("📥 Importar planilha"):
        novos = importar_planilha(planilha)
        if novos:
            st.session_state.bens.extend(novos)
            st.success(f"{len(novos)} bens importados.")
            st.rerun()
        else:
            st.warning("Nenhum bem importado. Verifique a planilha.")

    st.caption("Colunas reconhecidas: patrimônio, descrição, unidade de guarda, localização, ano de aquisição, valor APE.")

# ---------------------------------------------------------
# Cadastro manual
# ---------------------------------------------------------
with st.container(border=True):
    st.subheader("3) Cadastro manual")
    if st.button("➕ Adicionar bem manualmente"):
        st.session_state.bens.append(novo_bem())
        st.rerun()

if not st.session_state.bens:
    st.info("Nenhum bem cadastrado ainda. Importe uma planilha ou adicione bens manualmente.")
    st.stop()

# ---------------------------------------------------------
# Avaliação dos bens
# ---------------------------------------------------------
st.subheader("4) Avaliação dos bens")

for idx, bem in enumerate(list(st.session_state.bens)):
    uid = bem["id"]

    with st.expander(f"Bem {idx + 1} — {bem.get('descricao') or 'Sem descrição'}", expanded=(idx == 0)):
        top1, top2, top3 = st.columns([1, 1, 0.6])

        with top1:
            bem["patrimonio"] = st.text_input("Patrimônio", value=str(bem.get("patrimonio", "")), key=f"pat_{uid}")
            bem["descricao"] = st.text_input("Descrição", value=str(bem.get("descricao", "")), key=f"desc_{uid}")
            bem["unidade_guarda"] = st.text_input("Unidade de guarda", value=str(bem.get("unidade_guarda", "")), key=f"ug_{uid}")
            bem["localizacao"] = st.text_input("Localização", value=str(bem.get("localizacao", "")), key=f"loc_{uid}")

        with top2:
            bem["ano_aquisicao"] = st.text_input("Ano de aquisição", value=str(bem.get("ano_aquisicao", "")), key=f"ano_{uid}")
            bem["valor_ape"] = st.number_input("Valor APE / valor contábil", min_value=0.0, value=float(garantir_float(bem.get("valor_ape", 0))), key=f"vape_{uid}", step=100.0)
            bem["valor_mercado"] = st.number_input("Valor de mercado estimado", min_value=0.0, value=float(garantir_float(bem.get("valor_mercado", 0))), key=f"vmerc_{uid}", step=100.0)
            bem["custo_recuperacao"] = st.number_input("Custo estimado de recuperação", min_value=0.0, value=float(garantir_float(bem.get("custo_recuperacao", 0))), key=f"vrec_{uid}", step=100.0)

        with top3:
            if st.button("🗑️ Excluir bem", key=f"del_{uid}"):
                st.session_state.bens = [x for x in st.session_state.bens if x["id"] != uid]
                st.rerun()

        st.markdown("#### Ficha do bem (opcional)")
        ficha = st.file_uploader(
            "Carregar ficha do bem (PDF, TXT, JPG, JPEG, PNG)",
            type=["pdf", "txt", "jpg", "jpeg", "png"],
            key=f"ficha_{uid}"
        )

        col_f1, col_f2 = st.columns([1, 3])
        if col_f1.button("🤖 Ler ficha com IA", key=f"ler_ficha_{uid}"):
            if ficha:
                res = processar_ficha_bem(ficha)
                if res:
                    bem["ficha_arquivo_nome"] = ficha.name
                    bem["ficha_resumo"] = str(res.get("resumo", "") or "")
                    if res.get("patrimonio"):
                        bem["patrimonio"] = res.get("patrimonio", "")
                    if res.get("descricao"):
                        bem["descricao"] = res.get("descricao", "")
                    if res.get("unidade_guarda"):
                        bem["unidade_guarda"] = res.get("unidade_guarda", "")
                    if res.get("localizacao"):
                        bem["localizacao"] = res.get("localizacao", "")
                    if res.get("ano_aquisicao"):
                        bem["ano_aquisicao"] = res.get("ano_aquisicao", "")
                    if res.get("valor_ape"):
                        bem["valor_ape"] = garantir_float(res.get("valor_ape", 0), bem["valor_ape"])
                    st.success("Ficha processada e campos pré-preenchidos.")
                    st.rerun()
                else:
                    st.warning("Não foi possível extrair dados da ficha.")
            else:
                st.info("Carrega primeiro a ficha do bem.")

        if bem.get("ficha_resumo"):
            st.text_area("Resumo extraído da ficha", value=bem.get("ficha_resumo", ""), height=100, key=f"res_ficha_{uid}")

        st.markdown("#### Fotos do bem")
        fotos = st.file_uploader(
            "Carregar fotos do bem (múltiplas)",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key=f"fotos_{uid}"
        )
        if fotos:
            bem["fotos"] = fotos

        if bem.get("fotos"):
            prev_cols = st.columns(min(4, len(bem["fotos"])))
            for i, ft in enumerate(bem["fotos"][:4]):
                prev_cols[i % len(prev_cols)].image(ft, caption=ft.name, use_container_width=True)

        if st.button("🧠 Analisar fotos com IA", key=f"ia_fotos_{uid}"):
            if bem.get("fotos"):
                res = analisar_fotos_bem_com_ia(bem["fotos"], bem.get("ficha_resumo", ""))
                if res:
                    bem["estado_conservacao_sugerido"] = res.get("estado_conservacao_sugerido", "")
                    bem["confianca_ia"] = res.get("confianca", "")
                    indicios = res.get("indicios_visuais", [])
                    bem["defeitos_identificados"] = indicios if isinstance(indicios, list) else []
                    bem["analise_visual_ia"] = (
                        f"Funcionalidade aparente: {res.get('funcionalidade_aparente', '')}. "
                        f"Justificativa visual: {res.get('justificativa_visual', '')}"
                    ).strip()
                    st.success("Fotos analisadas com IA.")
                    st.rerun()
                else:
                    st.warning("Não foi possível concluir a análise visual.")
            else:
                st.info("Carrega pelo menos uma foto do bem.")

        st.markdown("#### Critérios para classificação")
        c1, c2, c3 = st.columns(3)
        bem["em_condicoes_de_uso"] = c1.checkbox("Em condições de uso", value=bool(bem.get("em_condicoes_de_uso", True)), key=f"ecuso_{uid}")
        bem["esta_sendo_utilizado"] = c2.checkbox("Está sendo utilizado", value=bool(bem.get("esta_sendo_utilizado", True)), key=f"eusado_{uid}")
        bem["e_aproveitavel_pelo_orgao"] = c3.checkbox("É aproveitável pelo órgão", value=bool(bem.get("e_aproveitavel_pelo_orgao", True)), key=f"eaprov_{uid}")

        c4, c5, c6 = st.columns(3)
        bem["atende_exigencias_tecnicas_atuais"] = c4.checkbox("Atende às exigências técnicas atuais", value=bool(bem.get("atende_exigencias_tecnicas_atuais", True)), key=f"atende_{uid}")
        bem["manutencao_onerosa"] = c5.checkbox("Manutenção onerosa", value=bool(bem.get("manutencao_onerosa", False)), key=f"onerosa_{uid}")
        bem["rendimento_precario"] = c6.checkbox("Rendimento precário", value=bool(bem.get("rendimento_precario", False)), key=f"precario_{uid}")

        c7, c8 = st.columns(2)
        bem["perdeu_caracteristicas_essenciais"] = c7.checkbox("Perdeu características essenciais", value=bool(bem.get("perdeu_caracteristicas_essenciais", False)), key=f"perdeu_{uid}")
        bem["ha_viabilidade_economica_de_recuperacao"] = c8.checkbox("Há viabilidade econômica de recuperação", value=bool(bem.get("ha_viabilidade_economica_de_recuperacao", True)), key=f"viavel_{uid}")

        c9, c10 = st.columns([1, 2])
        if c9.button("⚖️ Sugerir classificação", key=f"class_{uid}"):
            bem["classificacao_final"] = sugerir_classificacao_decreto(bem)
            bem["destinacao_sugerida"] = sugerir_destinacao(bem)
            bem["justificativa_tecnica"] = gerar_justificativa_tecnica(bem)
            st.success("Classificação sugerida.")
            st.rerun()

        opcoes_classificacao = [
            "",
            "Ocioso / em desuso",
            "Obsoleto",
            "Antieconômico",
            "Irrecuperável",
            "Sem enquadramento automático"
        ]
        selecionada = bem.get("classificacao_final", "")
        idx_sel = opcoes_classificacao.index(selecionada) if selecionada in opcoes_classificacao else 0

        bem["classificacao_final"] = c10.selectbox(
            "Classificação final (ajustável pela comissão)",
            opcoes_classificacao,
            index=idx_sel,
            key=f"class_final_{uid}"
        )

        bem["destinacao_sugerida"] = st.text_input(
            "Destinação sugerida",
            value=bem.get("destinacao_sugerida", sugerir_destinacao(bem)),
            key=f"dest_{uid}"
        )

        bem["justificativa_tecnica"] = st.text_area(
            "Justificativa técnica",
            value=bem.get("justificativa_tecnica", gerar_justificativa_tecnica(bem) if bem.get("classificacao_final") else ""),
            height=120,
            key=f"just_{uid}"
        )

        bem["observacao_comissao"] = st.text_area(
            "Observação complementar da comissão",
            value=bem.get("observacao_comissao", ""),
            height=80,
            key=f"obscom_{uid}"
        )

# ---------------------------------------------------------
# Consolidação
# ---------------------------------------------------------
with st.container(border=True):
    st.subheader("5) Consolidação")

    total_bens = len(st.session_state.bens)
    total_valor_ape = sum(garantir_float(b.get("valor_ape", 0)) for b in st.session_state.bens)

    contagem = {
        "Ocioso / em desuso": 0,
        "Obsoleto": 0,
        "Antieconômico": 0,
        "Irrecuperável": 0,
        "Sem enquadramento automático": 0
    }

    for b in st.session_state.bens:
        cf = b.get("classificacao_final", "")
        if cf in contagem:
            contagem[cf] += 1

    c1, c2, c3 = st.columns(3)
    c1.metric("Total de bens", total_bens)
    c2.metric("Valor APE total", f"R$ {total_valor_ape:,.2f}")
    c3.metric("Bens irrecuperáveis", contagem["Irrecuperável"])

    resumo_df = pd.DataFrame([
        {"Classificação": k, "Quantidade": v}
        for k, v in contagem.items()
    ])
    st.dataframe(resumo_df, use_container_width=True)

# ---------------------------------------------------------
# Geração do PDF
# ---------------------------------------------------------
with st.container(border=True):
    st.subheader("6) Relatório")
    if st.button("🚀 Gerar relatório consolidado em PDF"):
        pdf = gerar_pdf_relatorio(st.session_state.processo, st.session_state.bens)
        st.download_button(
            "📥 Baixar PDF",
            data=pdf,
            file_name="Relatorio_Avaliacao_Bens_Inserviveis.pdf",
            mime="application/pdf"
        )
