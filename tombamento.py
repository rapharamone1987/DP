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

# --- 2. FUNÇÕES DE APOIO E TRATAMENTO ---
def tr(texto):
    """Trata acentuação para o padrão PDF Latin-1"""
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

# --- 3. CLASSE PDF PROFISSIONAL (VERDE #009A44) ---
class RelatorioTombamento(FPDF):
    def header(self):
        # Faixa verde no topo
        self.set_fill_color(0, 154, 68) # Verde #009A44
        self.rect(0, 0, 210, 12, 'F')
        
        self.set_y(15)
        self.set_font("Arial", 'B', 14)
        self.set_text_color(0, 154, 68)
        self.cell(180, 10, tr("TERMO DE TOMBAMENTO E RESPONSABILIDADE"), ln=True, align='C')
        self.set_text_color(0, 0, 0)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        # Faixa verde no rodapé
        self.set_fill_color(0, 154, 68)
        self.rect(0, 285, 210, 12, 'F')
        
        self.set_font("Arial", 'I', 8)
        self.set_text_color(100)
        dt = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.cell(0, 10, tr(f"Relatório Gerado em {dt} - Página {self.page_no()}/{{nb}}"), 0, 0, 'C')

# --- 4. INTERFACE E ESTADO ---
st.set_page_config(page_title="Gestão de Patrimônio", layout="centered")

if "df_patrimonios" not in st.session_state: st.session_state.df_patrimonios = pd.DataFrame()
if "registros" not in st.session_state: st.session_state.registros = {}
if "desc_unica" not in st.session_state: st.session_state.desc_unica = ""
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

st.markdown("""<style>
    .titulo { color: #009A44; font-weight: bold; font-size: 24px; text-align: center; }
    .barra { background-color: #009A44; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; }
</style>""", unsafe_allow_html=True)

st.title("🛡️ Tombamento Digital")

# --- 5. FASE 1: CARGA ---
if st.session_state.df_patrimonios.empty:
    st.subheader("Configurar Novo Lote")
    st.session_state.desc_unica = st.text_input("Descrição do Bem (Única para o lote):", placeholder="Ex: Microcomputador Dell Optiplex")
    
    st.write("---")
    t1, t2 = st.tabs(["📄 Extrair do PDF", "📊 Colar Lista"])
    
    with t1:
        pdf_up = st.file_uploader("Upload da Relação", type="pdf")
        if pdf_up and client and st.button("Analisar PDF"):
            with st.spinner("Extraindo números de patrimônio..."):
                st.session_state.df_patrimonios = extrair_patrimonios_ia(pdf_up)
                st.rerun()
    with t2:
        txt_nums = st.text_area("Cole os números de patrimônio:")
        if st.button("Carregar Patrimônios"):
            linhas = [l.strip() for l in txt_nums.split('\n') if l.strip()]
            st.session_state.df_patrimonios = pd.DataFrame({"PATRIMONIO": linhas})
            st.rerun()

# --- 6. FASE 2: REVISÃO ---
elif not st.session_state.get("iniciado"):
    st.subheader("Revisar Números")
    st.info(f"**Item:** {st.session_state.desc_unica}")
    st.session_state.df_patrimonios = st.data_editor(st.session_state.df_patrimonios, num_rows="dynamic", use_container_width=True)
    if st.button("🚀 Iniciar Tombamento"):
        st.session_state.iniciado = True; st.rerun()

# --- 7. FASE 3: OPERAÇÃO ---
elif st.session_state.get("iniciado") and not st.session_state.get("finalizado"):
    st.markdown(f'<div class="barra">{st.session_state.desc_unica.upper()}</div>', unsafe_allow_html=True)
    
    st.write(f"📊 **Progresso:** {len(st.session_state.registros)} de {len(st.session_state.df_patrimonios)}")
    busca = st.text_input("SCANEAR PLAQUETA:", key="input_busca").strip()
    
    if busca:
        if busca in st.session_state.df_patrimonios["PATRIMONIO"].astype(str).values:
            st.success(f"✅ PATRIMÔNIO ENCONTRADO: {busca}")
            serial = st.text_input("Nº de Série (Fabricante):", key=f"s_{busca}")
            
            c1, c2 = st.columns(2)
            with c1:
                if f"f1_{busca}" not in st.session_state:
                    if st.button("📷 Foto Etiqueta", key=f"b1_{busca}"): st.session_state.camera_ativa = "f1"; st.rerun()
                    if st.session_state.camera_ativa == "f1":
                        f1 = st.camera_input("Plaqueta")
                        if f1: st.session_state[f"f1_{busca}"] = f1; st.session_state.camera_ativa = None; st.rerun()
                else: st.image(st.session_state[f"f1_{busca}"], width=120)

            with c2:
                if f"f2_{busca}" not in st.session_state:
                    if st.button("📷 Foto do Bem", key=f"b2_{busca}"): st.session_state.camera_ativa = "f2"; st.rerun()
                    if st.session_state.camera_ativa == "f2":
                        f2 = st.camera_input("Geral")
                        if f2: st.session_state[f"f2_{busca}"] = f2; st.session_state.camera_ativa = None; st.rerun()
                else: st.image(st.session_state[f"f2_{busca}"], width=120)

            if st.button("💾 SALVAR E PRÓXIMO", key=f"save_{busca}"):
                if f"f2_{busca}" in st.session_state:
                    st.session_state.registros[busca] = {"placa": busca, "serial": serial, "f1": st.session_state[f"f1_{busca}"], "f2": st.session_state[f"f2_{busca}"]}
                    st.rerun()
        else: st.error("❌ Número não está na lista.")

    st.divider()
    if st.button("🏁 Finalizar e Gerar Termo"):
        st.session_state.finalizado = True; st.rerun()

# --- 8. PDF FINAL (LAYOUT RICO) ---
elif st.session_state.get("finalizado"):
    servidor = st.text_input("Servidor Responsável:")
    setor = st.text_input("Setor de Destino:")
    
    if st.button("🚀 BAIXAR TERMO OFICIAL"):
        try:
            pdf = RelatorioTombamento(); pdf.alias_nb_pages(); pdf.set_margins(15, 15, 15)
            for p, r in st.session_state.registros.items():
                pdf.add_page()
                
                # Box de Identificação do Item (Verde)
                pdf.set_fill_color(0, 154, 68)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(180, 10, tr(f" BEM: {st.session_state.desc_unica.upper()}"), border=0, ln=True, fill=True)
                
                # Dados Técnicos (Tabela)
                pdf.set_text_color(0, 0, 0)
                pdf.set_fill_color(245, 245, 245)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(40, 8, tr(" PATRIMÔNIO:"), border=1, fill=True)
                pdf.set_font("Arial", '', 10); pdf.cell(50, 8, tr(f" {r['placa']}"), border=1)
                pdf.set_font("Arial", 'B', 10); pdf.cell(40, 8, tr(" SÉRIE:"), border=1, fill=True)
                pdf.set_font("Arial", '', 10); pdf.cell(50, 8, tr(f" {r['serial']}"), border=1, ln=True)
                
                pdf.set_font("Arial", 'B', 10); pdf.cell(40, 8, tr(" SETOR:"), border=1, fill=True)
                pdf.set_font("Arial", '', 10); pdf.cell(140, 8, tr(f" {setor.upper()}"), border=1, ln=True)
                
                pdf.ln(10)

                # Fotos com Moldura
                curr_y = pdf.get_y()
                path1 = salvar_imagem_temp(r["f1"])
                path2 = salvar_imagem_temp(r["f2"])
                
                # Imagem 1
                pdf.set_draw_color(200)
                pdf.rect(15, curr_y, 85, 65) # Moldura
                pdf.image(path1, x=17, y=curr_y+2, w=81, h=61)
                
                # Imagem 2
                pdf.rect(110, curr_y, 85, 65) # Moldura
                pdf.image(path2, x=112, y=curr_y+2, w=81, h=61)
                
                pdf.set_y(curr_y + 70)
                pdf.set_font("Arial", 'B', 8); pdf.set_text_color(100)
                pdf.cell(90, 5, tr("EVIDÊNCIA DA PLAQUETA"), 0, 0, 'C')
                pdf.cell(90, 5, tr("EVIDÊNCIA DO BEM"), 0, 1, 'C')
                
                # Atesto Individual
                pdf.ln(15)
                pdf.set_fill_color(240, 240, 240)
                pdf.set_font("Arial", 'I', 9); pdf.set_text_color(0)
                pdf.multi_cell(180, 8, tr("Atesto para fins de inventário e registro patrimonial que o bem acima foi devidamente identificado, etiquetado e conferido fisicamente nesta data."), border='T', align='C', fill=True)
                
                os.unlink(path1); os.unlink(path2)

            # Página de Assinatura Final
            pdf.add_page()
            pdf.set_y(120)
            pdf.set_draw_color(0); pdf.line(60, pdf.get_y(), 150, pdf.get_y())
            pdf.set_font("Arial", 'B', 12); pdf.cell(180, 10, tr(servidor.upper()), ln=True, align='C')
            pdf.set_font("Arial", '', 10); pdf.cell(180, 8, tr("Responsável pelo Tombamento"), ln=True, align='C')

            out = pdf.output(dest='S')
            if isinstance(out, str): out = out.encode('latin-1')
            st.download_button("📥 Baixar Termo Premium", data=out, file_name="Termo_Tombamento.pdf")
        except Exception as e: st.error(f"Erro no PDF: {e}")

if st.sidebar.button("Reiniciar"):
    st.session_state.clear(); st.rerun()
