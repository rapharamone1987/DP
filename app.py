import streamlit as st
from groq import Groq
import pdfplumber
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import json
import time
import re
from PIL import Image

# =========================================================
# 1. CONFIGURAÇÃO GERAL
# =========================================================
st.set_page_config(
    page_title="Recebimento de Bens e Materiais",
    layout="centered"
)

# =========================================================
# 2. ESTADO INICIAL
# =========================================================
DEFAULT_CABECALHO = {
    "fornecedor": "",
    "edital": "",
    "objeto": ""
}

def inicializar_estado():
    if "items_lista" not in st.session_state:
        st.session_state.items_lista = []

    if "cabecalho" not in st.session_state:
        st.session_state.cabecalho = DEFAULT_CABECALHO.copy()

    if "midia" not in st.session_state:
        st.session_state.midia = {}

    if "conferidos" not in st.session_state:
        st.session_state.conferidos = {}

    if "obs_itens" not in st.session_state:
        st.session_state.obs_itens = {}

    if "camera_ativa" not in st.session_state:
        st.session_state.camera_ativa = None

    if "natureza_ia" not in st.session_state:
        st.session_state.natureza_ia = "Consumo"

inicializar_estado()

# =========================================================
# 3. CONFIGURAÇÃO DA IA
# =========================================================
CHAVE_API = st.secrets["GROQ_API_KEY"] if "GROQ_API_KEY" in st.secrets else ""
client = Groq(api_key=CHAVE_API) if CHAVE_API else None

# =========================================================
# 4. FUNÇÕES DE APOIO
# =========================================================
def tr(texto):
    """
    Normaliza texto para uso no FPDF (latin-1).
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
        .replace("•", "-")
        .replace("→", "->")
    )
    return texto.encode("latin-1", "replace").decode("latin-1")


def limpar_json_ia(texto):
    """
    Extrai o JSON da resposta da IA, mesmo que venha com texto extra.
    """
    if not texto:
        return None

    try:
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        bruto = match.group(0) if match else texto
        return json.loads(bruto)
    except Exception:
        return None


def validar_resposta_ia(resposta):
    """
    Garante formato mínimo esperado.
    """
    if not isinstance(resposta, dict):
        return None

    fornecedor = str(resposta.get("fornecedor", "") or "").strip()
    edital = str(resposta.get("edital", "") or "").strip()
    objeto = str(resposta.get("objeto", "") or "").strip()
    checklist = resposta.get("checklist", [])

    if not isinstance(checklist, list):
        checklist = []

    checklist = [str(item).strip() for item in checklist if str(item).strip()]

    return {
        "fornecedor": fornecedor,
        "edital": edital,
        "objeto": objeto,
        "checklist": checklist
    }


def extrair_dados_ia(pdf_file, natureza):
    """
    Lê as primeiras páginas do PDF e solicita à IA extração de checklist técnico.
    """
    texto_extraido = ""

    try:
        with pdfplumber.open(pdf_file) as pdf:
            for pagina in pdf.pages[:4]:
                texto_extraido += (pagina.extract_text() or "") + "\n"
    except Exception:
        return None

    if not texto_extraido.strip():
        return None

    prompt = (
        "Você é um Especialista em Recebimento de bens públicos. "
        f"Analise o documento para recebimento de item do tipo {natureza}. "
        "Extraia apenas informações objetivas e físicas do item, úteis à conferência no recebimento, "
        "como marca, modelo, dimensões, material, capacidade, potência, voltagem, cor, componentes, acessórios, acabamento, "
        "itens inclusos e demais características verificáveis. "
        "Ignore cláusulas jurídicas, obrigações contratuais genéricas, penalidades, prazos e textos administrativos. "
        "Responda APENAS em JSON válido, sem comentários, no seguinte formato exato: "
        '{"fornecedor": "nome", "edital": "número", "objeto": "descrição", "checklist": ["item 1", "item 2", "item 3"]}'
    )

    if not client:
        return None

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


def processar_imagem_pdf(st_image):
    """
    Converte imagem recebida para JPG temporário.
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
        img.save(temp_path, "JPEG", quality=75)

    return temp_path


def desenhar_check(pdf, x, y, status):
    """
    Desenha indicador visual do item (conforme/não conforme).
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


def limpar_estado():
    st.session_state.items_lista = []
    st.session_state.cabecalho = DEFAULT_CABECALHO.copy()
    st.session_state.midia = {}
    st.session_state.conferidos = {}
    st.session_state.obs_itens = {}
    st.session_state.camera_ativa = None
    st.session_state.natureza_ia = "Consumo"


def excluir_item(indice, uid):
    st.session_state.items_lista.pop(indice)
    st.session_state.conferidos.pop(uid, None)
    st.session_state.midia.pop(uid, None)
    st.session_state.obs_itens.pop(uid, None)
    if st.session_state.camera_ativa == uid:
        st.session_state.camera_ativa = None


# =========================================================
# 5. CLASSE PDF
# =========================================================
class PDFChecklist(FPDF):
    def __init__(self, status_geral=True, data_emissao=""):
        super().__init__()
        self.status_geral = status_geral
        self.data_emissao = data_emissao

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
            self.set_font("Arial", "B", 13)
            self.set_text_color(0)

            titulo = (
                "RELATÓRIO DE RECEBIMENTO TÉCNICO"
                if self.status_geral
                else "RELATÓRIO DE DESCONFORMIDADE TÉCNICA"
            )

            self.cell(0, 8, tr("SECRETARIA DA AGRICULTURA, PECUÁRIA, PRODUÇÃO SUSTENTÁVEL E IRRIGAÇÃO"), 0, 1, "C")
            self.set_font("Arial", "B", 12)
            self.cell(0, 8, tr(titulo), 0, 1, "C")
            self.ln(2)

    def footer(self):
        self.set_y(-13)
        self.set_font("Arial", "I", 7)
        self.set_text_color(90)
        rodape = f"Página {self.page_no()} | Emitido em {self.data_emissao}"
        self.cell(0, 4, tr(rodape), 0, 1, "C")

        self.set_y(-6)
        self.desenhar_faixa_tricolor(291)


# =========================================================
# 6. INTERFACE
# =========================================================
st.title("📋 Checklist Recebimento Técnico RS")

with st.sidebar:
    st.markdown("### Ações")
    if st.button("🔄 Reiniciar aplicação"):
        limpar_estado()
        st.rerun()

# =========================================================
# ETAPA 1 - LEITURA DO PDF
# =========================================================
if not st.session_state.items_lista:
    st.session_state.natureza_ia = st.radio(
        "Natureza do item:",
        ["Consumo", "Permanente"],
        horizontal=True
    )

    pdf_file = st.file_uploader("Suba o PDF do processo / especificação", type=["pdf"])

    col_a, col_b = st.columns([1, 1])
    analisar = col_a.button("🔍 Analisar documento")
    abrir_manual = col_b.button("✍️ Abrir formulário manual")

    if analisar and pdf_file:
        with st.spinner("Lendo documento e montando checklist técnico..."):
            resultado = extrair_dados_ia(pdf_file, st.session_state.natureza_ia)

        if not resultado:
            st.error("Não foi possível extrair dados válidos do PDF. Você pode usar o preenchimento manual.")
        else:
            st.session_state.cabecalho = {
                "fornecedor": resultado.get("fornecedor", ""),
                "edital": resultado.get("edital", ""),
                "objeto": resultado.get("objeto", "")
            }

            checklist = resultado.get("checklist", [])
            if checklist:
                st.session_state.items_lista = [
                    {"id": time.time() + i, "texto": item}
                    for i, item in enumerate(checklist)
                ]
            else:
                st.session_state.items_lista = [
                    {"id": time.time(), "texto": "Novo requisito"}
                ]

            st.rerun()

    if abrir_manual:
        st.session_state.items_lista = [{"id": time.time(), "texto": "Novo requisito"}]
        st.rerun()

# =========================================================
# ETAPA 2 - FORMULÁRIO DE CONFERÊNCIA
# =========================================================
else:
    with st.container(border=True):
        st.write("### 📝 Dados do processo")

        c1, c2 = st.columns(2)

        st.session_state.cabecalho["fornecedor"] = c1.text_input(
            "Fornecedor",
            value=st.session_state.cabecalho.get("fornecedor", "")
        )

        st.session_state.cabecalho["edital"] = c2.text_input(
            "ARP / Edital",
            value=st.session_state.cabecalho.get("edital", "")
        )

        st.session_state.cabecalho["objeto"] = st.text_area(
            "Objeto",
            value=st.session_state.cabecalho.get("objeto", ""),
            height=80
        )

        nf = c1.text_input("Nº Nota Fiscal")
        qtd = c2.text_input("Quantidade")
        placa = c1.text_input("Patrimônio / ID")
        unidade = c2.text_input("Unidade de destino")

        tipo_atesto_ui = st.selectbox(
            "Tipo de atesto no relatório",
            ["Definitivo", "Provisório"]
        )

    st.write("### ✅ Conferência dos requisitos")

    todos_ok = bool(st.session_state.items_lista)

    for i, item_obj in enumerate(st.session_state.items_lista.copy()):
        uid = item_obj["id"]

        with st.container(border=True):
            col_ch, col_tx, col_ex = st.columns([0.15, 0.70, 0.15])

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

            st.session_state.items_lista[i]["texto"] = item_obj["texto"]

            if col_ex.button("🗑️", key=f"del_{uid}"):
                excluir_item(i, uid)
                st.rerun()

            obs_item = st.text_area(
                "Observação / evidência / desconformidade do item",
                value=st.session_state.obs_itens.get(uid, ""),
                key=f"obs_{uid}",
                height=80,
                placeholder="Ex.: cor divergente, medida incompatível, avaria, item ausente, especificação diferente..."
            )
            st.session_state.obs_itens[uid] = obs_item

            if uid not in st.session_state.midia:
                t1, t2 = st.tabs(["📸 Câmera", "📁 Arquivo"])

                with t1:
                    if st.session_state.camera_ativa == uid:
                        foto = st.camera_input("Capturar imagem", key=f"cam_{uid}")
                        if foto:
                            st.session_state.midia[uid] = foto
                            st.session_state.camera_ativa = None
                            st.rerun()
                    else:
                        if st.button("Abrir câmera", key=f"btn_c_{uid}"):
                            st.session_state.camera_ativa = uid
                            st.rerun()

                with t2:
                    up = st.file_uploader(
                        "Upload de imagem",
                        type=["jpg", "jpeg", "png"],
                        key=f"up_{uid}"
                    )
                    if up:
                        st.session_state.midia[uid] = up
                        st.rerun()

            else:
                st.image(st.session_state.midia[uid], width=180)
                if st.button("Remover foto", key=f"rm_{uid}"):
                    st.session_state.midia.pop(uid, None)
                    st.rerun()

    col_add, col_space = st.columns([1, 3])
    if col_add.button("➕ Adicionar requisito"):
        st.session_state.items_lista.append(
            {"id": time.time(), "texto": "Novo requisito"}
        )
        st.rerun()

    st.write("### 📌 Conclusão")
    obs_geral = st.text_area(
        "Observações gerais / justificativa",
        height=120,
        placeholder="Observações complementares do recebimento técnico..."
    )

    col1, col2 = st.columns(2)
    servidor = col1.text_input("Nome do servidor responsável")
    cargo = col2.text_input("Cargo / função", value="Responsável pelo Recebimento")

    # =====================================================
    # GERAÇÃO DO PDF
    # =====================================================
    if st.button("🚀 Gerar relatório"):
        if not servidor.strip():
            st.error("Informe o nome do servidor responsável.")
        elif not st.session_state.items_lista:
            st.error("Nenhum requisito foi informado.")
        elif not st.session_state.cabecalho.get("objeto", "").strip():
            st.error("Informe o objeto do recebimento.")
        else:
            try:
                data_emissao = datetime.now().strftime("%d/%m/%Y %H:%M")

                pdf = PDFChecklist(
                    status_geral=todos_ok,
                    data_emissao=data_emissao
                )
                pdf.alias_nb_pages()
                pdf.set_auto_page_break(auto=True, margin=18)
                pdf.set_margins(15, 12, 15)

                cab = st.session_state.cabecalho

                campos_print = []
                if cab.get("fornecedor", "").strip():
                    campos_print.append(("FORNECEDOR", cab["fornecedor"].upper()))
                if cab.get("edital", "").strip():
                    campos_print.append(("EDITAL / ARP", cab["edital"]))
                if st.session_state.natureza_ia.strip():
                    campos_print.append(("NATUREZA", st.session_state.natureza_ia.upper()))
                if nf.strip():
                    campos_print.append(("NOTA FISCAL", nf))
                if qtd.strip():
                    campos_print.append(("QUANTIDADE", qtd))
                if placa.strip():
                    campos_print.append(("ID / PATRIMÔNIO", placa.upper()))
                if unidade.strip():
                    campos_print.append(("UNIDADE DE DESTINO", unidade.upper()))
                campos_print.append(("DATA/HORA DA EMISSÃO", data_emissao))

                pdf.add_page()

                # Bloco do objeto
                pdf.set_fill_color(99, 157, 49)
                pdf.set_text_color(255)
                pdf.set_font("Arial", "B", 10)
                pdf.multi_cell(
                    0,
                    8,
                    tr(f"OBJETO: {cab['objeto'].upper()}"),
                    border=1,
                    align="L",
                    fill=True
                )

                pdf.set_text_color(0)
                pdf.set_font("Arial", "", 9)

                for label, valor in campos_print:
                    pdf.set_font("Arial", "B", 9)
                    pdf.write(6, tr(f"{label}: "))
                    pdf.set_font("Arial", "", 9)
                    pdf.multi_cell(0, 6, tr(valor), border="B", align="L")

                pdf.ln(3)

                # Título da seção
                pdf.set_font("Arial", "B", 10)
                pdf.set_fill_color(235, 235, 235)
                pdf.cell(0, 7, tr("REQUISITOS CONFERIDOS"), border=1, ln=1, align="C", fill=True)
                pdf.ln(2)

                # Itens
                total_itens = len(st.session_state.items_lista)
                total_ok = 0
                total_nok = 0

                for idx, it in enumerate(st.session_state.items_lista, start=1):
                    uid = it["id"]
                    status_item = st.session_state.conferidos.get(uid, False)
                    obs_item = st.session_state.obs_itens.get(uid, "").strip()

                    if status_item:
                        total_ok += 1
                    else:
                        total_nok += 1

                    if pdf.get_y() > 245:
                        pdf.add_page()

                    desenhar_check(pdf, 16, pdf.get_y() + 1, status_item)
                    pdf.set_x(24)
                    pdf.set_font("Arial", "B", 10)
                    prefixo = f"{idx}. "
                    pdf.multi_cell(170, 6, tr(prefixo + it["texto"]))

                    pdf.set_x(24)
                    pdf.set_font("Arial", "", 9)
                    situacao = "Situação: Conforme" if status_item else "Situação: Não conforme"
                    pdf.multi_cell(170, 5, tr(situacao))

                    if obs_item:
                        pdf.set_x(24)
                        pdf.set_font("Arial", "I", 9)
                        pdf.multi_cell(170, 5, tr(f"Observação: {obs_item}"))

                    if uid in st.session_state.midia:
                        img_temp = processar_imagem_pdf(st.session_state.midia[uid])
                        if img_temp:
                            try:
                                with Image.open(img_temp) as im_f:
                                    largura = im_f.width if im_f.width else 1
                                    altura = im_f.height if im_f.height else 1
                                    altura_pdf = 55 * (altura / largura)

                                if pdf.get_y() + altura_pdf > 260:
                                    pdf.add_page()

                                pdf.image(img_temp, x=70, y=pdf.get_y() + 2, w=55)
                                pdf.set_y(pdf.get_y() + altura_pdf + 5)
                            finally:
                                if os.path.exists(img_temp):
                                    os.unlink(img_temp)

                    pdf.set_draw_color(220, 220, 220)
                    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                    pdf.ln(3)

                # Resumo
                if pdf.get_y() > 230:
                    pdf.add_page()

                pdf.ln(2)
                pdf.set_font("Arial", "B", 10)
                pdf.set_fill_color(240, 240, 240)
                pdf.cell(0, 7, tr("RESUMO DA CONFERÊNCIA"), border=1, ln=1, align="C", fill=True)

                pdf.set_font("Arial", "", 10)
                pdf.multi_cell(
                    0,
                    6,
                    tr(
                        f"Total de requisitos avaliados: {total_itens}\n"
                        f"Itens conformes: {total_ok}\n"
                        f"Itens não conformes: {total_nok}"
                    ),
                    border=1,
                    align="L"
                )

                pdf.ln(3)

                # Conclusão
                at_cor = (235, 245, 235) if todos_ok else (255, 230, 230)
                pdf.set_fill_color(*at_cor)
                pdf.set_font("Arial", "B", 10)

                if todos_ok:
                    mensagem_final = (
                        f"ATESTO O RECEBIMENTO {tipo_atesto_ui.upper()} POR CONFORMIDADE TÉCNICA, "
                        "UMA VEZ QUE OS REQUISITOS VERIFICADOS SE ENCONTRAM ATENDIDOS."
                    )
                else:
                    mensagem_final = (
                        "RELATÓRIO DE DESCONFORMIDADE TÉCNICA: FORAM IDENTIFICADAS INCONSISTÊNCIAS "
                        "EM RELAÇÃO AOS REQUISITOS VERIFICADOS NO RECEBIMENTO."
                    )

                pdf.multi_cell(0, 9, tr(mensagem_final), border=1, align="C", fill=True)

                if obs_geral.strip():
                    pdf.ln(4)
                    pdf.set_font("Arial", "B", 9)
                    pdf.cell(0, 6, tr("OBSERVAÇÕES GERAIS"), 0, 1)
                    pdf.set_font("Arial", "", 9)
                    pdf.multi_cell(0, 5, tr(obs_geral), border=1, align="L")

                # Assinatura
                pdf.ln(12)
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 6, tr(servidor.upper()), 0, 1, "C")
                pdf.set_font("Arial", "", 9)
                pdf.cell(0, 5, tr(cargo), 0, 1, "C")

                pdf_bytes = pdf.output(dest="S").encode("latin-1")

                st.success("Relatório gerado com sucesso.")
                st.download_button(
                    "📥 Baixar PDF",
                    data=pdf_bytes,
                    file_name="Relatorio_Recebimento_Tecnico_RS.pdf",
                    mime="application/pdf"
                )

            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")
