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

# --- 1. CONFIGURAÇÃO DA IA ---
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
    """Extrai patrimônios e descrições em blocos para suportar listas longas"""
    todos_dados = []
    with pdfplumber.open(pdf_file) as pdf:
        for i in range(0, len(pdf.pages), 5):
            bloco_texto = ""
            for pagina in pdf.pages[i:i+5]:
                bloco_texto += (pagina.extract_text() or "") + "\n"
            
            if not bloco_texto.strip(): continue

            prompt = f"""Analise este texto de cadastro de bens. 
            Extraia o Número do Patrimônio e a Descrição Completa (incluindo Marca, Modelo e Chassi/Série se houver).
            Retorne APENAS um JSON no formato:
            [ {{"PATRIMONIO": "valor", "DESCRICAO": "texto completo"}} ]
            Texto: {bloco_texto[:8000]}"""

            try:
                res = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                match = re.search(r'\[.*\]', res.choices[0].message.content, re.DOTALL)
                if match:
                    todos_dados.extend(json.loads(match.group(0)))
                time.sleep(0.5)
            except: continue
    return pd.DataFrame(todos_dados)

def salvar_imagem_temp(foto_st):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    temp.write(foto_st.getvalue())
    temp.close() 
    return temp.name

# --- 3. CLASSE PDF (ESTILO RS) ---
class RelatorioTombamento(FPDF):
    def desenhar_faixa_tricolor(self, y_pos):
        h = 6
        self.set_fill_color(99, 157, 49); self.rect(0, y_pos, 70, h, 'F')
        self.set_fill_color(227, 6, 19); self.rect(70, y_pos, 70, h, 'F')
        self.set_fill_color(255, 194, 14); self.rect(140, y_pos, 70, h, 'F')
    def header(self):
        self.desenhar_faixa_tricolor(0)
        if self.page_no() == 1:
            self.set_y(10); self.set_font("Arial", 'B', 14); self.set_text_color(0)
            self.cell(0, 10, tr("RELATÓRIO DE TOMBAMENTO PATRIMONIAL"), 0, 1, 'C')
    def footer(self):
        self.set_y(-10); self.desenhar_faixa_tricolor(291)
        self.set_y(-18); self.set_font("Arial", 'I', 7); self.set_text_color(100)
        self.cell(0, 10, tr(f"Página {self.page_no()}"), 0, 0, 'C')

# --- 4. INTERFACE ---
st.set_page_config(page_title="Tombamento Versátil", layout="centered")

if "df_bens" not in st.session_state: st.session_state.df_bens = pd.DataFrame()
if "registros" not in st.session_state: st.session_state.registros = {}
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

st.title("🛡️ Tombamento e Busca por Chassi")

# --- 5. FASE 1: CARGA ---
if st.session_state.df_bens.empty:
    tab1, tab2 = st.tabs(["📄 Extrair PDF", "📊 Colar Tabela"])
    with tab1:
        file = st.file_uploader("Suba o PDF (Cadastro de Ativos)", type="pdf")
        if file and client and st.button("🔍 Analisar Documento"):
            with st.spinner("IA extraindo patrimônios e descrições..."):
                st.session_state.df_bens = extrair_dados_ia(file)
                st.rerun()
    with tab2:
        txt = st.text_area("Cole as colunas (Patrimônio e Descrição):")
        if st.button("Carregar Dados"):
            st.session_state.df_bens = pd.read_csv(io.StringIO(txt), sep=None, engine='python', header=None)
            st.session_state.df_bens.columns = ["PATRIMONIO", "DESCRICAO"]
            st.rerun()

# --- 6. FASE 2: OPERAÇÃO ---
elif not st.session_state.get("finalizado"):
    st.write(f"📊 **Progresso:** {len(st.session_state.registros)} de {len(st.session_state.df_bens)} itens")
    
    # BUSCA GLOBAL (Plaqueta, Chassi, Modelo...)
    termo_busca = st.text_input("🔍 BUSCAR (PATRIMÔNIO, CHASSI OU MODELO):", placeholder="Digite qualquer parte da informação...").strip().upper()
    
    if termo_busca:
        # Filtra o dataframe por qualquer coluna que contenha o termo
        mask = (st.session_state.df_bens["PATRIMONIO"].astype(str).str.contains(termo_busca, case=False)) | \
               (st.session_state.df_bens["DESCRICAO"].astype(str).str.contains(termo_busca, case=False))
        resultados = st.session_state.df_bens[mask]

        if not resultados.empty:
            for idx, row in resultados.iterrows():
                patr = str(row["PATRIMONIO"])
                with st.container(border=True):
                    st.write(f"**Patrimônio:** {patr}")
                    st.write(f"**Descrição:** {row['DESCRICAO']}")
                    
                    if patr in st.session_state.registros:
                        st.success("✅ Item já registrado.")
                        if st.button(f"Editar Registro {patr}", key=f"ed_{patr}"):
                            del st.session_state.registros[patr]; st.rerun()
                    else:
                        serial = st.text_input("Confirmar Número de Série/Chassi:", key=f"s_{patr}")
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            if f"f1_{patr}" not in st.session_state:
                                if st.button("📷 Foto Plaqueta", key=f"b1_{patr}"): st.session_state.camera_ativa = f"f1_{patr}"; st.rerun()
                                if st.session_state.camera_ativa == f"f1_{patr}":
                                    f = st.camera_input("Plaqueta", key=f"cam1_{patr}")
                                    if f: st.session_state[f"f1_{patr}"] = f; st.session_state.camera_ativa = None; st.rerun()
                            else: st.image(st.session_state[f"f1_{patr}"], width=150)
                        
                        with c2:
                            if f"f2_{patr}" not in st.session_state:
                                if st.button("📷 Foto Geral", key=f"b2_{patr}"): st.session_state.camera_ativa = f"f2_{patr}"; st.rerun()
                                if st.session_state.camera_ativa == f"f2_{patr}":
                                    f = st.camera_input("Bem Inteiro", key=f"cam2_{patr}")
                                    if f: st.session_state[f"f2_{patr}"] = f; st.session_state.camera_ativa = None; st.rerun()
                            else: st.image(st.session_state[f"f2_{patr}"], width=150)

                        if st.button(f"💾 SALVAR ITEM {patr}", key=f"sv_{patr}"):
                            if f"f2_{patr}" in st.session_state:
                                st.session_state.registros[patr] = {
                                    "desc": row["DESCRICAO"], "placa": patr, "serial": serial,
                                    "img1": st.session_state[f"f1_{patr}"], "img2": st.session_state[f"f2_{patr}"]
                                }
                                st.rerun()
        else:
            st.error("Nenhum item corresponde à busca.")

    st.divider()
    if st.button("🏁 Finalizar e Gerar PDF"): st.session_state.finalizado = True; st.rerun()

# --- 7. FASE FINAL: PDF ---
elif st.session_state.get("finalizado"):
    servidor = st.text_input("Responsável:")
    setor = st.text_input("Unidade de Destino:")
    if st.button("🚀 BAIXAR RELATÓRIO"):
        try:
            pdf = RelatorioTombamento(); pdf.alias_nb_pages(); pdf.set_margins(15, 10, 15)
            lista = list(st.session_state.registros.items())
            for i, (placa, dados) in enumerate(lista):
                if i % 2 == 0: pdf.add_page()
                else: pdf.ln(5); pdf.set_draw_color(200); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(5)

                pdf.set_fill_color(99, 157, 49); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 10)
                pdf.multi_cell(0, 8, tr(f" ITEM: {dados['desc'].upper()}"), 1, 'L', fill=True)
                pdf.set_text_color(0); pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(240)
                pdf.cell(90, 8, tr(f" PATRIMÔNIO: {placa}"), border=1, fill=True)
                pdf.cell(90, 8, tr(f" SÉRIE/CHASSI: {dados['serial']}"), border=1, ln=True, fill=True)
                pdf.cell(0, 8, tr(f" UNIDADE DESTINO: {setor.upper()}"), border=1, ln=True)
                
                pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.set_text_color(99, 157, 49)
                pdf.cell(90, 6, tr("EVIDÊNCIA DA PLAQUETA"), 0, 0, 'C'); pdf.cell(90, 6, tr("VISTA GERAL DO BEM"), 0, 1, 'C')
                
                p1 = salvar_imagem_temp(dados["img1"]); p2 = salvar_imagem_temp(dados["img2"])
                y_f = pdf.get_y()
                if p1: pdf.image(p1, x=25, y=y_f, w=70, h=52); os.unlink(p1)
                if p2: pdf.image(p2, x=115, y=y_f, w=70, h=52); os.unlink(p2)
                
                pdf.set_y(y_f + 54); pdf.set_font("Arial", 'I', 8); pdf.set_text_color(0)
                pdf.multi_cell(0, 5, tr("ATESTO O RECEBIMENTO DEFINITIVO do bem acima descrito por conformidade física nesta data."), align='C')
                
                if i == len(lista) - 1:
                    if pdf.get_y() > 240: pdf.add_page()
                    pdf.ln(10); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, tr(servidor.upper()), 0, 1, 'C')
                    pdf.set_font("Arial", '', 9); pdf.cell(0, 5, tr("Responsável pelo Tombamento"), 0, 1, 'C')
            st.download_button("📥 Salvar Relatório", data=pdf.output(dest='S').encode('latin-1'), file_name="Relatorio_Tombamento.pdf")
        except Exception as e: st.error(f"Erro: {e}")

if st.sidebar.button("Nova Inspeção"): st.session_state.clear(); st.rerun()
