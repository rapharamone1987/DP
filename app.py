import sys
import os
import streamlit as st
import pandas as pd
from groq import Groq

# ------------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA INTERFACE E AMBIENTE
# ------------------------------------------------------------------------------
st.set_page_config(page_title="Aegis Eleitoral PRO", layout="wide")

st.title("🛡️ Aegis Eleitoral — Inteligência de Guerrilha")
st.caption("Plataforma Avançada de Sala de Situação, Big Data Geopolítico e Controle Financeiro — Eleições 2026")

# --- VALIDAÇÃO DOS SECRETS ---
try:
    api_key = st.secrets["GROQ_API_KEY"]
except KeyError:
    st.error("⚠️ Chave de API do Groq (GROQ_API_KEY) não encontrada nos secrets do Streamlit Cloud.")
    st.stop()

# ------------------------------------------------------------------------------
# 2. BANCO DE DADOS ESTATÍSTICOS ANCORA (MUNICÍPIOS REFERÊNCIA)
# ------------------------------------------------------------------------------
DADOS_GEOPOLITICOS_RS = {
    "PORTO ALEGRE": {
        "regiao": "Metropolitana",
        "eleitorado_total": 1084000,
        "abstencao_media": "22.4%",
        "perfil_socioeconomico": "Capital do Estado. Predomínio do setor de serviços, funcionalismo público, comércio adensado e forte núcleo universitário. Alto IDH (0.805).",
        "comportamento_historico": "Eleitorado altamente fragmentado, crítico e polarizado. Divisão histórica acentuada entre periferias (voto de demanda estrutural) e bairros centrais (voto ideológico de opinião/redes).",
        "principais_dores": "Segurança nos eixos comerciais, revitalização do centro urbano, eficiência no transporte público e desburocratização tributária municipal."
    },
    "CAXIAS DO SUL": {
        "regiao": "Serra Gaúcha",
        "eleitorado_total": 348000,
        "abstencao_media": "18.1%",
        "perfil_socioeconomico": "Segundo maior polo econômico do estado. Forte DNA metal-mecânico, industrial, vitivinicultor e cooperativista. Baixo desemprego.",
        "comportamento_historico": "Eleitorado de perfil conservador, pragmático e focado em pautas econômicas de livre mercado, ordem pública e valorização do trabalho e da família.",
        "principais_dores": "Gargalos logísticos de escoamento (estradas federais), segurança nas zonas industriais e demandas por saúde suplementar."
    },
    "PASSO FUNDO": {
        "regiao": "Planalto Médio",
        "eleitorado_total": 152000,
        "abstencao_media": "16.5%",
        "perfil_socioeconomico": "Polo de saúde, educação superior e entroncamento logístico do agronegócio de alta precisão. Renda impulsionada pelas safras de grãos.",
        "comportamento_historico": "Voto tradicionalmente ligado a grandes lideranças locais (voto de liderança e representação regional). Forte influência do setor produtivo e sindicatos rurais.",
        "principais_dores": "Insegurança e roubo de defensivos em propriedades rurais, infraestrutura de rodovias estaduais secundárias e retenção de talentos técnicos."
    },
    "URUGUAIANA": {
        "regiao": "Fronteira Oeste",
        "eleitorado_total": 88000,
        "abstencao_media": "24.2%",
        "perfil_socioeconomico": "Maior porto seco da América Latina. Economia baseada na logística internacional do Mercosul, pecuária extensiva e grande lavoura arrozeira.",
        "comportamento_historico": "Eleitorado com alto índice de abstenção. Voto muito dependente de estruturas políticas consolidadas e forte apelo a demandas de segurança nacional e apoio governamental.",
        "principais_dores": "Falta de policiamento nas rotas de fronteira, burocracia aduaneira sufocante e isolamento político em relação à capital."
    }
}

DADOS_ESTADUAIS_GERAIS = {
    "regiao": "Todo o Rio Grande do Sul",
    "eleitorado_total": 8600000,
    "abstencao_media": "19.8%",
    "perfil_socioeconomico": "Estado com forte equilíbrio entre o PIB industrial (Serra/Metropolitana) e a força do Agronegócio (Norte/Fronteira/Sul). Elevado índice de politização e IDH médio alto.",
    "comportamento_historico": "Tendência histórica a eleições plebiscitárias e polarizadas. Forte tradição de voto regionalizado, onde deputados federais precisam consolidar bases em 'dobradinhas' com estaduais locais.",
    "principais_dores": "Dívida pública do Estado, infraestrutura logística e estradas, segurança pública rural e urbana, e incentivos fiscais para reter indústrias."
}

# ------------------------------------------------------------------------------
# 3. MOTOR DE INTELIGÊNCIA ARTIFICIAL MILITARIZADO (PHD CORE)
# ------------------------------------------------------------------------------
def inicializar_motor_campanha(api_key, dados_candidato):
    client = Groq(api_key=api_key)
    
    nome = dados_candidato.get('nome', 'Candidato')
    partido = dados_candidato.get('partido', 'Partido')
    idade = dados_candidato.get('idade', '45')
    nicho_livre = dados_candidato.get('nicho', 'Geral')
    biografia = dados_candidato.get('biografia', 'Sem histórico detalhado.')
    municipios_texto = ", ".join(dados_candidato.get('municipios', []))

    prompt_sistema = f"""
    Você é o Estrategista-Chefe, General de Sala de Crise e PhD em Ciência Política da campanha de {nome} ({partido}), disputando a eleição de Deputado Federal pelo Rio Grande do Sul.
    Idade: {idade} anos.
    
    [PRONTUÁRIO BIOGRÁFICO REAL DO CANDIDATO]
    {biografia}
    
    [MAPA GEOPOLÍTICO E PAUTA]
    - Territórios-Alvo selecionados: {municipios_texto}
    - Trincheira Temática Central: {nicho_livre}
    
    [DIRETRIZES DO COMITÊ CENTRAL - IMPRESCINDÍVEL]
    1. POSTURA TÁTICA: Suas recomendações devem ser arrojadas, disruptivas e baseadas em estratégias reais de guerra política de desgaste. Esqueça cartilhas corporativas ou conselhos confortáveis.
    2. ANÁLISE JURÍDICO-POLÍTICA: O eleitor gaúcho exige profundidade. Confronte a biografia do candidato com as dores socioeconômicas fornecidas, indicando como roubar votos de dinastias políticas tradicionais locais.
    3. TRAVA JURÍDICA TSE: Desenhe discursos e conteúdos de altíssimo impacto institucional ("Nosso dever é confrontar", "Exijo tolerância zero com"), mas NUNCA use palavras de pedido explícito de voto ("vote", "eleja", "apoie nas urnas").
    """

    class EngineGuerrilha:
        def generate_content(self, prompt_usuario):
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": prompt_usuario}
                ],
                temperature=0.1,  # Máxima precisão analítica e lógica
                max_tokens=2500
            )
            class Wrapper:
                def __init__(self, text): self.text = text
            return Wrapper(completion.choices[0].message.content)
            
    return EngineGuerrilha()

# ------------------------------------------------------------------------------
# 4. ONBOARDING TOTALMENTE NEUTRO (SEM PRÉ-PREENCHIMENTO COMERCIAL)
# ------------------------------------------------------------------------------
st.sidebar.title("👤 Inteligência de Origem")
st.sidebar.markdown("*Insira os dados reais do candidato para inicializar os algoritmos de guerrilha.*")

with st.sidebar.form("contexto_campanha"):
    nome_input = st.text_input("Nome de Urna", placeholder="Ex: Capitão Veríssimo")
    idade_input = st.number_input("Idade", min_value=18, max_value=90, value=35)
    partido_input = st.text_input("Partido / Federação", placeholder="Ex: NOVO / PP / MDB")
    nicho_input = st.text_input("Trincheira / Pauta Central", placeholder="Ex: Defesa do Livre Mercado / Segurança Pública")
    
    biografia_input = st.text_area(
        "Biografia e Capital Político do Candidato", 
        placeholder="Ex: Empresário local, sem histórico em cargos eletivos anteriores, muito forte entre lideranças comerciais da região litorânea, mas sem recall em Porto Alegre..."
    )
    
    # Lista de opções expandida para demonstrar dinamismo regional comercial
    OPCOES_REGIOES = list(DADOS_GEOPOLITICOS_RS.keys()) + ["LITORAL NORTE", "ZONA DA CAMPANHA", "SERRA CENTRAL", "VALE DO TAQUARI"]
    municipios_alvo = st.multiselect(
        "Cidades/Regiões Foco de Atuação", 
        options=OPCOES_REGIOES,
        default=[] # Tela totalmente limpa por padrão
    )
    
    ativar_motor = st.form_submit_button("🔥 Disparar Célula de Inteligência")

# ------------------------------------------------------------------------------
# 5. MEMÓRIA DE SESSÃO E SALVAMENTO DE ESTADO
# ------------------------------------------------------------------------------
if activar_motor:
    if not nome_input or not partido_input or not nicho_input or not biografia_input or not municipios_alvo:
        st.sidebar.error("⚠️ Operação Interrompida: Preencha TODOS os campos da barra lateral para forjar a identidade estratégica.")
    else:
        dados_candidato = {
            "nome": nome_input, 
            "idade": idade_input, 
            "partido": partido_input, 
            "nicho": nicho_input, 
            "biografia": biografia_input,
            "municipios": municipios_alvo
        }
        st.session_state['dados_candidato'] = dados_candidato
        st.session_state['motor_ia'] = inicializar_motor_campanha(api_key, dados_candidato)
        
        with st.spinner("Mapeando vulnerabilidades do território e quebrando defesas adversárias..."):
            try:
                response = st.session_state['motor_ia'].generate_content(
                    "Gere um Diagnóstico de Ruptura Eleitoral. Faça uma análise SWOT agressiva e profunda confrontando minha biografia com as regiões selecionadas e destacando as estratégias de guerrilha necessárias."
                )
                st.session_state['analise_inicial'] = response.text
                st.toast("Célula estratégica operando em nível máximo!", icon="✅")
            except Exception as e:
                st.error(f"Erro na API do Groq: {e}")

# ------------------------------------------------------------------------------
# 6. ABAS OPERACIONAIS DE COMANDO
# ------------------------------------------------------------------------------
tab_diagnostico, tab_bigdata, tab_conversao, tab_financeiro, tab_criativo = st.tabs([
    "🧠 Plano de Ruptura (SWOT)", 
    "📊 Big Data Geopolítico",
    "🗺️ Inteligência Territorial", 
    "💰 Alocação e Controle Financeiro",
    "📝 Fábrica de Conteúdo de Guerrilha"
])

# RENDERING CONTROLADO SEGURO
if 'motor_ia' in st.session_state:
    dados_usuario = st.session_state['dados_candidato']
    
    # --- ABA 1: PLANO DE RUPTURA ---
    with tab_diagnostico:
        st.subheader(f"Plano Tático de Ataque — {dados_usuario['nome']}")
        if 'analise_inicial' in st.session_state:
            st.markdown(st.session_state['analise_inicial'])
            st.text_area("Copiar Relatório SWOT:", value=st.session_state['analise_inicial'], height=120)

    # --- ABA 2: BIG DATA GEOPOLÍTICO HÍBRIDO (RESOLUÇÃO DO PONTO CEGO) ---
    with tab_bigdata:
        st.header("📊 Inteligência de Dados Demográficos e Eleitorais")
        st.markdown("Auditoria estatística ancorada em indicadores reais ou gerada por inferência perita sob demanda.")
        
        opcao_visualizacao = st.selectbox(
            "Selecione o recorte estatístico para auditoria:",
            options=["Consolidado Estadual (Geral)"] + dados_usuario['municipios']
        )
        
        # Lógica híbrida: verifica se a praça está mapeada ou se exige varredura do motor
        if opcao_visualizacao in DADOS_GEOPOLITICOS_RS:
            bd = DADOS_GEOPOLITICOS_RS[opcao_visualizacao]
            modo_ia_puro = False
        elif opcao_visualizacao == "Consolidado Estadual (Geral)":
            bd = DADOS_ESTADUAIS_GERAIS
            modo_ia_puro = False
        else:
            modo_ia_puro = True
            
        if not modo_ia_puro:
            col_bd1, col_bd2, col_bd3 = st.columns(3)
            col_bd1.metric("Eleitorado Alvo Fixo", f"{bd['eleitorado_total']:,} Votos")
            col_bd2.metric("Abstenção Média Histórica", bd['abstencao_media'])
            col_bd3.metric("Recorte Geográfico", bd['regiao'])
            
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.info(f"**Matriz Socioeconômica Regional:**\n\n{bd['perfil_socioeconomico']}")
            with col_info2:
                st.warning(f"**Comportamento de Urna e Histórico:**\n\n{bd['comportamento_historico']}")
        else:
            st.warning(f"🌐 Região '{opcao_visualizacao}' detectada fora do núcleo fixo. Ativando Varredura Neural de Big Data...")
            st.markdown("*O motor vai buscar em seu ecossistema de dados o perfil demográfico, as dores macroeconômicas e estimativas históricas para esta praça.*")

        st.markdown("---")
        
        # Botão de geração profunda de cenários de voz e tom adaptativo
        if st.button(f"🧠 Forjar Cenários de Discurso e Tom para {opcao_visualizacao}"):
            with st.spinner("Calculando ressonância psicológica do eleitorado local..."):
                if not modo_ia_puro:
                    contexto_prompt = f"Perfil Socioeconômico: {bd['perfil_socioeconomico']}. Histórico de Urna: {bd['comportamento_historico']}. Dores: {bd['principais_dores']}."
                else:
                    contexto_prompt = f"Gere os dados demográficos, estimativas de eleitorado, abstenção e matriz socioeconômica crua para a região de {opcao_visualizacao} no Rio Grande do Sul."
                
                prompt_bd = f"""
                Analise o seguinte cenário territorial para a praça [{opcao_visualizacao}]:
                Contexto Regional: {contexto_prompt}
                
                Considerando minha biografia ("{dados_usuario['biografia']}") e meu nicho ("{dados_usuario['nicho']}"), monte um relatório tático de nível PhD apresentando de forma aprofundada, crua e arrojada:
                1. DADOS SOCIOECONÔMICOS E GEOPOLÍTICOS: Se a região for nova, estabeleça os parâmetros estimados.
                2. TRÊS CENÁRIOS DE TOM DE DISCURSO DE GUERRA (Cenário A: Invasão/Ruptura Agressiva, Cenário B: Contraponto Técnico, Cenário C: Conexão Popular/Demanda de Base). Diga exatamente a frase de impacto que inicia cada tom e qual deles possui maior viabilidade matemática de quebrar as dinastias locais.
                3. ZONA DE REJEIÇÃO: O que o candidato está terminantemente proibido de falar para não ser esmagado pelo histórico cultural dessa região.
                """
                try:
                    relatorio_bd = st.session_state['motor_ia'].generate_content(prompt_bd)
                    st.session_state[f'discurso_{opcao_visualizacao}'] = relatorio_bd.text
                except Exception as e:
                    st.error(f"Erro no motor de Big Data: {e}")
                    
        if f'discurso_{opcao_visualizacao}' in st.session_state:
            st.subheader(f"🔥 Diretrizes de Discurso e Posicionamento Adaptativo")
            st.markdown(st.session_state[f'discurso_{opcao_visualizacao}'])
            st.text_area("Copiar Dossiê de Discurso:", value=st.session_state[f'discurso_{opcao_visualizacao}'], height=120)

    # --- ABA 3: CONVERSÃO TERRITORIAL DE CAMPO ---
    with tab_conversao:
        st.header("🗺️ Plano de Infiltração Territorial")
        cidade_foco = st.selectbox("Selecione a praça para auditoria tática de cabos eleitorais:", options=dados_usuario['municipios'])
        
        st.subheader("🧮 Calculadora de Estrutura Terrestre (CRM)")
        col_crm1, col_crm2, col_crm3 = st.columns(3)
        with col_crm1:
            num_liderancas = st.number_input("Número de Generais de Base (Líderes) na Cidade", min_value=0, max_value=100, value=5, key=f"lid_{cidade_foco}")
        with col_crm2:
            media_votos_lider = st.number_input("Cobrança de Meta por General (Votos)", min_value=10, max_value=5000, value=1000, key=f"meta_{cidade_foco}")
        with col_crm3:
            votos_opiniao_insta = st.slider("Arrasto Projetado por Tráfego Pago (Aéreo)", min_value=0, max_value=20000, value=2000, key=f"traf_{cidade_foco}")
            
        votos_estrutura_total = num_liderancas * media_votos_lider
        votos_projetados_totais = votos_estrutura_total + votos_opiniao_insta
        
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Votos Amarrados em Terra", f"{votos_estrutura_total:,}")
        col_m2.metric("Projeção Real de Urna (Alvo)", f"{votos_projetados_totais:,}")
        
        if st.button(f"🔥 Forjar Plano de Ocupação para {cidade_foco}"):
            with st.spinner("Forjando ordens de batalha para as lideranças..."):
                prompt_analise = f"""
                Gere um Relatório de Ocupação Territorial Estratégica para a região de {cidade_foco}.
                Meta de Votos Terrestres: {votos_estrutura_total} baseada em {num_liderancas} líderes de base.
                Meta de Votos de Redes (Aéreo): {votos_opiniao_insta} votos.
                
                Com base na BIOGRAFIA e HISTÓRICO do candidato, entregue uma estratégia de guerra arrojada:
                1. ARMA DE COBRANÇA: Como o candidato constrange, audita e amarra essas {num_liderancas} lideranças para garantir que entreguem os {media_votos_lider} votos prometidos sem traição ou desvio para concorrentes tradicionais.
                2. ASSALTO NARRATIVO: Qual ação tática de impacto de guerrilha terrestre (infiltração em feiras, sindicatos ou eventos) o candidato deve fazer nesta praça para roubar o eleitorado consolidado das raposas políticas tradicionais.
                """
                try:
                    relatorio_cidade = st.session_state['motor_ia'].generate_content(prompt_analise)
                    st.session_state[f'relatorio_{cidade_foco}'] = relatorio_cidade.text
                except Exception as e:
                    st.error(f"Erro no motor territorial: {e}")
                    
        if f'relatorio_{cidade_foco}' in st.session_state:
            st.markdown("---")
            st.markdown(st.session_state[f'relatorio_{cidade_foco}'])
            st.text_area("Copiar Relatório Territorial:", value=st.session_state[f'relatorio_{cidade_foco}'], height=120)

    # --- ABA 4: ALOCAÇÃO E CONTROLE FINANCEIRO ---
    with tab_financeiro:
        st.header("💰 Planejamento Financeiro de Mobilização e Pessoal")
        st.markdown("Controle de alocação de trabalhadores de campanha e auditoria de teto de gastos por região de conflito.")
        
        lista_dados_financeiros = []
        for cidade in dados_usuario['municipios']:
            with st.expander(f"⚙️ Orçamento de Pessoal — {cidade}", expanded=True):
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    militantes = st.number_input(f"Militantes / Panfleteiros (Qtd)", min_value=0, value=20, key=f"mil_q_{cidade}")
                    sal_militante = st.number_input(f"Remuneração por Militante (R$)", min_value=0, value=1500, key=f"mil_s_{cidade}")
                with col_f2:
                    coordenadores = st.number_input(f"Coordenadores de Área (Qtd)", min_value=0, value=2, key=f"coord_q_{cidade}")
                    sal_coordenador = st.number_input(f"Remuneração por Coordenador (R$)", min_value=0, value=4000, key=f"coord_s_{cidade}")
                with col_f3:
                    fiscais = st.number_input(f"Fiscais de Urna (Qtd)", min_value=0, value=10, key=f"fisc_q_{cidade}")
                    sal_fiscal = st.number_input(f"Remuneração por Fiscal (R$)", min_value=0, value=300, key=f"fisc_s_{cidade}")
            
            custo_total_cidade = (militantes * sal_militante) + (coordenadores * sal_coordenador) + (fiscais * sal_fiscal)
            total_trabalhadores = militantes + coordenadores + fiscais
            
            lista_dados_financeiros.append({
                "Região/Cidade": cidade,
                "Trabalhadores": total_trabalhadores,
                "Investimento Pessoal (R$)": custo_total_cidade
            })
            
        df_financeiro = pd.DataFrame(lista_dados_financeiros)
        
        st.markdown("---")
        st.subheader("🏁 Consolidação de Custos do Comitê Central")
        
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.dataframe(df_financeiro, use_container_width=True, hide_index=True)
            investimento_total_estado = df_financeiro["Investimento Pessoal (R$)"].sum()
            st.metric("Investimento Total em Pessoal Terrestre", f"R$ {investimento_total_estado:,.2f}")
            
        with col_res2:
            st.markdown("**Distribuição Visual do Fundo Eleitoral por Região**")
            st.bar_chart(df_financeiro.set_index("Região/Cidade")["Investimento Pessoal (R$)"])

    # --- ABA 5: FÁBRICA DE POSTS AUTÔNOMA E INTEGRADA ---
    with tab_criativo:
        st.header("📝 Fábrica de Ataque Digital")
        st.markdown("Peças de comunicação tática de alto impacto territorial com blindagem anti-sanção do TSE.")
        
        st.markdown(
            f"""
            <div style="background-color: #f1f5f9; padding: 12px; border-radius: 4px; margin-bottom: 15px; border-left: 4px solid #b91c1c;">
                <strong>Briefing de Combate Ativo:</strong> {dados_usuario['nome']} | Linha Ideológica: {dados_usuario['nicho']}
            </div>
            """, unsafe_allow_html=True
        )
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            canal = st.selectbox("Formato da Arma Digital", ["Roteiro de Vídeo Curto (Reels Agressivo)", "Carrossel de Confronto", "Nota de Ataque Institucional"])
        with col_c2:
            cidade_recorte = st.selectbox("Afunilar Alvo Narrativo para qual Cidade?", ["Foco Estadual Geral"] + dados_usuario['municipios'])
            
        pauta_dia = st.text_area("O Fato Político ou Notícia do Dia para Posicionamento:", placeholder="Ex: Quebra de maquinários agrícolas por falta de manutenção nas estradas locais ou escândalo de emendas do rival...")
        
        if st.button("🚀 Disparar Linha de Produção Digital"):
            if not pauta_dia:
                st.error("⚠️ Insira uma pauta real para orientar a redação.")
            else:
                with st.spinner("Redigindo peça institucional sob as travas do TSE..."):
                    prompt_criativo = f"""
                    Gere uma peça no formato [{canal}] focado em [{cidade_recorte}].
                    Notícia/Fato do dia a explorar: "{pauta_dia}".
                    
                    ESTRUTURA OBRIGATÓRIA DA RESPOSTA:
                    1. HOOK / GANCHO (Primeiros 3 segundos para travar o feed do eleitor gaúcho).
                    2. ARGUMENTO DE GUERRA (Exponha o escândalo/fato, use a biografia do candidato para trazer autoridade e esmague a omissão dos rivais tradicionais).
                    3. CHAMADA INSTITUCIONAL (Engajamento e convocação de debate, com total compliance anti-TSE, sem pedir votos).
                    """
                    try:
                        peca_final = st.session_state['motor_ia'].generate_content(prompt_creativo)
                        st.session_state['peca_comunicacao_atual'] = peca_final.text
                    except Exception as e:
                        st.error(f"Erro na fábrica de criativos: {e}")
                        
        if 'peca_comunicacao_atual' in st.session_state:
            st.markdown("---")
            st.subheader("🔥 Peça Pronta para Distribuição")
            st.markdown(st.session_state['peca_comunicacao_atual'])
            st.text_area("Copiar Peça para Redes/WhatsApp:", value=st.session_state['peca_comunicacao_atual'], height=120)

else:
    with tab_diagnostico:
        st.info("👋 Central Aegis Eleitoral Zerada e Pronta para Onboarding. Insira o perfil, o partido e a biografia profunda do candidato na barra lateral para abrir a central de controle comercial.")
