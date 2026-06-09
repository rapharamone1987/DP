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
    
    prompt = f"""Extraia todos os Números de Patrimônio deste texto.
    Retorne APENAS uma lista JSON de strings: ["num1", "num2", "num3"]
    Texto: {texto}"""
    
    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    json_str = res.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    return pd.DataFrame({"PATRIMONIO": json.loads(json_str)})

def salvar_imagem_temp(foto_st):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    temp.write(foto_st.getvalue())
    temp.close() 
    return temp.name

# --- 3. INTERFACE E ESTADO ---
st.set_page_config(page_title="Tombamento em Lote", layout="centered")

if "df_patrimonios" not in st.session_state: st.session_state.df_patrimonios = pd.DataFrame()
if "registros" not in st.session_state: st.session_state.registros = {}
if "desc_unica" not in st.session_state: st.session_state.desc_unica = ""
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

st.markdown("""<style>
    .barra { background-color: #003366; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; }
    .card-busca { background-color: #e3f2fd; border: 2px solid #1976d2; padding: 15px; border-radius: 10px; margin: 10px 0; }
</style>""", unsafe_allow_html=True)

st.title("🛡️ Tombamento (Descrição Única)")

# --- 4. FASE 1: DEFINIÇÃO E CARGA ---
if st.session_state.df_patrimonios.empty:
    st.subheader("1. Configurar Lote de Bens")
    st.session_state.desc_unica = st.text_input("Descrição Padrão do Bem:", placeholder="Ex: Notebook Dell Latitude 3440")
    
    st.write("---")
    st.write("**Carregar Lista de Patrimônios**")
    t1, t2 = st.tabs(["📄 Extrair do PDF", "📊 Colar do Excel/Texto"])
    
    with t1:
        pdf_up = st.file_uploader("Suba o documento com os números", type="pdf")
        if pdf_up and client and st.button("🔍 Analisar PDF"):
            with st.spinner("IA extraindo números..."):
                try:
                    st.session_state.df_patrimonios = extrair_patrimonios_ia(pdf_up)
                    st.rerun()
                except: st.error("Erro na extração. Tente colar os números manualmente.")
                
    with t2:
        txt_nums = st.text_area("Cole a coluna de números de patrimônio aqui:")
        if st.button("Carregar Patrimônios"):
            if txt_nums:
                linhas = [l.strip() for l in txt_nums.split('\n') if l.strip()]
                st.session_state.df_patrimonios = pd.DataFrame({"PATRIMONIO": linhas})
                st.rerun()

# --- 5. FASE 2: REVISÃO ---
elif not st.session_state.get("iniciado"):
    st.subheader("2. Revisar Números Carregados")
    st.write(f"**Descrição:** {st.session_state.desc_unica}")
    st.session_state.df_patrimonios = st.data_editor(st.session_state.df_patrimonios, num_rows="dynamic", use_container_width=True)
    
    if st.button("🚀 Iniciar Coleta no Pátio"):
        if st.session_state.desc_unica:
            st.session_state.iniciado = True
            st.rerun()
        else: st.error("Defina a descrição padrão antes de continuar.")

# --- 6. FASE 3: OPERAÇÃO DE CAMPO ---
elif st.session_state.get("iniciado") and not st.session_state.get("finalizado"):
    st.markdown(f'<div class="barra">{st.session_state.desc_unica.upper()}</div>', unsafe_allow_html=True)
    
    progresso = len(st.session_state.registros)
    total = len(st.session_state.df_patrimonios)
    st.write(f"📊 **Progresso:** {progresso} de {total}")
    
    st.write("### 🔍 Scanear Plaqueta")
    # O foco deve ser sempre aqui para agilizar com o teclado barcode
    busca = st.text_input("AGUARDANDO SCANNER...", key="input_busca").strip()
    
    if busca:
        # Verifica se o número scaneado existe na lista carregada
        if busca in st.session_state.df_patrimonios["PATRIMONIO"].astype(str).values:
            st.markdown(f'<div class="card-busca">✅ <b>PATRIMÔNIO LOCALIZADO:</b> {busca}</div>', unsafe_allow_html=True)
            
            if busca in st.session_state.registros:
                st.warning("Este item já foi registrado.")
            
            serial = st.text_input("Número de Série (Fabricante):", key=f"ser_{busca}")
            
            c1, c2 = st.columns(2)
            with c1:
                if f"f1_{busca}" not in st.session_state:
                    if st.button("📷 Foto Etiqueta"): st.session_state.camera_ativa = "f1"; st.rerun()
                    if st.session_state.camera_ativa == "f1":
                        f1 = st.camera_input("Foto da Plaqueta")
                        if f1: st.session_state[f"f1_{busca}"] = f1; st.session_state.camera_ativa = None; st.rerun()
                else: st.image(st.session_state[f"f1_{busca}"], width=120)

            with c2:
                if f"f2_{busca}" not in st.session_state:
                    if st.button("📷 Foto do Bem"): st.session_state.camera_ativa = "f2"; st.rerun()
                    if st.session_state.camera_ativa == "f2":
                        f2 = st.camera_input("Foto Geral")
                        if f2: st.session_state[f"f2_{busca}"] = f2; st.session_state.camera_ativa = None; st.rerun()
                else: st.image(st.session_state[f"f2_{busca}"], width=120)

            if st.button("💾 SALVAR E PRÓXIMO"):
                if f"f2_{busca}" in st.session_state:
                    st.session_state.registros[busca] = {
                        "placa": busca, "serial": serial,
                        "f1": st.session_state[f"f1_{busca}"], "f2": st.session_state[f"f2_{busca}"]
                    }
                    st.success("Registrado!")
                    time.sleep(0.5)
                    st.rerun() # Limpa o campo de busca para o próximo scan
        else:
            st.error(f"❌ Placa {busca} não encontrada na lista inicial.")

    st.divider()
    if st.button("🏁 Finalizar e Gerar PDF"):
        st.session_state.finalizado = True; st.rerun()

# --- 7. FASE FINAL: PDF ---
elif st.session_state.get("finalizado"):
    servidor = st.text_input("Nome do Servidor:")
    if st.button("🚀 BAIXAR TERMO"):
        try:
            pdf = FPDF(); pdf.set_margins(15, 15, 15)
            for p, r in st.session_state.registros.items():
                pdf.add_page()
                pdf.set_font("Arial", 'B', 16); pdf.cell(180, 10, tr("TERMO DE TOMBAMENTO"), ln=True, align='C')
                pdf.set_fill_color(240); pdf.set_font("Arial", 'B', 11)
                pdf.cell(180, 10, tr(f" ITEM: {st.session_state.desc_unica.upper()}"), border=1, ln=True, fill=True)
                pdf.cell(90, 10, tr(f" PATRIMÔNIO: {r['placa']}"), border=1)
                pdf.cell(90, 10, tr(f" SÉRIE: {r['serial']}"), border=1, ln=True)
                
                p1 = salvar_imagem_temp(r["f1"])
                p2 = salvar_imagem_temp(r["f2"])
                pdf.image(p1, x=15, y=pdf.get_y()+5, w=85)
                pdf.image(p2, x=105, y=pdf.get_y()+5, w=85)
                os.unlink(p1); os.unlink(p2)
            
            pdf_bytes = pdf.output(dest='S')
            if isinstance(pdf_bytes, str): pdf_bytes = pdf_bytes.encode('latin-1')
            st.download_button("📥 Download", data=pdf_bytes, file_name="Termo_Tombamento.pdf")
        except Exception as e: st.error(f"Erro: {e}")

if st.sidebar.button("Limpar Tudo"): st.session_state.clear(); st.rerun()
