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

# CONFIGURAÇÃO DA IA
key = st.secrets.get("GROQ_API_KEY", "")
client = Groq(api_key=key) if key else None

# ==========================================
# 2. FUNÇÕES DE APOIO
# ==========================================
def tr(texto):
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def extrair_dados_ia(pdf_file):
    texto_extraido = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages[:6]:
            texto_extraido += (pagina.extract_text() or "") + "\n"
    
    prompt = f"""Analise este texto e extraia o Número do Patrimônio e a Descrição Completa (Marca, Modelo, Chassi).
    Retorne APENAS um JSON no formato:
    [ {{"PATRIMONIO": "valor", "DESCRICAO": "texto completo"}} ]
    Texto: {texto_extraido}"""
    
    res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.1)
    match = re.search(r'\[.*\]', res.choices[0].message.content, re.DOTALL)
    return pd.DataFrame(json.loads(match.group(0))) if match else pd.DataFrame()

def salvar_imagem_temp(foto_st):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    temp.write(foto_st.getvalue())
    temp.close() 
    return temp.name

# ==========================================
# 3. CLASSE PDF (ESTILO RS OFICIAL)
# ==========================================
class RelatorioRS(FPDF):
    def faixa(self, y):
        self.set_fill_color(99, 157, 49); self.rect(0, y, 70, 6, 'F')
        self.set_fill_color(227, 6, 19); self.rect(70, y, 70, 6, 'F')
        self.set_fill_color(255, 194, 14); self.rect(140, y, 70, 6, 'F')
    def header(self):
        self.faixa(0)
        if self.page_no() == 1:
            self.set_y(10); self.set_font("Arial", 'B', 10); self.set_text_color(0)
            self.cell(0, 6, tr("SECRETARIA DA AGRICULTURA, PECUÁRIA, PRODUÇÃO SUSTENTÁVEL E IRRIGAÇÃO"), 0, 1, 'C')
            self.set_font("Arial", 'B', 14)
            self.cell(0, 10, tr("RELATÓRIO DE TOMBAMENTO PATRIMONIAL"), 0, 1, 'C')
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
        # VOLTOU A DESCRIÇÃO MANUAL
        desc_man = st.text_input("Descrição Padrão para os itens:")
        patr_man = st.text_area("Lista de Patrimônios (um por linha):")
        if st.button("Criar Lista Manual"):
            if desc_man and patr_man:
                linhas = [l.strip() for l in patr_man.split('\n') if l.strip()]
                st.session_state.df_bens = pd.DataFrame({"PATRIMONIO": linhas, "DESCRICAO": [desc_man]*len(linhas)})
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
                        c1, c2 = st.columns(2)
                        
                        # FOTO 1
                        with c1:
                            if f"f1_{p}" not in st.session_state:
                                if st.button("📷 Foto Plaqueta", key=f"b1_{p}"): st.session_state.camera_ativa = f"f1_{p}"; st.rerun()
                                if st.session_state.camera_ativa == f"f1_{p}":
                                    f = st.camera_input("Plaqueta", key=f"cam1_{p}")
                                    if f: st.session_state[f"f1_{p}"] = f; st.session_state.camera_ativa = None; st.rerun()
                            else:
                                st.image(st.session_state[f"f1_{p}"], width=150)
                                if st.button("🗑️ Apagar Foto", key=f"d1_{p}"): del st.session_state[f"f1_{p}"]; st.rerun()
                        
                        # FOTO 2
                        with c2:
                            if f"f2_{p}" not in st.session_state:
                                if st.button("📷 Foto Geral", key=f"b2_{p}"): st.session_state.camera_ativa = f"f2_{p}"; st.rerun()
                                if st.session_state.camera_ativa == f"f2_{p}":
                                    f = st.camera_input("Bem Inteiro", key=f"cam2_{p}")
                                    if f: st.session_state[f"f2_{p}"] = f; st.session_state.camera_ativa = None; st.rerun()
                            else:
                                st.image(st.session_state[f"f2_{p}"], width=150)
                                if st.button("🗑️ Apagar Foto ", key=f"d2_{p}"): del st.session_state[f"f2_{p}"]; st.rerun()

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

                pdf.set_fill_color(99, 157, 49); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 10)
                pdf.multi_cell(0, 8, tr(f" ITEM: {dados['desc'].upper()}"), 1, 'L', fill=True)
                pdf.set_text_color(0); pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(240)
                pdf.cell(90, 8, tr(f" PATRIMÔNIO: {p}"), border=1, fill=True)
                pdf.cell(90, 8, tr(f" SÉRIE/CHASSI: {dados['serial']}"), border=1, ln=True, fill=True)
                pdf.cell(0, 8, tr(f" UNIDADE DESTINO: {unidade.upper()}"), border=1, ln=True)
                
                pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.set_text_color(99, 157, 49)
                pdf.cell(90, 6, tr("EVIDÊNCIA DA PLAQUETA"), 0, 0, 'C'); pdf.cell(90, 6, tr("VISTA GERAL DO BEM"), 0, 1, 'C')
                
                p1 = salvar_imagem_temp(dados["img1"]); p2 = salvar_imagem_temp(dados["img2"])
                y_f = pdf.get_y()
                pdf.image(p1, x=25, y=y_f, w=70, h=52); os.unlink(p1)
                pdf.image(p2, x=115, y=y_f, w=70, h=52); os.unlink(p2)
                
                pdf.set_y(y_f + 54); pdf.set_font("Arial", 'I', 8); pdf.set_text_color(0)
                pdf.multi_cell(0, 5, tr("ATESTO O RECEBIMENTO DEFINITIVO do bem acima descrito por conformidade física."), 0, 'C')
                
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
