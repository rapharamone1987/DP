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
    # Se já for um caminho de arquivo (da restauração de backup), retorna ele
    if isinstance(st_image, str) and os.path.exists(st_image): return st_image
    
    temp_path = os.path.join(temp_dir, f"img_{time.time()}.jpg")
    img = Image.open(st_image)
    if img.mode != 'RGB': img = img.convert('RGB')
    img.save(temp_path, "JPEG", quality=75)
    return temp_path

# --- 3. CLASSE PDF ---
class PDFTombamento(FPDF):
    def header(self):
        self.set_fill_color(0, 154, 68); self.rect(0, 0, 210, 15, 'F')
        self.set_y(20); self.set_font("Arial", 'B', 16); self.set_text_color(0, 154, 68)
        self.cell(0, 10, tr("RELATÓRIO DE TOMBAMENTO PATRIMONIAL"), 0, 1, 'C'); self.ln(5)
    def footer(self):
        self.set_y(-15); self.set_fill_color(0, 154, 68); self.rect(0, 282, 210, 15, 'F')
        self.set_font("Arial", 'I', 8); self.set_text_color(255, 255, 255)
        self.cell(0, 10, tr(f"Página {self.page_no()}"), 0, 0, 'C')

# --- 4. INTERFACE E ESTADO ---
st.set_page_config(page_title="Tombamento Anti-Falha", layout="centered")

if "df_patris" not in st.session_state: st.session_state.df_patris = pd.DataFrame()
if "registros" not in st.session_state: st.session_state.registros = {}
if "desc_lote" not in st.session_state: st.session_state.desc_lote = ""
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

st.markdown("""<style>
    .barra-verde { background-color: #009A44; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; margin-bottom: 20px; }
    .stButton>button { width: 100%; border-radius: 10px; font-weight: bold; }
</style>""", unsafe_allow_html=True)

# --- SIDEBAR: O COFRE DE SEGURANÇA ---
with st.sidebar:
    st.header("🔐 Segurança de Dados")
    if st.session_state.registros:
        # Criar dados para backup (transforma imagens em bytes para salvar)
        backup_data = {
            "desc_lote": st.session_state.desc_lote,
            "df_patris": st.session_state.df_patris.to_json(),
            "registros_keys": list(st.session_state.registros.keys())
        }
        st.download_button("💾 Baixar Backup Atual", 
                           data=json.dumps(backup_data), 
                           file_name=f"backup_tombamento_{datetime.now().strftime('%H%M')}.json",
                           help="Se a internet cair, você usa este arquivo para recuperar tudo.")
    
    st.write("---")
    upload_backup = st.file_uploader("📂 Restaurar de Backup", type="json")
    if upload_backup:
        back = json.loads(upload_backup.read())
        st.session_state.desc_lote = back["desc_lote"]
        st.session_state.df_patris = pd.read_json(io.StringIO(back["df_patris"]))
        st.success("Backup carregado! (Nota: Fotos precisam ser tiradas novamente ou gerenciadas via DB para persistência total)")

st.title("🛡️ Tombamento Digital")

# --- 5. FASE 1: CARGA ---
if st.session_state.df_patris.empty:
    st.session_state.desc_lote = st.text_input("Descrição Única do Bem:")
    t1, t2 = st.tabs(["📄 PDF", "📊 Lista"])
    with t1:
        file = st.file_uploader("PDF", type="pdf")
        if file and client and st.button("Analisar PDF"):
            st.session_state.df_patris = extrair_patrimonios_ia(file); st.rerun()
    with t2:
        txt = st.text_area("Números:")
        if st.button("Carregar"):
            st.session_state.df_patris = pd.DataFrame({"PATRIMONIO": [l.strip() for l in txt.split('\n') if l.strip()]}); st.rerun()

# --- 6. FASE 2: OPERAÇÃO ---
elif not st.session_state.get("finalizado"):
    st.markdown(f'<div class="barra-verde">{st.session_state.desc_lote.upper()}</div>', unsafe_allow_html=True)
    busca = st.text_input("SCANEAR OU DIGITAR PLAQUETA:", key="input_scan").strip()
    
    if busca:
        if busca in st.session_state.df_patris["PATRIMONIO"].astype(str).values:
            st.success(f"✅ Patrimônio: {busca}")
            serial = st.text_input("Série:", key=f"s_{busca}")
            
            c1, c2 = st.columns(2)
            with c1:
                if f"f1_{busca}" not in st.session_state:
                    if st.button("📷 Foto Plaqueta"): st.session_state.camera_ativa = f"f1_{busca}"; st.rerun()
                    if st.session_state.camera_ativa == f"f1_{busca}":
                        f = st.camera_input("Traseira", key=f"c1_{busca}", facing_mode="environment")
                        if f: st.session_state[f"f1_{busca}"] = f; st.session_state.camera_ativa = None; st.rerun()
                else:
                    st.image(st.session_state[f"f1_{busca}"], width=150)
                    if st.button("🗑️ Apagar", key=f"d1_{busca}"): del st.session_state[f"f1_{busca}"]; st.rerun()

            with c2:
                if f"f2_{busca}" not in st.session_state:
                    if st.button("📷 Foto Bem"): st.session_state.camera_ativa = f"f2_{busca}"; st.rerun()
                    if st.session_state.camera_ativa == f"f2_{busca}":
                        f = st.camera_input("Traseira ", key=f"c2_{busca}", facing_mode="environment")
                        if f: st.session_state[f"f2_{busca}"] = f; st.session_state.camera_ativa = None; st.rerun()
                else:
                    st.image(st.session_state[f"f2_{busca}"], width=150)
                    if st.button("🗑️ Apagar ", key=f"d2_{busca}"): del st.session_state[f"f2_{busca}"]; st.rerun()

            if st.button("💾 SALVAR", key=f"sv_{busca}"):
                if f"f2_{busca}" in st.session_state:
                    st.session_state.registros[busca] = {"serial": serial, "img1": st.session_state[f"f1_{busca}"], "img2": st.session_state[f"f2_{busca}"]}
                    st.rerun()
        else: st.error("Não encontrado.")

    if st.session_state.registros:
        st.write("### 📋 Lançados")
        for p in list(st.session_state.registros.keys()):
            col_inf, col_ex = st.columns([0.8, 0.2])
            col_inf.write(f"Patr: {p} | Série: {st.session_state.registros[p]['serial']}")
            if col_ex.button("🗑️", key=f"del_item_{p}"): del st.session_state.registros[p]; st.rerun()

    st.divider()
    if st.button("🏁 Finalizar e Gerar PDF"): st.session_state.finalizado = True; st.rerun()

# --- 7. FASE FINAL: PDF ---
elif st.session_state.get("finalizado"):
    servidor = st.text_input("Responsável:")
    setor = st.text_input("Setor:")
    if st.button("🚀 BAIXAR TERMO"):
        try:
            pdf = PDFTombamento(); pdf.alias_nb_pages(); pdf.set_margins(15, 15, 15)
            lista = list(st.session_state.registros.items())
            for i, (placa, dados) in enumerate(lista):
                pdf.add_page()
                pdf.set_fill_color(0, 154, 68); pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 10, tr(f" BEM: {st.session_state.desc_lote.upper()}"), 0, 1, 'L', fill=True)
                pdf.set_text_color(0); pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(240, 240, 240)
                pdf.cell(90, 10, tr(f" PATRIMÔNIO: {placa}"), border=1, fill=True)
                pdf.cell(90, 10, tr(f" SÉRIE: {dados['serial']}"), border=1, ln=True, fill=True)
                pdf.cell(180, 10, tr(f" SETOR: {setor.upper()}"), border=1, ln=True)
                pdf.ln(5); pdf.set_font("Arial", 'B', 9); pdf.set_text_color(0, 154, 68)
                pdf.cell(90, 8, tr("EVIDÊNCIA DA PLAQUETA"), 0, 0, 'C'); pdf.cell(90, 8, tr("VISTA GERAL DO BEM"), 0, 1, 'C')
                
                p1 = processar_imagem_pdf(dados["img1"]); p2 = processar_imagem_pdf(dados["img2"])
                if p1: pdf.image(p1, x=15, y=pdf.get_y(), w=85, h=65); os.unlink(p1)
                if p2: pdf.image(p2, x=110, y=pdf.get_y(), w=85, h=65); os.unlink(p2)
                
                pdf.set_y(pdf.get_y() + 68); pdf.set_font("Arial", 'I', 9); pdf.set_text_color(0)
                pdf.multi_cell(0, 8, tr("ATESTO O RECEBIMENTO DEFINITIVO do(s) bem(ns) acima descrito(s) por conformidade física nesta data."), align='C')
                if i == len(lista) - 1:
                    if pdf.get_y() > 240: pdf.add_page()
                    pdf.ln(10); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, tr(servidor.upper()), 0, 1, 'C')
                    pdf.set_font("Arial", '', 9); pdf.cell(0, 5, tr("Responsável pelo Tombamento"), 0, 1, 'C')
            st.download_button("Salvar PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="Termo.pdf")
        except Exception as e: st.error(f"Erro: {e}")

if st.sidebar.button("Reiniciar"): st.session_state.clear(); st.rerun()
