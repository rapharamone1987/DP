import streamlit as st
from groq import Groq
import pdfplumber
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import io
import json
import time
from PIL import Image

# --- 1. CONFIGURAÇÃO ---
if "GROQ_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GROQ_API_KEY"]
else:
    CHAVE_API = ""

client = Groq(api_key=CHAVE_API) if CHAVE_API else None

# --- 2. FUNÇÕES DE APOIO ---
def tr(texto):
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def extrair_patrimonios_ia(pdf_file):
    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto += pagina.extract_text() + "\n"
    prompt = f"Extraia os Números de Patrimônio deste texto. Retorne APENAS uma lista JSON: [\"num1\", \"num2\"] Texto: {texto}"
    res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
    json_str = res.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    return pd.DataFrame({"PATRIMONIO": json.loads(json_str)})

def processar_imagem_pdf(st_image):
    if st_image is None: return None
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"img_{time.time()}_{os.urandom(4).hex()}.jpg")
    img = Image.open(st_image)
    if img.mode != 'RGB': img = img.convert('RGB')
    img.save(temp_path, "JPEG", quality=70)
    return temp_path

# --- 3. CLASSE PDF (ESTILO RS COM TÍTULO PRETO) ---
class PDFTombamento(FPDF):
    def desenhar_faixa_tricolor(self, y_pos):
        h_faixa = 6
        self.set_fill_color(99, 157, 49) # Verde
        self.rect(0, y_pos, 70, h_faixa, 'F')
        self.set_fill_color(227, 6, 19) # Vermelho
        self.rect(70, y_pos, 70, h_faixa, 'F')
        self.set_fill_color(255, 194, 14) # Amarelo
        self.rect(140, y_pos, 70, h_faixa, 'F')

    def header(self):
        self.desenhar_faixa_tricolor(0)
        if self.page_no() == 1:
            self.set_y(10)
            self.set_font("Arial", 'B', 14)
            self.set_text_color(0, 0, 0) # COR ALTERADA PARA PRETO
            self.cell(0, 10, tr("RELATÓRIO DE TOMBAMENTO PATRIMONIAL"), 0, 1, 'C')
            self.ln(2)

    def footer(self):
        self.set_y(-10)
        self.desenhar_faixa_tricolor(291)
        self.set_y(-18)
        self.set_font("Arial", 'I', 7); self.set_text_color(100)
        self.cell(0, 10, tr(f"Página {self.page_no()}"), 0, 0, 'C')

# --- 4. INTERFACE ---
st.set_page_config(page_title="Tombamento RS", layout="centered")

if "df_patris" not in st.session_state: st.session_state.df_patris = pd.DataFrame()
if "registros" not in st.session_state: st.session_state.registros = {}
if "desc_lote" not in st.session_state: st.session_state.desc_lote = ""
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

st.markdown("""<style>
    .barra-verde { background-color: #639d31; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; margin-bottom: 20px; }
    .stButton>button { width: 100%; border-radius: 10px; font-weight: bold; }
</style>""", unsafe_allow_html=True)

st.title("🛡️ Tombamento Digital")

# --- 5. FASE 1: CARGA ---
if st.session_state.df_patris.empty:
    st.session_state.desc_lote = st.text_area("Descrição do Bem (Única para o lote):")
    t1, t2 = st.tabs(["📄 Extrair PDF", "📊 Colar Lista"])
    with t1:
        file = st.file_uploader("Upload PDF", type="pdf")
        if file and client and st.button("Analisar PDF"):
            st.session_state.df_patris = extrair_patrimonios_ia(file); st.rerun()
    with t2:
        txt = st.text_area("Cole os números:")
        if st.button("Carregar Lista"):
            st.session_state.df_patris = pd.DataFrame({"PATRIMONIO": [l.strip() for l in txt.split('\n') if l.strip()]}); st.rerun()

# --- 6. FASE 2: OPERAÇÃO ---
elif not st.session_state.get("finalizado"):
    st.markdown(f'<div class="barra-verde">{st.session_state.desc_lote.upper()}</div>', unsafe_allow_html=True)
    busca = st.text_input("SCANEAR OU DIGITAR NÚMERO:", key="input_scan").strip()
    
    if busca:
        if busca in st.session_state.df_patris["PATRIMONIO"].astype(str).values:
            st.success(f"✅ Identificado: {busca}")
            serial = st.text_input("Número de Série:", key=f"s_{busca}")
            
            # --- SEÇÃO DE FOTOS COM OPÇÃO DE UPLOAD ---
            c1, c2 = st.columns(2)
            
            # FOTO 1: PLAQUETA
            with c1:
                st.write("**Evidência da Plaqueta**")
                if f"f1_{busca}" not in st.session_state:
                    t_f1_cam, t_f1_arq = st.tabs(["📷 Câmera", "📁 Arquivo"])
                    with t_f1_cam:
                        if st.button("Ligar Câmera", key=f"btn_c1_{busca}"): 
                            st.session_state.camera_ativa = f"f1_{busca}"; st.rerun()
                        if st.session_state.camera_ativa == f"f1_{busca}":
                            f = st.camera_input("Foto", key=f"cam1_{busca}")
                            if f: st.session_state[f"f1_{busca}"] = f; st.session_state.camera_ativa = None; st.rerun()
                    with t_f1_arq:
                        up_f1 = st.file_uploader("Escolher foto", type=['jpg','jpeg','png'], key=f"up1_{busca}")
                        if up_f1: st.session_state[f"f1_{busca}"] = up_f1; st.rerun()
                else:
                    st.image(st.session_state[f"f1_{busca}"], width=150)
                    if st.button("Apagar Foto 1", key=f"del1_{busca}"):
                        del st.session_state[f"f1_{busca}"]; st.rerun()

            # FOTO 2: BEM GERAL
            with c2:
                st.write("**Vista Geral do Bem**")
                if f"f2_{busca}" not in st.session_state:
                    t_f2_cam, t_f2_arq = st.tabs(["📷 Câmera ", "📁 Arquivo "])
                    with t_f2_cam:
                        if st.button("Ligar Câmera ", key=f"btn_c2_{busca}"): 
                            st.session_state.camera_ativa = f"f2_{busca}"; st.rerun()
                        if st.session_state.camera_ativa == f"f2_{busca}":
                            f = st.camera_input("Foto ", key=f"cam2_{busca}")
                            if f: st.session_state[f"f2_{busca}"] = f; st.session_state.camera_ativa = None; st.rerun()
                    with t_f2_arq:
                        up_f2 = st.file_uploader("Escolher foto ", type=['jpg','jpeg','png'], key=f"up2_{busca}")
                        if up_f2: st.session_state[f"f2_{busca}"] = up_f2; st.rerun()
                else:
                    st.image(st.session_state[f"f2_{busca}"], width=150)
                    if st.button("Apagar Foto 2", key=f"del2_{busca}"):
                        del st.session_state[f"f2_{busca}"]; st.rerun()

            if st.button("💾 SALVAR REGISTRO", key=f"sv_{busca}"):
                if f"f2_{busca}" in st.session_state:
                    st.session_state.registros[busca] = {"serial": serial, "img1": st.session_state[f"f1_{busca}"], "img2": st.session_state[f"f2_{busca}"]}
                    st.rerun()
        else: st.error("Patrimônio não listado.")

    if st.session_state.registros:
        st.write("---")
        st.write(f"### 📋 Lançados ({len(st.session_state.registros)})")
        for p in list(st.session_state.registros.keys()):
            col_inf, col_ex = st.columns([0.8, 0.2])
            col_inf.write(f"**P:** {p} | **S:** {st.session_state.registros[p]['serial']}")
            if col_ex.button("🗑️", key=f"del_{p}"): del st.session_state.registros[p]; st.rerun()

    st.divider()
    if st.button("🏁 Finalizar e Gerar PDF"): st.session_state.finalizado = True; st.rerun()

# --- 7. FASE FINAL: PDF ---
elif st.session_state.get("finalizado"):
    servidor = st.text_input("Responsável:")
    setor = st.text_input("Setor:")
    if st.button("🚀 BAIXAR RELATÓRIO"):
        try:
            pdf = PDFTombamento(); pdf.alias_nb_pages(); pdf.set_margins(15, 10, 15)
            lista = list(st.session_state.registros.items())
            for i, (placa, dados) in enumerate(lista):
                if i % 2 == 0: pdf.add_page()
                else:
                    pdf.ln(5); pdf.set_draw_color(200); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(5)

                pdf.set_fill_color(99, 157, 49); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 10)
                pdf.multi_cell(0, 8, tr(f" BEM: {st.session_state.desc_lote.upper()}"), 0, 'L', fill=True)
                pdf.set_text_color(0); pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(240)
                pdf.cell(90, 8, tr(f" PATRIMÔNIO: {placa}"), border=1, fill=True)
                pdf.cell(90, 8, tr(f" SÉRIE: {dados['serial']}"), border=1, ln=True, fill=True)
                pdf.cell(0, 8, tr(f" SETOR: {setor.upper()}"), border=1, ln=True)
                
                pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.set_text_color(99, 157, 49)
                pdf.cell(90, 6, tr("EVIDÊNCIA DA PLAQUETA"), 0, 0, 'C'); pdf.cell(90, 6, tr("VISTA GERAL DO BEM"), 0, 1, 'C')
                
                p1 = processar_imagem_pdf(dados["img1"]); p2 = processar_imagem_pdf(dados["img2"])
                y_fotos = pdf.get_y()
                if p1: pdf.image(p1, x=25, y=y_fotos, w=70, h=52); os.unlink(p1)
                if p2: pdf.image(p2, x=115, y=y_fotos, w=70, h=52); os.unlink(p2)
                
                pdf.set_y(y_fotos + 54); pdf.set_font("Arial", 'I', 8); pdf.set_text_color(0)
                pdf.multi_cell(0, 5, tr("ATESTO O RECEBIMENTO DEFINITIVO do bem acima por conformidade física."), 0, 'C')

                if i == len(lista) - 1:
                    pdf.ln(5); pdf.set_font("Arial", 'B', 10)
                    pdf.cell(0, 5, tr(servidor.upper()), 0, 1, 'C')
                    pdf.set_font("Arial", '', 8); pdf.cell(0, 4, tr("Responsável pelo Tombamento"), 0, 1, 'C')

            st.download_button("📥 Salvar PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="Relatorio_Tombamento.pdf")
        except Exception as e: st.error(f"Erro: {e}")

if st.sidebar.button("Novo Trabalho"): st.session_state.clear(); st.rerun()
