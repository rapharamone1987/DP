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
    """Corrige acentuação para PDF Latin-1"""
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
    """Converte UploadedFile do Streamlit em caminho de arquivo temporário seguro"""
    if st_image is None: return None
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"img_{time.time()}.jpg")
    img = Image.open(st_image)
    if img.mode != 'RGB': img = img.convert('RGB')
    img.save(temp_path, "JPEG", quality=75)
    return temp_path

# --- 3. CLASSE PDF (ESTILO CHECKLIST RECEBIMENTO) ---
class PDFTombamento(FPDF):
    def header(self):
        # Faixa Verde Topo
        self.set_fill_color(0, 154, 68) # Verde #009A44
        self.rect(0, 0, 210, 15, 'F')
        
        self.set_y(20)
        self.set_font("Arial", 'B', 16)
        self.set_text_color(0, 154, 68)
        self.cell(0, 10, tr("RELATÓRIO DE TOMBAMENTO PATRIMONIAL"), 0, 1, 'C')
        self.ln(5)

    def footer(self):
        # Faixa Verde Rodapé
        self.set_y(-15)
        self.set_fill_color(0, 154, 68)
        self.rect(0, 282, 210, 15, 'F')
        
        self.set_font("Arial", 'I', 8)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, tr(f"Página {self.page_no()} de {{nb}}"), 0, 0, 'C')

# --- 4. INTERFACE ---
st.set_page_config(page_title="Tombamento Pro", layout="centered")

if "df_patris" not in st.session_state: st.session_state.df_patris = pd.DataFrame()
if "registros" not in st.session_state: st.session_state.registros = {}
if "desc_lote" not in st.session_state: st.session_state.desc_lote = ""
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

st.markdown("""<style>
    .titulo { color: #009A44; font-weight: bold; font-size: 24px; text-align: center; }
    .barra-verde { background-color: #009A44; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; margin-bottom: 20px; }
    .stButton>button { width: 100%; border-radius: 10px; font-weight: bold; height: 3.5em; }
</style>""", unsafe_allow_html=True)

st.title("🛡️ Tombamento Digital")

# --- 5. FASE 1: CARGA ---
if st.session_state.df_patris.empty:
    st.session_state.desc_lote = st.text_input("Descrição Única do Bem:", placeholder="Ex: Cadeira de Escritório Modelo X")
    
    t1, t2 = st.tabs(["📄 Extrair PDF", "📊 Colar Lista"])
    with t1:
        file = st.file_uploader("Suba o PDF", type="pdf")
        if file and client and st.button("Analisar PDF"):
            st.session_state.df_patris = extrair_patrimonios_ia(file)
            st.rerun()
    with t2:
        txt = st.text_area("Cole os números (um por linha):")
        if st.button("Carregar Lista"):
            st.session_state.df_patris = pd.DataFrame({"PATRIMONIO": [l.strip() for l in txt.split('\n') if l.strip()]})
            st.rerun()

# --- 6. FASE 2: OPERAÇÃO ---
elif not st.session_state.get("finalizado"):
    st.markdown(f'<div class="barra-verde">{st.session_state.desc_lote.upper()}</div>', unsafe_allow_html=True)
    
    busca = st.text_input("SCANEAR PLAQUETA:", key="input_scan").strip()
    
    if busca:
        if busca in st.session_state.df_patris["PATRIMONIO"].astype(str).values:
            st.success(f"✅ Item Localizado: {busca}")
            
            serial = st.text_input("Número de Série:", key=f"s_{busca}")
            
            c1, c2 = st.columns(2)
            with c1:
                if f"f1_{busca}" not in st.session_state:
                    if st.button("📷 Foto Plaqueta"): st.session_state.camera_ativa = f"f1_{busca}"; st.rerun()
                    if st.session_state.camera_ativa == f"f1_{busca}":
                        f = st.camera_input("Foto da Plaqueta")
                        if f: st.session_state[f"f1_{busca}"] = f; st.session_state.camera_ativa = None; st.rerun()
                else: st.image(st.session_state[f"f1_{busca}"], width=150)

            with c2:
                if f"f2_{busca}" not in st.session_state:
                    if st.button("📷 Foto do Bem"): st.session_state.camera_ativa = f"f2_{busca}"; st.rerun()
                    if st.session_state.camera_ativa == f"f2_{busca}":
                        f = st.camera_input("Foto Geral")
                        if f: st.session_state[f"f2_{busca}"] = f; st.session_state.camera_ativa = None; st.rerun()
                else: st.image(st.session_state[f"f2_{busca}"], width=150)

            if st.button("💾 SALVAR REGISTRO", key=f"sv_{busca}"):
                if f"f2_{busca}" in st.session_state:
                    st.session_state.registros[busca] = {
                        "placa": busca, "serial": serial,
                        "img1": st.session_state[f"f1_{busca}"],
                        "img2": st.session_state[f"f2_{busca}"]
                    }
                    st.toast("Salvo!", icon="✅")
                    time.sleep(1)
                    st.rerun()
        else: st.error("Placa não encontrada na lista carregada.")

    st.divider()
    st.write(f"**Registrados:** {len(st.session_state.registros)} de {len(st.session_state.df_patris)}")
    if st.button("🏁 Gerar PDF"): st.session_state.finalizado = True; st.rerun()

# --- 7. FASE FINAL: PDF ---
elif st.session_state.get("finalizado"):
    servidor = st.text_input("Nome do Servidor:")
    if st.button("📥 BAIXAR RELATÓRIO PDF"):
        try:
            pdf = PDFTombamento(); pdf.alias_nb_pages(); pdf.set_margins(15, 15, 15)
            
            # Percorre os registros salvos
            for placa, dados in st.session_state.registros.items():
                pdf.add_page()
                
                # Identificação do Item
                pdf.set_fill_color(0, 154, 68)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 10, tr(f" BEM: {st.session_state.desc_lote.upper()}"), 0, 1, 'L', fill=True)
                
                # Dados Técnicos
                pdf.set_text_color(0)
                pdf.set_font("Arial", 'B', 10)
                pdf.set_fill_color(240, 240, 240)
                pdf.cell(90, 10, tr(f" PATRIMÔNIO: {placa}"), border=1, fill=True)
                pdf.cell(90, 10, tr(f" SÉRIE: {dados['serial']}"), border=1, ln=True, fill=True)
                pdf.ln(5)

                # Processamento de Imagens
                p1 = processar_imagem_pdf(dados["img1"])
                p2 = processar_imagem_pdf(dados["img2"])
                
                y_fotos = pdf.get_y()
                if p1: 
                    pdf.image(p1, x=15, y=y_fotos, w=85)
                    os.unlink(p1)
                if p2: 
                    pdf.image(p2, x=110, y=y_fotos, w=85)
                    os.unlink(p2)
                
                pdf.set_y(y_fotos + 68)
                pdf.set_font("Arial", 'I', 9)
                pdf.multi_cell(0, 8, tr("\nAtesto que o bem acima foi devidamente identificado e etiquetado conforme normas patrimoniais."), align='C')

            # Assinatura Final
            pdf.add_page()
            pdf.set_y(120)
            pdf.line(60, pdf.get_y(), 150, pdf.get_y())
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, tr(servidor.upper()), 0, 1, 'C')
            pdf.set_font("Arial", '', 10)
            pdf.cell(0, 10, tr("Responsável pelo Tombamento"), 0, 1, 'C')

            st.download_button("Clique para Salvar", data=pdf.output(dest='S').encode('latin-1'), file_name="Tombamento.pdf", mime="application/pdf")
        except Exception as e: st.error(f"Erro no PDF: {e}")

if st.sidebar.button("Limpar Tudo"): st.session_state.clear(); st.rerun()
