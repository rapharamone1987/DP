import streamlit as st
from groq import Groq
import pdfplumber
from fpdf import FPDF
import tempfile
import os
import json
import time
import re
from PIL import Image

# =========================================================
# 1. INICIALIZAÇÃO SEGURA DO ESTADO
# =========================================================
DEFAULT_CABECALHO = {
    "fornecedor": "",
    "edital": "",
    "objeto": ""
}

if "items_lista" not in st.session_state:
    st.session_state.items_lista = []

if "cabecalho" not in st.session_state:
    st.session_state.cabecalho = DEFAULT_CABECALHO.copy()

if "midia" not in st.session_state:
    st.session_state.midia = {}

if "conferidos" not in st.session_state:
    st.session_state.conferidos = {}

if "camera_ativa" not in st.session_state:
    st.session_state.camera_ativa = None

if "natureza_ia" not in st.session_state:
    st.session_state.natureza_ia = "Consumo"


# =========================================================
# 2. CONFIGURAÇÃO DA IA
# =========================================================
CHAVE_API = st.secrets["GROQ_API_KEY"] if "GROQ_API_KEY" in st.secrets else ""
client = Groq(api_key=CHAVE_API) if CHAVE_API else None


# =========================================================
# 3. FUNÇÕES DE APOIO
# =========================================================
def tr(texto):
    """
    Normaliza texto para o FPDF (latin-1), minimizando quebras por caracteres especiais.
    """
    if texto is None:
        return ""
    texto = str(texto)
    texto = (
        texto.replace("–", "-")
        .replace("—", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("´", "'")
        .replace("`", "'")
    )
    return texto.encode("latin-1", "replace").decode("latin-1")


def limpar_json_ia(texto):
    """
    Tenta extrair um JSON válido da resposta da IA.
    """
    try:
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        bruto = match.group(0) if match else texto
        return json.loads(bruto)
    except Exception:
        return None


def validar_resposta_ia(resposta):
    """
    Garante estrutura mínima esperada:
    {
        "fornecedor": "...",
        "edital": "...",
        "objeto": "...",
        "checklist": ["...", "..."]
    }
    """
    if not isinstance(resposta, dict):
        return None

    fornecedor = resposta.get("fornecedor", "") or ""
    edital = resposta.get("edital", "") or ""
    objeto = resposta.get("objeto", "") or ""
    checklist = resposta.get("checklist", [])

    if not isinstance(checklist, list):
        checklist = []

    checklist = [str(i).strip() for i in checklist if str(i).strip()]

    return {
        "fornecedor": str(fornecedor).strip(),
        "edital": str(edital).strip(),
        "objeto": str(objeto).strip(),
        "checklist": checklist
    }


def extrair_dados_ia(pdf_file, natureza):
    """
    Extrai texto das primeiras páginas do PDF e pede à IA
    para devolver apenas dados técnicos físicos e checklist em JSON.
    """
    texto_extraido = ""

    with pdfplumber.open(pdf_file) as pdf:
        paginas = pdf.pages[:4]
        for pagina in paginas:
            texto_extraido += (pagina.extract_text() or "") + "\n"

    if not texto_extraido.strip():
        return None

    prompt = (
        "Você é um Especialista em Recebimento de bens públicos. "
        f"Analise o documento para recebimento de item do tipo {natureza}. "
        "Extraia apenas informações objetivas e físicas do item, como marca, modelo, dimensões, capacidade, cor, material, voltagem, acessórios, especificações técnicas e demais características verificáveis no recebimento. "
        "Ignore cláusulas jurídicas, penalidades, prazos contratuais, obrigações administrativas, garantias genéricas e textos normativos. "
        "Responda APENAS em JSON válido, SEM explicações, no seguinte formato exato: "
        '{"fornecedor": "nome", "edital": "número", "objeto": "descrição", "checklist": ["item 1", "item 2", "item 3"]}'
    )

    if client:
        try:
            resposta = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "user", "content": prompt + "\n\nDOCUMENTO:\n" + texto_extraido}
                ],
                temperature=0.1
            )
            conteudo = resposta.choices[0].message.content
            return validar_resposta_ia(limpar_json_ia(conteudo))
        except Exception:
            return None

    return None


def processar_imagem_pdf(st_image):
    """
    Converte upload/captura para JPG temporário,
    facilitando inserção no PDF.
    """
    if st_image is None:
        return None

    temp_path = os.path.join(
        tempfile.gettempdir(),
        f"img_{time.time()}_{os.urandom(4).hex()}.jpg"
    )

    with Image.open(st_image) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(temp_path, "JPEG", quality=70)

    return temp_path


def desenhar_check(pdf, x, y, status):
    """
    Desenha indicador circular verde/vermelho.
    """
    cor = (99, 157, 49) if status else (227, 6, 19)

    pdf.set_fill_color(*cor)
    pdf.ellipse(x, y, 5, 5, "F")

    pdf.set_draw_color(255, 255, 255)
    pdf.set_line_width(0.4)

    if status:
        pdf.line(x + 1.2, y + 2.5, x + 2.2, y + 3.8)
        pdf.line(x + 2.2, y + 3.8, x + 3.8, y + 1.5)
    else:
        pdf.line(x + 1.5, y + 1.5, x + 3.5, y + 3.5)
        pdf.line(x + 3.5, y + 1.5, x + 1.5, y + 3.5)

    pdf.set_line_width(0.2)
    pdf.set_draw_color(0, 0, 0)


# =========================================================
# 4. CLASSE PDF (ESTILO RS)
# =========================================================
class PDFChecklist(FPDF):
    def __init__(self, status_geral=True):
        super().__init__()
        self.status_geral = status_geral

    def desenhar_faixa_tricolor(self, y_pos):
        h = 6
        self.set_fill_color(99, 157, 49)
        self.rect(0, y_pos, 70, h, "F")

        self.set_fill_color(227, 6, 19)
        self.rect(70, y_pos, 70, h, "F")

        self.set_fill_color(255, 194, 14)
        self.rect(140, y_pos, 70, h, "F")

    def header(self):
        self.desenhar_faixa_tricolor(0)
        self.set_y(10)

        if self.page_no() == 1:
            self.set_font("Arial", "B", 14)
            self.set_text_color(0)

            titulo = (
                "RELATÓRIO DE RECEBIMENTO TÉCNICO"
                if self.status_geral
                else "SECRETARIA DA AGRICULTURA, PECUÁRIA, PRODUÇÃO SUSTENTÁVEL E IRRIGAÇÃO - RELATÓRIO DE DESCONFORMIDADE TÉCNICA"
            )

            self.cell(0, 10, tr(titulo), 0, 1, "C")

    def footer(self):
        self.set_y(-10)
        self.desenhar_faixa_tricolor(291)

        self.set_y(-18)
        self.set_font("Arial", "I", 7)
        self.set_text_color(100)
        self.cell(0, 10, tr(f"Página {self.page_no()}"), 0, 0, "C")


# =========================================================
# 5. FUNÇÕES DE FLUXO
# =========================================================
def limpar_estado_completo():
    st.session_state.items_lista = []
    st.session_state.cabecalho = DEFAULT_CABECALHO.copy()
    st.session_state.midia = {}
    st.session_state.conferidos = {}
    st.session_state.camera_ativa = None
    st.session_state.natureza_ia = "Consumo"


def excluir_item_por_uid(indice, uid):
    st.session_state.items_lista.pop(indice)
    st.session_state.conferidos.pop(uid, None)
    st.session_state.midia.pop(uid, None)
    if st.session_state.camera_ativa == uid:
        st.session_state.camera_ativa = None


# =========================================================
# 6. INTERFACE
# =========================================================
st.set_page_config(page_title="Recebimento de Bens e Materiais", layout="centered")
st.title("📋 Checklist Recebimento Técnico RS")

with st.sidebar:
    st.markdown("### Ações")
    if st.button("🔄 Reiniciar aplicação"):
        limpar_estado_completo()
        st.rerun()

# ---------------------------------------------------------
# ETAPA 1 - ANÁLISE DO PDF
# ---------------------------------------------------------
if not st.session_state.items_lista:
    st.session_state.natureza_ia = st.radio(
        "Natureza do Item:",
        ["Consumo", "Permanente"],
        horizontal=True
    )

    pdf_file = st.file_uploader("Suba o PDF", type=["pdf"])

    if pdf_file and st.button("🔍 ANALISAR DOCUMENTO"):
        with st.spinner("Extraindo dados do documento..."):
            resultado = extrair_dados_ia(pdf_file, st.session_state.natureza_ia)

        if not resultado:
            st.error("Não foi possível extrair dados válidos do PDF.")
        elif not resultado.get("checklist"):
            st.warning("A análise retornou dados, mas não gerou checklist. Ajuste manualmente após abertura.")
            st.session_state.cabecalho = {
                "fornecedor": resultado.get("fornecedor", ""),
                "edital": resultado.get("edital", ""),
                "objeto": resultado.get("objeto", "")
            }
            st.session_state.items_lista = [
                {"id": time.time(), "texto": "Novo requisito"}
            ]
            st.rerun()
        else:
            st.session_state.cabecalho = {
                "fornecedor": resultado.get("fornecedor", ""),
                "edital": resultado.get("edital", ""),
                "objeto": resultado.get("objeto", "")
            }
            st.session_state.items_lista = [
                {"id": time.time() + i, "texto": txt}
                for i, txt in enumerate(resultado["checklist"])
            ]
            st.rerun()

# ---------------------------------------------------------
# ETAPA 2 - CONFERÊNCIA E GERAÇÃO DO RELATÓRIO
# ---------------------------------------------------------
else:
    with st.container(border=True):
        st.write("### 📝 Dados do Processo")

        c1, c2 = st.columns(2)

        st.session_state.cabecalho["fornecedor"] = c1.text_input(
            "Fornecedor:",
            value=st.session_state.cabecalho.get("fornecedor", "")
        )

        st.session_state.cabecalho["edital"] = c2.text_input(
            "ARP/Edital:",
            value=st.session_state.cabecalho.get("edital", "")
        )

        st.session_state.cabecalho["objeto"] = st.text_area(
            "Objeto:",
            value=st.session_state.cabecalho.get("objeto", ""),
            height=70
        )

        nf = c1.text_input("Nº Nota Fiscal:")
        qtd = c2.text_input("Quantidade:")
        placa = c1.text_input("Patrimônio:")
        unidade = c2.text_input("Unidade de Destino:")

        tipo_atesto_ui = st.selectbox(
            "Tipo de Atesto no PDF:",
            ["Definitivo", "Provisório"]
        )

    st.write("### ✅ Conferência")

    todos_ok = bool(st.session_state.items_lista)

    for i, item_obj in enumerate(st.session_state.items_lista.copy()):
        uid = item_obj["id"]

        with st.container(border=True):
            col_ch, col_tx, col_ex = st.columns([0.15, 0.7, 0.15])

            st.session_state.conferidos[uid] = col_ch.checkbox(
                "OK",
                key=f"ch_{uid}",
                value=st.session_state.conferidos.get(uid, False)
            )

            if not st.session_state.conferidos[uid]:
                todos_ok = False

            item_obj["texto"] = col_tx.text_input(
                "Requisito",
                value=item_obj["texto"],
                key=f"input_{uid}",
                label_visibility="collapsed"
            )

            # Atualiza item no session_state
            st.session_state.items_lista[i]["texto"] = item_obj["texto"]

            if col_ex.button("🗑️", key=f"del_{uid}"):
                excluir_item_por_uid(i, uid)
                st.rerun()

            if uid not in st.session_state.midia:
                t1, t2 = st.tabs(["📸 Câmera", "📁 Arquivo"])

                with t1:
