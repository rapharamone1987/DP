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

def extrair_dados_ia(pdf_file):
    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto += pagina.extract_text() + "\n"
    
    # Prompt em JSON para evitar erro de colunas misturadas
    prompt = f"""Analise este texto de um documento de patrimônio. 
    Extraia o Número do Patrimônio e a Descrição do Item.
    Retorne APENAS um JSON no formato:
    [
      {{"PATRIMONIO": "valor", "ITEM": "descrição"}},
      {{"PATRIMONIO": "valor", "ITEM": "descrição"}}
    ]
    Ignore cabeçalhos e rodapés. Se o item não tiver número de patrimônio claro, ignore.
    Texto: {texto}"""
    
    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1 # Temperatura baixa para ser mais preciso
    )
    
    content = res.choices[0].message.content
    # Limpa a resposta da IA (remove markdown ```json)
    json_str = content.replace("```json", "").replace("```", "").strip()
    return pd.DataFrame(json.loads(json_str))

# --- 3. INTERFACE E ESTADO ---
st.set_page_config(page_title="Tombamento por Busca", layout="centered")

if "df_bens" not in st.session_state: st.session_state.df_bens = pd.DataFrame()
if "registros" not in st.session_state: st.session_state.registros = {}
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

st.markdown("""<style>
    .barra { background-color: #004d00; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; }
    .found-card { background-color: #e8f5e9; border: 2px solid #2e7d32; padding: 15px; border-radius: 10px; margin: 10px 0; }
    .stDataEditor { border: 1px solid #ddd; border-radius: 5px; }
</style>""", unsafe_allow_html=True)

st.title("🛡️ Sistema de Tombamento e Busca")

# --- 4. FASE 1: CARGA E EDIÇÃO ---
if st.session_state.df_bens.empty:
    st.subheader("1. Carregar Tabela de Bens")
    tab1, tab2 = st.tabs(["📄 Extrair do PDF (IA)", "📊 Colar do Excel/Planilha"])
    
    with tab1:
        pdf_up = st.file_uploader("Suba o arquivo do TR/Empenho", type="pdf")
        if pdf_up and client and st.button("🔍 Analisar PDF com IA"):
            with st.spinner("IA extraindo patrimônios..."):
                try:
                    df_extraido = extrair_dados_ia(pdf_up)
                    st.session_state.df_bens = df_extraido
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro na extração: {e}")
                
    with tab2:
        st.write("Copie as colunas 'Patrimônio' e 'Descrição' da sua planilha e cole abaixo:")
        txt_csv = st.text_area("Cole aqui (incluindo o cabeçalho):", height=150)
        if st.button("Carregar Dados do Excel"):
            try:
                # O sep=None faz o pandas adivinhar se é vírgula ou Tabulação (Excel)
                df_manual = pd.read_csv(io.StringIO(txt_csv), sep=None, engine='python')
                # Força os nomes das colunas
                df_manual.columns = ["PATRIMONIO", "ITEM"]
                st.session_state.df_bens = df_manual
                st.rerun()
            except:
                st.error("Erro no formato. Dica: Cole as colunas diretamente do Excel.")

# --- 5. FASE 2: REVISÃO (IMPORTANTE PARA LIMPAR DADOS) ---
elif not st.session_state.get("iniciado"):
    st.subheader("2. Conferir e Ajustar Lista")
    st.info("💡 Use a lixeira lateral para remover linhas de lixo. Você pode editar os números se a IA leu errado.")
    
    # Editor que permite editar qualquer célula e deletar linhas
    st.session_state.df_bens = st.data_editor(
        st.session_state.df_bens, 
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "PATRIMONIO": st.column_config.TextColumn("Nº Patrimônio"),
            "ITEM": st.column_config.TextColumn("Descrição do Bem", width="large")
        }
    )
    
    if st.button("🚀 Iniciar Operação no Pátio"):
        # Garante que Patrimônio seja string e limpa espaços
        st.session_state.df_bens["PATRIMONIO"] = st.session_state.df_bens["PATRIMONIO"].astype(str).str.strip()
        st.session_state.iniciado = True
        st.rerun()

# --- 6. FASE 3: BUSCA E REGISTRO ---
elif st.session_state.get("iniciado") and not st.session_state.get("finalizado"):
    st.markdown('<div class="barra">MODO BUSCA ATIVO</div>', unsafe_allow_html=True)
    
    st.write(f"📊 **Progresso:** {len(st.session_state.registros)} de {len(st.session_state.df_bens)} registrados.")

    st.write("### 🔍 Scanear ou Digitar Plaqueta")
    # Limpa o campo de busca automaticamente usando session_state se necessário
    busca = st.text_input("FOQUE O SCANNER NESTE CAMPO:", key="input_busca").strip()
    
    if busca:
        # Busca exata
        match = st.session_state.df_bens[st.session_state.df_bens["PATRIMONIO"] == busca]
        
        if not match.empty:
            nome_item = match.iloc[0]["ITEM"]
            st.markdown(f"""<div class="found-card">
                <b>✅ ITEM LOCALIZADO:</b><br>{nome_item}<br>
                <b>Patrimônio:</b> {busca}
            </div>""", unsafe_allow_html=True)
            
            if busca in st.session_state.registros:
                st.warning("⚠️ Já registrado.")
            
            serial = st.text_input("Número de Série (Fabricante):", key=f"ser_{busca}")
            
            c1, c2 = st.columns(2)
            # FOTO 1
            with c1:
                if f"f1_{busca}" not in st.session_state:
                    if st.button("📷 Foto Etiqueta", key=f"btn1_{busca}"): st.session_state.camera_ativa = "f1"; st.rerun()
                    if st.session_state.camera_ativa == "f1":
                        f1 = st.camera_input("Fixação")
                        if f1: st.session_state[f"f1_{busca}"] = f1; st.session_state.camera_ativa = None; st.rerun()
                else: st.image(st.session_state[f"f1_{busca}"], width=120)

            # FOTO 2
            with c2:
                if f"f2_{busca}" not in st.session_state:
                    if st.button("📷 Foto do Bem", key=f"btn2_{busca}"): st.session_state.camera_ativa = "f2"; st.rerun()
                    if st.session_state.camera_ativa == "f2":
                        f2 = st.camera_input("Geral")
                        if f2: st.session_state[f"f2_{busca}"] = f2; st.session_state.camera_ativa = None; st.rerun()
                else: st.image(st.session_state[f"f2_{busca}"], width=120)

            if st.button("💾 SALVAR REGISTRO", key=f"save_{busca}"):
                if serial and f"f2_{busca}" in st.session_state:
                    st.session_state.registros[busca] = {
                        "item": nome_item, "patrimonio": busca, "serial": serial,
                        "f1": st.session_state[f"f1_{busca}"], "f2": st.session_state[f"f2_{busca}"]
                    }
                    st.success("Salvo!")
                    time.sleep(1)
                    st.rerun()
        else:
            st.error(f"❌ Placa {busca} não está na lista.")

    st.divider()
    if st.button("🏁 Finalizar e Baixar PDF"):
        st.session_state.finalizado = True; st.rerun()

# --- 7. FASE FINAL: PDF ---
elif st.session_state.get("finalizado"):
    servidor = st.text_input("Nome do Servidor:")
    if st.button("🚀 GERAR PDF"):
        pdf = FPDF(); pdf.set_margins(15, 15, 15)
        for p, r in st.session_state.registros.items():
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16); pdf.cell(180, 10, tr("TERMO DE TOMBAMENTO"), ln=True, align='C')
            pdf.set_fill_color(240); pdf.set_font("Arial", 'B', 11)
            pdf.cell(180, 10, tr(f" ITEM: {r['item']}"), border=1, ln=True, fill=True)
            pdf.cell(90, 10, tr(f" PATRIMÔNIO: {r['patrimonio']}"), border=1)
            pdf.cell(90, 10, tr(f" SÉRIE: {r['serial']}"), border=1, ln=True)
            
            curr_y = pdf.get_y() + 5
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t1:
                t1.write(r["f1"].getvalue()); pdf.image(t1.name, x=15, y=curr_y, w=85)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t2:
                t2.write(r["f2"].getvalue()); pdf.image(t2.name, x=105, y=curr_y, w=85)
            
        pdf_out = pdf.output(dest='S')
        if isinstance(pdf_out, str): pdf_out = pdf_out.encode('latin-1')
        st.download_button("📥 Baixar PDF", data=pdf_out, file_name="Tombamento.pdf")

if st.sidebar.button("Limpar Tudo"): st.session_state.clear(); st.rerun()
