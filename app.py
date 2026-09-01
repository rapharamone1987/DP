import io
import json
import os
import re
import tempfile
import time
from datetime import datetime

from fpdf import FPDF
from groq import Groq
import pandas as pd
import pdfplumber
from PIL import Image
import streamlit as st

# ==========================================
# 1. INICIALIZAÇÃO OBRIGATÓRIA (TOPO ABSOLUTO)
# ==========================================
if "items_lista" not in st.session_state:
    st.session_state.items_lista = []
if "cabecalho" not in st.session_state:
    st.session_state.cabecalho = {
        "fornecedor": "",
        "edital": "",
        "objeto": "",
        "nf": "",
        "qtd": "",
        "placa": "",
        "unidade": "",
    }
if "registros_media" not in st.session_state:
    st.session_state.registros_media = {}
if "conferidos_status" not in st.session_state:
    st.session_state.conferidos_status = {}
if "camera_ativa" not in st.session_state:
    st.session_state.camera_ativa = None
if "atesto_tipo_final" not in st.session_state:
    st.session_state.atesto_tipo_final = "Definitivo"
if "texto_pdf" not in st.session_state:
    st.session_state.texto_pdf = ""

# CONFIGURAÇÃO DA IA (GROQ)
key = st.secrets.get("GROQ_API_KEY", "")
client = Groq(api_key=key) if key else None
MODELO_ID = "llama-3.3-70b-versatile"


# ==========================================
# 2. FUNÇÕES DE APOIO
# ==========================================
def tr(texto):
    """Trata acentuação para PDF Latin-1"""
    if not texto:
        return ""
    return str(texto).encode("latin-1", "replace").decode("latin-1")


def limpar_json_ia(texto):
    try:
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        return json.loads(match.group(0)) if match else json.loads(texto)
    except Exception:
        return None


def extrair_dados_ia(texto_entrada):
    prompt = (
        "Você é um Auditor de Recebimento de Materiais. Analise o texto e extraia "
        "detalhes técnicos FÍSICOS REAIS (Marca, modelo, peças, medidas, hardware). "
        "IGNORE cláusulas jurídicas, prazos de entrega ou multas. "
        "Extraia apenas o que o fiscal pode tocar ou medir. Responda APENAS JSON: "
        '{"fornecedor": "nome", "edital": "número", "objeto": "descrição", "checklist": ["item 1", "item 2"]}'
    )
    if client:
        try:
            res = client.chat.completions.create(
                model=MODELO_ID,
                messages=[
                    {
                        "role": "user",
                        "content": f"{prompt}\n\nTexto do Documento:\n{texto_entrada}",
                    }
                ],
                temperature=0.1,
            )
            return limpar_json_ia(res.choices[0].message.content)
        except Exception as e:
            st.error(f"Erro ao comunicar com a IA: {e}")
            return None
    return None


def perguntar_ia(pergunta, contexto):
    if client and contexto:
        try:
            prompt = f"Responda de forma curta baseada no documento: {pergunta}\n\nDocumento:\n{contexto[:10000]}"
            res = client.chat.completions.create(
                model=MODELO_ID,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            return res.choices[0].message.content
        except Exception as e:
            return f"Erro na consulta: {e}"
    return "Nenhum documento disponível ou chave de API não configurada."


def processar_imagem_pdf(st_image):
    if st_image is None:
        return None
    temp_path = os.path.join(
        tempfile.gettempdir(), f"img_{time.time()}_{os.urandom(4).hex()}.jpg"
    )
    img = Image.open(st_image)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(temp_path, "JPEG", quality=70)
    return temp_path


def desenhar_check(pdf, x, y, status):
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


# ==========================================
# 3. CLASSE PDF RS (LAYOUT PREMIUM)
# ==========================================
class PDFRS(FPDF):
    def __init__(self, status_geral=True):
        super().__init__()
        self.status_geral = status_geral

    def faixa(self, y):
        self.set_fill_color(99, 157, 49)
        self.rect(0, y, 70, 6, "F")  # Verde
        self.set_fill_color(227, 6, 19)
        self.rect(70, y, 70, 6, "F")  # Vermelho
        self.set_fill_color(255, 194, 14)
        self.rect(140, y, 70, 6, "F")  # Amarelo

    def header(self):
        self.faixa(0)
        self.set_y(10)
        self.set_font("Arial", "B", 10)
        self.set_text_color(0)
        self.cell(
            0,
            6,
            tr(
                "SECRETARIA DA AGRICULTURA, PECUÁRIA, PRODUÇÃO SUSTENTÁVEL E IRRIGAÇÃO"
            ),
            0,
            1,
            "C",
        )
        self.set_font("Arial", "B", 14)
        t = (
            "RELATÓRIO DE RECEBIMENTO TÉCNICO"
            if self.status_geral
            else "RELATÓRIO DE DESCONFORMIDADE TÉCNICA"
        )
        self.cell(0, 8, tr(t), 0, 1, "C")

    def footer(self):
        self.set_y(-10)
        self.faixa(291)
        self.set_y(-18)
        self.set_font("Arial", "I", 7)
        self.set_text_color(100)
        self.cell(0, 10, tr(f"Página {self.page_no()}"), 0, 0, "C")


# ==========================================
# 4. INTERFACE STREAMLIT
# ==========================================
st.set_page_config(page_title="Recebimento RS", layout="centered")
st.title("📋 Checklist Recebimento Técnico RS")

if not st.session_state.items_lista:
    tabs = st.tabs(["📄 Analisar PDF", "✍️ Colar Texto", "🖊️ Manual"])
    with tabs[0]:
        pdf_file = st.file_uploader("Upload PDF", type="pdf")
        if pdf_file and st.button("🔍 ANALISAR DOCUMENTO"):
            with st.spinner("IA (70B) extraindo dados..."):
                texto = ""
                pdf_file.seek(0)
                
                # Leitura em memória via BytesIO
                with pdfplumber.open(io.BytesIO(pdf_file.read())) as pdf:
                    for pg in pdf.pages[:6]:
                        ext = pg.extract_text()
                        if ext:
                            texto += ext + "\n"
                
                if not texto.strip():
                    st.error("⚠️ Não foi possível extrair texto do PDF. Verifique se o arquivo não é uma imagem digitalizada sem camada de texto (OCR).")
                else:
                    st.session_state.texto_pdf = texto
                    res = extrair_dados_ia(texto)
                    if res:
                        st.session_state.cabecalho.update(
                            {k: res.get(k, "") for k in st.session_state.cabecalho}
                        )
                        st.session_state.items_lista = [
                            {"id": time.time() + i, "texto": txt}
                            for i, txt in enumerate(res.get("checklist", []))
                        ]
                        st.rerun()
                    else:
                        st.warning("⚠️ O documento foi lido, mas a IA não identificou os requisitos no formato esperado.")

    with tabs[1]:
        txt_col = st.text_area("Cole as especificações aqui:")
        if st.button("🚀 Gerar do Texto") and txt_col:
            st.session_state.texto_pdf = txt_col
            res = extrair_dados_ia(txt_col)
            if res:
                st.session_state.cabecalho.update(
                    {k: res.get(k, "") for k in st.session_state.cabecalho}
                )
                st.session_state.items_lista = [
                    {"id": time.time() + i, "texto": txt}
                    for i, txt in enumerate(res.get("checklist", []))
                ]
                st.rerun()

    with tabs[2]:
        if st.button("🖊️ Iniciar em Branco"):
            st.session_state.items_lista = [
                {"id": time.time(), "texto": "Novo requisito"}
            ]
            st.rerun()

elif st.session_state.items_lista:
    if st.session_state.texto_pdf:
        with st.expander("🤖 Chat Suporte com a IA"):
            p = st.text_input("Qual detalhe você quer confirmar?")
            if st.button("Perguntar"):
                st.info(
                    f"**IA:** {perguntar_ia(p, st.session_state.texto_pdf)}"
                )

    obj_tit = st.session_state.cabecalho["objeto"].upper()
    st.markdown(
        f'<div style="background-color:#639d31;color:white;padding:10px;border-radius:5px;font-weight:bold;text-align:center;margin-bottom:20px;">ITEM: {obj_tit}</div>',
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.write("### 📝 Dados Editáveis")
        c1, c2 = st.columns(2)
        st.session_state.cabecalho["fornecedor"] = c1.text_input(
            "Fornecedor:", value=st.session_state.cabecalho["fornecedor"]
        )
        st.session_state.cabecalho["edital"] = c2.text_input(
            "ARP/Edital:", value=st.session_state.cabecalho["edital"]
        )
        st.session_state.cabecalho["objeto"] = st.text_area(
            "Descrição Item:",
            value=st.session_state.cabecalho["objeto"],
            height=70,
        )
        nf = c1.text_input(
            "NF:", value=st.session_state.cabecalho.get("nf", "")
        )
        qtd = c2.text_input(
            "Qtd:", value=st.session_state.cabecalho.get("qtd", "")
        )
        placa = c1.text_input(
            "ID:", value=st.session_state.cabecalho.get("placa", "")
        )
        unidade = c2.text_input(
            "Unidade Destino:",
            value=st.session_state.cabecalho.get("unidade", ""),
        )
        st.session_state.atesto_tipo_final = st.selectbox(
            "Tipo de Atesto:", ["Definitivo", "Provisório"]
        )

    st.write("### ✅ Checklist")
    todos_ok = True
    for i, itm in enumerate(st.session_state.items_lista):
        uid = itm["id"]
        with st.container(border=True):
            col_ch, col_tx, col_ex = st.columns([0.15, 0.7, 0.15])
            st.session_state.conferidos_status[uid] = col_ch.checkbox(
                "OK",
                key=f"ch_{uid}",
                value=st.session_state.conferidos_status.get(uid, False),
            )
            if not st.session_state.conferidos_status[uid]:
                todos_ok = False
            itm["texto"] = col_tx.text_input(
                f"txt{uid}",
                itm["texto"],
                key=f"in_{uid}",
                label_visibility="collapsed",
            )
            if col_ex.button("🗑️", key=f"del_{uid}"):
                st.session_state.items_lista.pop(i)
                st.rerun()

            if uid not in st.session_state.registros_media:
                t1, t2 = st.tabs(["📸 Câmera", "📁 Galeria"])
                with t1:
                    if st.session_state.camera_ativa == uid:
                        f = st.camera_input("Foto", key=f"cam_{uid}")
                        if f:
                            st.session_state.registros_media[uid] = f
                            st.session_state.camera_ativa = None
                            st.rerun()
                    elif st.button("Abrir Câmera", key=f"btn_c_{uid}"):
                        st.session_state.camera_ativa = uid
                        st.rerun()
                with t2:
                    up = st.file_uploader("Upload", key=f"up_{uid}")
                    if up:
                        st.session_state.registros_media[uid] = up
                        st.rerun()
            else:
                st.image(st.session_state.registros_media[uid], width=150)
                if st.button("Remover Foto", key=f"rm_{uid}"):
                    del st.session_state.registros_media[uid]
                    st.rerun()

    if st.button("➕ Adicionar Requisito"):
        st.session_state.items_lista.append(
            {"id": time.time(), "texto": "Novo requisito"}
        )
        st.rerun()

    obs_geral = st.text_area("Justificativa / Obs:")
    servidor = st.text_input("Responsável:")

    if st.button("🚀 GERAR RELATÓRIO FINAL"):
        if not servidor:
            st.error("Informe o servidor responsável.")
        else:
            try:
                pdf = PDFRS(status_geral=todos_ok)
                pdf.alias_nb_pages()
                pdf.set_margins(15, 10, 15)
                cab = st.session_state.cabecalho

                def imp_cab(pdf_obj):
                    pdf_obj.set_fill_color(99, 157, 49)
                    pdf_obj.set_text_color(255)
                    pdf_obj.set_font("Arial", "B", 10)
                    pdf_obj.multi_cell(
                        0,
                        8,
                        tr(f" ITEM: {cab['objeto'].upper()}"),
                        1,
                        "L",
                        fill=True,
                    )
                    pdf_obj.set_text_color(0)
                    pdf_obj.set_font("Arial", "", 9)
                    pdf_obj.set_fill_color(245)
                    campos = [
                        ("FORNECEDOR", cab["fornecedor"]),
                        ("ARP", cab["edital"]),
                        ("NF", nf),
                        ("QTD", qtd),
                        ("ID", placa),
                        ("UNIDADE", unidade),
                    ]
                    for l, v in campos:
                        if v:
                            pdf_obj.set_font("Arial", "B", 9)
                            pdf_obj.write(7, tr(f" {l}: "))
                            pdf_obj.set_font("Arial", "", 9)
                            pdf_obj.multi_cell(
                                0, 7, tr(v.upper()), "B", "L", False
                            )
                    pdf_obj.ln(4)

                pdf.add_page()
                imp_cab(pdf)

                for it in st.session_state.items_lista:
                    if pdf.get_y() > 240:
                        pdf.add_page()
                        imp_cab(pdf)
                    desenhar_check(
                        pdf,
                        17,
                        pdf.get_y() + 1,
                        st.session_state.conferidos_status.get(
                            it["id"], False
                        ),
                    )
                    pdf.set_x(25)
                    pdf.set_font("Arial", "B", 10)
                    pdf.multi_cell(165, 6, tr(it["texto"]))

                    if it["id"] in st.session_state.registros_media:
                        img_p = processar_imagem_pdf(
                            st.session_state.registros_media[it["id"]]
                        )
                        if img_p:
                            try:
                                with Image.open(img_p) as im:
                                    p_h = 60 * (im.height / im.width)
                                if pdf.get_y() + p_h > 260:
                                    pdf.add_page()
                                    imp_cab(pdf)
                                pdf.image(
                                    img_p, x=75, y=pdf.get_y() + 1, w=50
                                )
                                pdf.set_y(pdf.get_y() + p_h + 4)
                            finally:
                                if os.path.exists(img_p):
                                    os.unlink(img_p)

                    pdf.ln(2)
                    pdf.set_draw_color(220)
                    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                    pdf.ln(2)

                if pdf.get_y() > 220:
                    pdf.add_page()
                    imp_cab(pdf)

                at_cor = (235, 245, 235) if todos_ok else (255, 230, 230)
                pdf.set_fill_color(*at_cor)
                pdf.set_font("Arial", "B", 10)
                msg = (
                    f"ATESTO O RECEBIMENTO {st.session_state.atesto_tipo_final.upper()} por conformidade técnica."
                    if todos_ok
                    else "RELATÓRIO DE DESCONFORMIDADE TÉCNICA."
                )
                pdf.multi_cell(0, 10, tr(msg), 1, "C", fill=True)

                if obs_geral:
                    pdf.ln(4)
                    pdf.set_font("Arial", "B", 9)
                    pdf.cell(0, 6, tr("OBSERVAÇÕES:"), 0, 1)
                    pdf.multi_cell(0, 5, tr(obs_geral), 1)

                pdf.ln(10)
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 6, tr(servidor.upper()), 0, 1, "C")
                pdf.set_font("Arial", "", 9)
                pdf.cell(
                    0, 5, tr("Responsável pelo Recebimento"), 0, 1, "C"
                )

                st.download_button(
                    "📥 Baixar PDF",
                    data=pdf.output(dest="S").encode("latin-1"),
                    file_name="Relatorio_Recebimento.pdf",
                    mime="application/pdf",
                )
            except Exception as e:
                st.error(f"Erro ao gerar o PDF: {e}")

if st.sidebar.button("Reset Total"):
    st.session_state.clear()
    st.rerun()
