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
import re
from PIL import Image

# ==========================================
# 1. INICIALIZAÇÃO SEGURA DO ESTADO
# ==========================================
if "df_bens" not in st.session_state: st.session_state.df_bens = pd.DataFrame()
if "registros" not in st.session_state: st.session_state.registros = {}
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None
if "finalizado" not in st.session_state: st.session_state.finalizado = False
if "desc_lote" not in st.session_state: st.session_state.desc_lote = ""

# CONFIGURAÇÃO DA IA
key = st.secrets.get("GROQ_API_KEY", "")
client = Groq(api_key=key) if key else None

# ==========================================
# 2. FUNÇÕES DE APOIO
# ==========================================
def tr(texto):
    """Trata acentuação para PDF Latin-1"""
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def extrair_dados_ia(pdf_file):
    texto_extraido = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages[:6]:
            texto_extraido += (pagina.extract_text() or "") + "\n"
    
    prompt = f"""Analise este texto e extraia o Número do Patrimônio e a Descrição Completa.
    Retorne APENAS um JSON no formato:
    [ {{"PATRIMONIO": "valor", "DESCRICAO": "texto completo"}} ]
    Texto: {texto_extraido}"""
    
    res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.1)
    match = re.search(r'\[.*\]', res.choices[0].message.content, re.DOTALL)
    return pd.DataFrame(json.loads(match.group(0))) if match else pd.DataFrame()

def processar_imagem_pdf(st_image):
    if st_image is None: return None
    temp_path = os.path.join(tempfile.gettempdir(), f"tomb_{time.time()}_{os.urandom(4).hex()}.jpg")
    img = Image.open(st_image)
    if img.mode != 'RGB': img = img.convert('RGB')
    img.save(temp_path, "JPEG", quality=70)
    return temp_path

# ==========================================
# 3. CLASSE PDF (ESTILO RS OFICIAL)
# ==========================================
class RelatorioRS(FPDF):
    def faixa(self, y):
        self.set_fill_color(99, 157, 49); self.rect(0, y, 70, 6, 'F') # Verde
        self.set_fill_color(227, 6, 19); self.rect(70, y, 70, 6, 'F') # Vermelho
        self.set_fill_color(255, 194, 14); self.rect(140, y, 70, 6, 'F') # Amarelo

    def header(self):
        self.faixa(0)
        if self.page_no() == 1:
            self.set_y(10); self.set_font("Arial", 'B', 10); self.set_text_color(0)
            self.cell(0, 6, tr("SECRETARIA DA AGRICULTURA, PECUÁRIA, PRODUÇÃO SUSTENTÁVEL E IRRIGAÇÃO"), 0, 1, 'C')
            self.set_font("Arial", 'B', 14)
            self.cell(0, 10, tr("RELATÓRIO DE TOMBAMENTO PATRIMONIAL"), 0, 1, 'C')
        else:
            self.set_y(10)

    def footer(self):
        self.set_y(-10); self.faixa(291)
        self.set_y(-18); self.set_font("Arial", 'I', 7); self.set_text_color(100)
        self.cell(0, 10, tr(f"Página {self.page_no()}"), 0, 0, 'C')

# ==========================================
# 4. INTERFACE STREAMLIT
# ==========================================
st.set_page_config(page_title="Tombamento RS", layout="centered")
st.title("🛡️ Tombamento e Busca Versátil")

# --- FASE 1: CARGA ---
if st.session_state.df_bens.empty:
    tab1, tab2, tab3 = st.tabs(["📄 Extrair PDF", "📊 Colar Excel", "🖊️ Manual"])
    
    with tab1:
        file = st.file_uploader("Suba o PDF", type="pdf")
        if file and client and st.button("Analisar PDF"):
            with st.spinner("IA extraindo dados..."):
                st.session_state.df_bens = extrair_dados_ia(file); st.rerun()
    with tab2:
        txt_excel = st.text_area("Cole as colunas (Patrimônio e Descrição):")
        if st.button("Carregar Dados Excel"):
            try:
                st.session_state.df_bens = pd.read_csv(io.StringIO(txt_excel), sep=None, engine='python', header=None)
                st.session_state.df_bens.columns = ["PATRIMONIO", "DESCRICAO"]
                st.rerun()
            except: st.error("Erro no formato.")
    with tab3:
        st.session_state.desc_lote = st.text_input("Descrição Padrão para os itens:")
        patr_man = st.text_area("Lista de Patrimônios (um por linha):")
        if st.button("Criar Lista Manual"):
            if st.session_state.desc_lote and patr_man:
                linhas = [l.strip() for l in patr_man.split('\n') if l.strip()]
                st.session_state.df_bens = pd.DataFrame({"PATRIMONIO": linhas, "DESCRICAO": [st.session_state.desc_lote]*len(linhas)})
                st.rerun()

# --- FASE 2: OPERAÇÃO ---
elif not st.session_state.finalizado:
    st.write(f"📊 **Progresso:** {len(st.session_state.registros)} de {len(st.session_state.df_bens)} itens")
    
    termo = st.text_input("🔍 BUSCAR (PATRIMÔNIO, CHASSI OU MODELO):").strip().upper()
    
    if termo:
        mask = (st.session_state.df_bens["PATRIMONIO"].astype(str).str.contains(termo, case=False)) | \
               (st.session_state.df_bens["DESCRICAO"].astype(str).str.contains(termo, case=False))
        resultados = st.session_state.df_bens[mask]

        if not resultados.empty:
            for _, row in resultados.iterrows():
                p = str(row["PATRIMONIO"])
                with st.container(border=True):
                    st.write(f"**Patrimônio:** {p}")
                    st.write(f"**Descrição:** {row['DESCRICAO']}")
                    
                    if p in st.session_state.registros:
                        st.success("✅ Item já registrado.")
                        if st.button(f"🗑️ Excluir Registro {p}", key=f"del_reg_{p}"):
                            del st.session_state.registros[p]; st.rerun()
                    else:
                        serial = st.text_input("Série/Chassi real:", key=f"s_{p}")
                        
                        # --- SEÇÃO DE MÍDIA (CÂMERA OU GALERIA) ---
                        c1, c2 = st.columns(2)
                        
                        # FOTO 1: PLAQUETA
                        with c1:
                            st.write("**Evidência da Plaqueta**")
                            if f"f1_{p}" not in st.session_state:
                                t1_cam, t1_gal = st.tabs(["📸 Câmera", "📁 Galeria"])
                                with t1_cam:
                                    if st.session_state.camera_ativa == f"f1_{p}":
                                        f = st.camera_input("Foto", key=f"cam1_{p}")
                                        if f: st.session_state[f"f1_{p}"] = f; st.session_state.camera_ativa = None; st.rerun()
                                    elif st.button("Ligar Câmera", key=f"btn1_{p}"): st.session_state.camera_ativa = f"f1_{p}"; st.rerun()
                                with t1_gal:
                                    up1 = st.file_uploader("Escolher foto", type=['jpg','png','jpeg'], key=f"up1_{p}")
                                    if up1: st.session_state[f"f1_{p}"] = up1; st.rerun()
                            else:
                                st.image(st.session_state[f"f1_{p}"], width=150)
                                if st.button("🗑️ Apagar Foto 1", key=f"del1_{p}"): del st.session_state[f"f1_{p}"]; st.rerun()
                        
                        # FOTO 2: BEM GERAL
                        with c2:
                            st.write("**Vista Geral do Bem**")
                            if f"f2_{p}" not in st.session_state:
                                t2_cam, t2_gal = st.tabs(["📸 Câmera ", "📁 Galeria "])
                                with t2_cam:
                                    if st.session_state.camera_ativa == f"f2_{p}":
                                        f = st.camera_input("Foto ", key=f"cam2_{p}")
                                        if f: st.session_state[f"f2_{p}"] = f; st.session_state.camera_ativa = None; st.rerun()
                                    elif st.button("Ligar Câmera ", key=f"btn2_{p}"): st.session_state.camera_ativa = f"f2_{p}"; st.rerun()
                                with t2_gal:
                                    up2 = st.file_uploader("Escolher foto ", type=['jpg','png','jpeg'], key=f"up2_{p}")
                                    if up2: st.session_state[f"f2_{p}"] = up2; st.rerun()
                            else:
                                st.image(st.session_state[f"f2_{p}"], width=150)
                                if st.button("🗑️ Apagar Foto 2", key=f"del2_{p}"): del st.session_state[f"f2_{p}"]; st.rerun()

                        if st.button(f"💾 SALVAR ITEM {p}", key=f"sv_{p}"):
                            if f"f2_{p}" in st.session_state:
                                st.session_state.registros[p] = {"desc": row["DESCRICAO"], "serial": serial, "img1": st.session_state[f"f1_{p}"], "img2": st.session_state[f"f2_{p}"]}
                                st.rerun()
        else: st.error("Não encontrado.")

    st.divider()
    if st.button("🏁 Finalizar e Gerar PDF"): st.session_state.finalizado = True; st.rerun()

# --- FASE 3: PDF ---
elif st.session_state.finalizado:
    servidor = st.text_input("Responsável:")
    unidade = st.text_input("Unidade de Destino:")
    obs = st.text_area("Observações:")

    if st.button("🚀 BAIXAR TERMO"):
        try:
            pdf = RelatorioRS(); pdf.alias_nb_pages(); pdf.set_margins(15, 10, 15)
            lista = list(st.session_state.registros.items())
            for i, (p, dados) in enumerate(lista):
                if i % 2 == 0: pdf.add_page()
                else: pdf.ln(5); pdf.set_draw_color(200); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(5)

                # Cabeçalho do Item com Borda
                pdf.set_fill_color(99, 157, 49); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 10)
                pdf.multi_cell(0, 8, tr(f" ITEM: {dados['desc'].upper()}"), 1, 'L', fill=True)
                
                pdf.set_text_color(0); pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(240)
                pdf.cell(90, 8, tr(f" PATRIMÔNIO: {p}"), border=1, fill=True)
                pdf.cell(90, 8, tr(f" SÉRIE/CHASSI: {dados['serial']}"), border=1, ln=True, fill=True)
                pdf.cell(0, 8, tr(f" UNIDADE DESTINO: {unidade.upper()}"), border=1, ln=True)
                
                pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.set_text_color(99, 157, 49)
                pdf.cell(90, 6, tr("EVIDÊNCIA DA PLAQUETA"), 0, 0, 'C'); pdf.cell(90, 6, tr("VISTA GERAL DO BEM"), 0, 1, 'C')
                
                p1 = processar_imagem_pdf(dados["img1"]); p2 = processar_imagem_pdf(dados["img2"])
                y_f = pdf.get_y()
                if p1: pdf.image(p1, x=25, y=y_f, w=70, h=52); os.unlink(p1)
                if p2: pdf.image(p2, x=115, y=y_f, w=70, h=52); os.unlink(p2)
                
                pdf.set_y(y_f + 54); pdf.set_font("Arial", 'I', 8); pdf.set_text_color(0)
                pdf.multi_cell(0, 5, tr("ATESTO O RECEBIMENTO DEFINITIVO do bem acima descrito por conformidade física nesta data."), 0, 'C')
                
                if i == len(lista) - 1:
                    if obs: 
                        if pdf.get_y() > 220: pdf.add_page()
                        pdf.ln(5); pdf.set_font("Arial", 'B', 9); pdf.cell(0, 8, tr("OBSERVAÇÕES:"), 0, 1); pdf.multi_cell(0, 5, tr(obs), 1)
                    if pdf.get_y() > 240: pdf.add_page()
                    pdf.ln(10); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, tr(servidor.upper()), 0, 1, 'C')
                    pdf.set_font("Arial", '', 9); pdf.cell(0, 5, tr("Responsável pelo Tombamento"), 0, 1, 'C')

            st.download_button("📥 Baixar PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="Termo.pdf")
        except Exception as e: st.error(f"Erro: {e}")

if st.sidebar.button("Novo Trabalho"): st.session_state.clear(); st.rerun()
