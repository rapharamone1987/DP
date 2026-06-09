import streamlit as st
from groq import Groq
import pdfplumber
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import io
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

def extrair_dados_ia(pdf_file):
    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto += pagina.extract_text() + "\n"
    
    prompt = f"""Extraia uma tabela de bens deste texto. 
    Retorne no formato CSV usando ponto-e-vírgula (;). 
    Colunas: PATRIMONIO;ITEM
    Texto: {texto}"""
    
    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    # Tenta limpar a resposta para pegar só o CSV
    csv_raw = res.choices[0].message.content
    if "```" in csv_raw:
        csv_raw = csv_raw.split("```")[1].replace("csv", "").strip()
    return pd.read_csv(io.StringIO(csv_raw), sep=';')

# --- 3. INTERFACE E ESTADO ---
st.set_page_config(page_title="Tombamento por Busca", layout="centered")

if "df_bens" not in st.session_state: st.session_state.df_bens = pd.DataFrame()
if "registros" not in st.session_state: st.session_state.registros = {}
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

st.markdown("""<style>
    .barra { background-color: #004d00; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; }
    .stButton>button { width: 100%; border-radius: 10px; font-weight: bold; }
    .found-card { background-color: #e8f5e9; border: 2px solid #2e7d32; padding: 15px; border-radius: 10px; margin: 10px 0; }
</style>""", unsafe_allow_html=True)

st.title("🛡️ Sistema de Tombamento e Busca")

# --- 4. FASE 1: CARGA E EDIÇÃO ---
if st.session_state.df_bens.empty:
    st.subheader("1. Carregar Tabela de Bens")
    tab1, tab2 = st.tabs(["📄 Extrair do PDF (IA)", "📊 Colar do Excel"])
    
    with tab1:
        pdf_up = st.file_uploader("Suba o arquivo", type="pdf")
        if pdf_up and client and st.button("Analisar PDF"):
            with st.spinner("IA extraindo patrimônios..."):
                try:
                    st.session_state.df_bens = extrair_dados_ia(pdf_up)
                    st.rerun()
                except: st.error("Erro na extração. Tente colar os dados na aba ao lado.")
                
    with tab2:
        txt_csv = st.text_area("Cole as colunas Patrimônio e Item aqui:")
        if st.button("Carregar Dados"):
            try:
                st.session_state.df_bens = pd.read_csv(io.StringIO(txt_csv), sep=None, engine='python')
                st.session_state.df_bens.columns = ["PATRIMONIO", "ITEM"] # Padroniza nomes
                st.rerun()
            except: st.error("Erro no formato. Certifique-se de ter as colunas Patrimônio e Item.")

# --- 5. FASE 2: EDIÇÃO E FILTRO ---
elif not st.session_state.get("iniciado"):
    st.subheader("2. Revisar Tabela")
    st.info("Verifique os números de patrimônio e exclua as linhas desnecessárias.")
    
    # Editor dinâmico (permite deletar linhas e editar números)
    st.session_state.df_bens = st.data_editor(st.session_state.df_bens, num_rows="dynamic", use_container_width=True)
    
    if st.button("🚀 Iniciar Operação de Campo"):
        st.session_state.iniciado = True
        st.rerun()

# --- 6. FASE 3: BUSCA E REGISTRO ---
elif st.session_state.get("iniciado") and not st.session_state.get("finalizado"):
    st.markdown('<div class="barra">BUSCA E IDENTIFICAÇÃO</div>', unsafe_allow_html=True)
    
    # Progresso
    total = len(st.session_state.df_bens)
    concluidos = len(st.session_state.registros)
    st.write(f"📊 **Status:** {concluidos} de {total} registrados.")

    # BUSCA
    st.write("### 🔍 Scanear ou Digitar Plaqueta")
    busca = st.text_input("FOQUE O SCANNER NESTE CAMPO:", key="input_busca")
    
    if busca:
        # Tenta encontrar o número na coluna PATRIMONIO (convertendo para string para comparar)
        item_match = st.session_state.df_bens[st.session_state.df_bens["PATRIMONIO"].astype(str) == str(busca)]
        
        if not item_match.empty:
            nome_item = item_match.iloc[0]["ITEM"]
            st.markdown(f"""<div class="found-card">
                <b>✅ ITEM LOCALIZADO:</b><br>{nome_item}<br>
                <b>Patrimônio:</b> {busca}
            </div>""", unsafe_allow_html=True)
            
            # Se já foi registrado, avisa
            if busca in st.session_state.registros:
                st.warning("⚠️ Este item já foi registrado anteriormente.")
                if st.button("Ver Registro"): st.write(st.session_state.registros[busca])
            
            # Campos para complementar
            serial = st.text_input("Número de Série (Fabricante):", key=f"ser_{busca}")
            
            c1, c2 = st.columns(2)
            # FOTO 1: ETIQUETA
            with c1:
                if f"f1_{busca}" not in st.session_state:
                    if st.button("📷 Foto Etiqueta"): st.session_state.camera_ativa = "f1"; st.rerun()
                    if st.session_state.camera_ativa == "f1":
                        f1 = st.camera_input("Foque na Etiqueta Colada")
                        if f1: st.session_state[f"f1_{busca}"] = f1; st.session_state.camera_ativa = None; st.rerun()
                else: st.image(st.session_state[f"f1_{busca}"], width=120)

            # FOTO 2: GERAL
            with c2:
                if f"f2_{busca}" not in st.session_state:
                    if st.button("📷 Foto do Bem"): st.session_state.camera_ativa = "f2"; st.rerun()
                    if st.session_state.camera_ativa == "f2":
                        f2 = st.camera_input("Foque no Bem Inteiro")
                        if f2: st.session_state[f"f2_{busca}"] = f2; st.session_state.camera_ativa = None; st.rerun()
                else: st.image(st.session_state[f"f2_{busca}"], width=120)

            if st.button("💾 SALVAR REGISTRO"):
                if serial and f"f2_{busca}" in st.session_state:
                    st.session_state.registros[busca] = {
                        "item": nome_item,
                        "patrimonio": busca,
                        "serial": serial,
                        "foto_fixa": st.session_state[f"f1_{busca}"],
                        "foto_geral": st.session_state[f"f2_{busca}"]
                    }
                    st.success("Salvo com sucesso!")
                    time.sleep(1)
                    st.rerun()
                else: st.error("Preencha o Serial e as Fotos.")
        else:
            st.error(f"❌ Patrimônio {busca} não encontrado na lista carregada.")

    st.divider()
    if st.button("🏁 Finalizar e Gerar Termo"):
        st.session_state.finalizado = True; st.rerun()

# --- 7. FASE FINAL: PDF ---
elif st.session_state.get("finalizado"):
    servidor = st.text_input("Nome do Servidor:")
    if st.button("🚀 BAIXAR PDF"):
        pdf = FPDF(); pdf.set_margins(15, 15, 15)
        for p, r in st.session_state.registros.items():
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16); pdf.set_text_color(0, 77, 0)
            pdf.cell(180, 10, tr("TERMO DE TOMBAMENTO"), ln=True, align='C')
            pdf.ln(5); pdf.set_fill_color(240); pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0)
            pdf.cell(180, 10, tr(f" ITEM: {r['item']}"), border=1, ln=True, fill=True)
            pdf.cell(90, 10, tr(f" PATRIMÔNIO: {r['patrimonio']}"), border=1)
            pdf.cell(90, 10, tr(f" SÉRIE: {r['serial']}"), border=1, ln=True)
            
            # Fotos
            curr_y = pdf.get_y() + 5
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t1:
                t1.write(r["foto_fixa"].getvalue()); pdf.image(t1.name, x=15, y=curr_y, w=85)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t2:
                t2.write(r["foto_geral"].getvalue()); pdf.image(t2.name, x=105, y=curr_y, w=85)
            
        pdf.add_page(); pdf.set_y(100); pdf.line(60, pdf.get_y(), 150, pdf.get_y())
        pdf.cell(180, 10, tr(servidor.upper()), align='C')
        st.download_button("📥 Download PDF", data=pdf.output(dest='S'), file_name="Tombamento.pdf")

if st.sidebar.button("Reiniciar"): st.session_state.clear(); st.rerun()

if st.sidebar.button("Novo"):
    st.session_state.clear(); st.rerun()
