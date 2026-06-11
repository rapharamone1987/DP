import streamlit as st
from groq import Groq
import pdfplumber
from fpdf import FPDF
from datetime import datetime
from zoneinfo import ZoneInfo
import json, time, re

st.set_page_config(page_title="Recebimento Técnico RS", layout="centered")

# =========================
# ESTADO SEGURO
# =========================
if "items" not in st.session_state or not isinstance(st.session_state.items, list):
    st.session_state.items = []

if "cab" not in st.session_state:
    st.session_state.cab = {"fornecedor":"","edital":"","objeto":""}

if "ok" not in st.session_state:
    st.session_state.ok = {}

if "obs" not in st.session_state:
    st.session_state.obs = {}

# =========================
# IA
# =========================
key = st.secrets.get("GROQ_API_KEY","")
client = Groq(api_key=key) if key else None

def limpar_json(txt):
    try:
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        return json.loads(m.group(0) if m else txt)
    except:
        return None

def extrair(pdf, tipo):
    texto = ""
    with pdfplumber.open(pdf) as p:
        for pg in p.pages[:4]:
            texto += (pg.extract_text() or "") + "\n"

    if not client or not texto.strip():
        return None

    prompt = f"""
Analise para recebimento de {tipo}.
Retorne apenas JSON:
{{"fornecedor":"","edital":"","objeto":"","checklist":["item"]}}
"""

    try:
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt+texto}],
            temperature=0.1
        )
        return limpar_json(r.choices[0].message.content)
    except:
        return None

# =========================
# PDF
# =========================
def tr(t): return str(t).encode("latin-1","replace").decode("latin-1")

class PDF(FPDF):
    def __init__(self, ok, data):
        super().__init__()
        self.ok_all = ok
        self.data = data

    def faixa(self,y):
        self.set_fill_color(99,157,49); self.rect(0,y,70,6,'F')
        self.set_fill_color(227,6,19); self.rect(70,y,70,6,'F')
        self.set_fill_color(255,194,14); self.rect(140,y,70,6,'F')

    def header(self):
        self.faixa(0)
        self.set_y(10)

        if self.page_no()==1:
            self.set_font("Arial","",11)
            self.cell(0,6,tr("SECRETARIA DA AGRICULTURA, PECUÁRIA, PRODUÇÃO SUSTENTÁVEL E IRRIGAÇÃO"),0,1,"C")

            self.ln(4)

            self.set_font("Arial","B",12)
            titulo = "RELATÓRIO DE RECEBIMENTO TÉCNICO" if self.ok_all else "RELATÓRIO DE DESCONFORMIDADE TÉCNICA"
            self.cell(0,7,tr(titulo),0,1,"C")

            self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Arial","I",7)
        self.cell(0,4,tr(f"Página {self.page_no()} | {self.data}"),0,0,"C")

        self.set_y(-6)
        self.faixa(291)

def draw_check(pdf,x,y,status):
    cor = (99,157,49) if status else (227,6,19)
    pdf.set_fill_color(*cor)
    pdf.ellipse(x,y,5,5,"F")

# =========================
# INTERFACE
# =========================
st.title("📋 Checklist Recebimento Técnico")

# =========================
# ETAPA INICIAL
# =========================
if not st.session_state.items:

    tipo = st.radio("Natureza",["Consumo","Permanente"],horizontal=True)
    file = st.file_uploader("PDF", type=["pdf"])

    col1, col2 = st.columns(2)

    if col1.button("Analisar") and file:
        r = extrair(file, tipo)
        if r:
            st.session_state.cab = r
            st.session_state.items = [
                {"id": time.time()+i, "txt": t}
                for i,t in enumerate(r.get("checklist",[]))
            ]
            st.rerun()
        else:
            st.error("Falha ao analisar PDF")

    if col2.button("Manual"):
        st.session_state.items = [{"id":time.time(),"txt":"Novo requisito"}]
        st.rerun()

# =========================
# FORMULÁRIO
# =========================
else:

    c1,c2 = st.columns(2)

    st.session_state.cab["fornecedor"] = c1.text_input("Fornecedor",st.session_state.cab["fornecedor"])
    st.session_state.cab["edital"] = c2.text_input("Edital",st.session_state.cab["edital"])
    st.session_state.cab["objeto"] = st.text_area("Objeto",st.session_state.cab["objeto"])

    nf = c1.text_input("NF")
    qtd = c2.text_input("Qtd")
    unidade = c1.text_input("Unidade")

    todos_ok = True

    # LOOP SEGURO
    for i, it in enumerate(list(st.session_state.items)):

        uid = it["id"]

        col1, col2, col3 = st.columns([1,6,1])

        st.session_state.ok[uid] = col1.checkbox(
            "OK",
            value=st.session_state.ok.get(uid, False),
            key=f"ok{uid}"
        )

        if not st.session_state.ok.get(uid, False):
            todos_ok = False

        novo_txt = col2.text_input("", it["txt"], key=f"txt{uid}")
        st.session_state.items[i]["txt"] = novo_txt

        if col3.button("X", key=f"del{uid}"):
            st.session_state.items = [
                item for item in st.session_state.items if item["id"] != uid
            ]
            st.session_state.ok.pop(uid, None)
            st.session_state.obs.pop(uid, None)
            st.rerun()

        st.session_state.obs[uid] = st.text_area(
            "Observação",
            st.session_state.obs.get(uid,""),
            key=f"obs{uid}",
            height=70
        )

    if st.button("Adicionar requisito"):
        st.session_state.items.append({"id":time.time(),"txt":"Novo requisito"})
        st.rerun()

    obs_geral = st.text_area("Observações gerais")
    servidor = st.text_input("Servidor")

    # =========================
    # GERAÇÃO PDF
    # =========================
    if st.button("Gerar PDF"):

        data = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")

        pdf = PDF(todos_ok, data)
        pdf.set_margins(15,12,15)
        pdf.add_page()

        cab = st.session_state.cab

        pdf.set_fill_color(99,157,49)
        pdf.set_text_color(255)
        pdf.set_font("Arial","B",10)
        pdf.multi_cell(0,7,tr(f"OBJETO: {cab['objeto'].upper()}"),1,fill=True)

        pdf.set_text_color(0)

        campos = [
            ("FORNECEDOR",cab["fornecedor"]),
            ("EDITAL",cab["edital"]),
            ("NF",nf),
            ("QTD",qtd),
            ("UNIDADE",unidade),
            ("DATA/HORA",data),
        ]

        for k,v in campos:
            if v:
                pdf.set_font("Arial","B",9)
                pdf.cell(45,6,tr(k+": "),0,0)
                pdf.set_font("Arial","",9)
                pdf.multi_cell(0,6,tr(v),"B")

        pdf.ln(3)

        pdf.set_font("Arial","B",9)
        pdf.set_fill_color(220,220,220)
        pdf.cell(0,6,"REQUISITOS CONFERIDOS",1,1,"C",True)
        pdf.ln(3)

        ok_count=0
        nok=0

        for i,it in enumerate(st.session_state.items,1):

            uid = it["id"]
            status = st.session_state.ok.get(uid,False)

            if status: ok_count+=1
            else: nok+=1

            draw_check(pdf,16,pdf.get_y()+1,status)

            pdf.set_x(24)
            pdf.set_font("Arial","B",9.5)
            pdf.multi_cell(170,5.5,tr(f"{i}. {it['txt']}"))

            pdf.set_x(24)
            pdf.set_font("Arial","",8.5)
            pdf.multi_cell(170,4.5,tr("Conforme" if status else "Não conforme"))

            if st.session_state.obs.get(uid):
                pdf.set_x(24)
                pdf.set_font("Arial","I",8.5)
                pdf.multi_cell(170,4.5,tr(st.session_state.obs[uid]))

            pdf.set_draw_color(220)
            pdf.line(15,pdf.get_y(),195,pdf.get_y())
            pdf.ln(3)

        pdf.set_font("Arial","",9)
        pdf.multi_cell(0,5.5,tr(
            f"Total de itens: {len(st.session_state.items)}\n"
            f"Conformes: {ok_count}\n"
            f"Não conformes: {nok}"
        ),1)

        pdf.ln(3)

        cor = (235,245,235) if todos_ok else (255,230,230)
        pdf.set_fill_color(*cor)

        msg = "ATESTO O RECEBIMENTO POR CONFORMIDADE TÉCNICA." if todos_ok else "RELATÓRIO DE DESCONFORMIDADE TÉCNICA."

        pdf.set_font("Arial","B",9)
        pdf.multi_cell(0,6,tr(msg),1,"C",True)

        if obs_geral:
            pdf.ln(3)
            pdf.multi_cell(0,5,tr(obs_geral),1)

        pdf.ln(8)
        pdf.set_font("Arial","B",11)
        pdf.cell(0,6,tr(servidor.upper()),0,1,"C")

        pdf.set_font("Arial","",9)
        pdf.cell(0,5,"Responsável pelo Recebimento",0,1,"C")

        st.download_button("📥 Baixar PDF", pdf.output(dest="S").encode("latin-1"), "relatorio.pdf")

if st.sidebar.button("Reset"):
    st.session_state.clear()
    st.rerun()

if st.sidebar.button("Reset"):
    st.session_state.clear()
    st.rerun()
