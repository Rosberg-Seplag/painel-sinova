# -*- coding: utf-8 -*-
"""
Painel de Ações SINOVA MT v4.0
==============================
Dashboard interativo para consulta de ações e resultados do SINOVA.
v4.0:
- Reformula a aba "Indicadores de Produto" para uma exibição visual com KPIs e gráficos.
- Adiciona um gráfico de evolução para o indicador principal de cada produto.
- Mantém a tabela detalhada em um expander para uma interface mais limpa.
"""

import unicodedata
import pandas as pd
import plotly.express as px
import streamlit as st

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# =============================================================================
st.set_page_config(
    page_title="🚀 Painel SINOVA MT",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# 2. FONTES DE DADOS E CONSTANTES
# =============================================================================
URL_ABA_INTERNO = "https://docs.google.com/spreadsheets/d/1RAfdxYZOQYMGWRnWONSraUWyzh7vSOAyVJTtBMGXz6o/export?format=csv&gid=0"
URL_ABA_EXTERNO = "https://docs.google.com/spreadsheets/d/1RAfdxYZOQYMGWRnWONSraUWyzh7vSOAyVJTtBMGXz6o/export?format=csv&gid=600618779"
URL_ABA_INDICADORES = "https://docs.google.com/spreadsheets/d/1RAfdxYZOQYMGWRnWONSraUWyzh7vSOAyVJTtBMGXz6o/export?format=csv&gid=1510207902"

COR_PRIMARIA = "#1F6FEB"
COR_SECUNDARIA = "#00A88F"
COR_DESTAQUE = "#F2A33C"

ORGAOS_A_EXCLUIR = [
    "ÓRGÃOS E ENTIDADES DO ESTADO", "Não informado",
    "PESSOAS SENSIBILIZADAS", "GESTÃO DE PESSOA",
]

# =============================================================================
# 3. FUNÇÕES DE ETL E VISUALIZAÇÃO
# =============================================================================

@st.cache_data(ttl=600, show_spinner="Carregando dados de Ações...")
def carregar_dados_acoes() -> pd.DataFrame:
    # Função para carregar e tratar as abas de ações (interno/externo)
    def _normalizar(nome: str) -> str:
        texto = str(nome)
        for simbolo in ("º", "°", "ª"): texto = texto.replace(simbolo, "")
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(c for c in texto if not unicodedata.combining(c))
        return " ".join(texto.upper().split())

    MAPA_COLUNAS = {
        "PRODUTOS": "Produto", "PRODUTO": "Produto", "TIPO": "Produto", "DATA/MES": "Data",
        "DATA / MES": "Data", "DATA": "Data", "MES": "Data", "N DE PARTICIPANTES": "Participantes",
        "N. DE PARTICIPANTES": "Participantes", "NUMERO DE PARTICIPANTES": "Participantes",
        "PARTICIPANTES": "Participantes", "ORGAO": "Orgao", "ORGAOS": "Orgao",
        "CATEGORIA": "Categoria", "ATIVIDADE": "Atividade",
    }

    def _padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
        renomear = {c: MAPA_COLUNAS.get(_normalizar(c), str(c).strip()) for c in df.columns}
        return df.rename(columns=renomear).loc[:, ~df.columns.duplicated()]

    df_interno = pd.read_csv(URL_ABA_INTERNO)
    df_externo = pd.read_csv(URL_ABA_EXTERNO, skiprows=1)
    df_interno = _padronizar_colunas(df_interno); df_externo = _padronizar_colunas(df_externo)
    df_interno["Origem"] = "Interno"; df_externo["Origem"] = "Externo"
    df_full = pd.concat([df_interno, df_externo], ignore_index=True, sort=False)

    for col in ["Data", "Produto", "Atividade", "Orgao", "Categoria", "Participantes"]:
        if col not in df_full.columns: df_full[col] = pd.NA

    df_full = df_full.dropna(how="all")
    df_full["Data"] = pd.to_datetime(df_full["Data"], errors="coerce", dayfirst=True)
    df_full = df_full.dropna(subset=["Data"])
    df_full["MES_ANO"] = df_full["Data"].dt.strftime("%Y-%m")
    df_full["Participantes"] = pd.to_numeric(df_full["Participantes"], errors="coerce").fillna(0).astype(int)

    for col in ["Produto", "Orgao", "Categoria", "Atividade"]:
        df_full[col] = df_full[col].astype("string").str.strip().replace({"": pd.NA}).fillna("Não informado")

    df_full['Categoria'] = df_full['Categoria'].str.replace('REUNIÕES', 'REUNIÃO', case=False)
    return df_full.sort_values("Data").reset_index(drop=True)

@st.cache_data(ttl=600, show_spinner="Carregando dados de Indicadores...")
def carregar_dados_indicadores() -> pd.DataFrame:
    df = pd.read_csv(URL_ABA_INDICADORES)
    if "PRODUTOS" in df.columns:
        df["PRODUTOS"] = df["PRODUTOS"].str.strip()
    # Limpa colunas que são totalmente vazias na planilha inteira
    df = df.dropna(axis=1, how='all')
    # Converte colunas numéricas, tratando erros
    for col in df.columns:
        if col != 'PRODUTOS':
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

def formatar_milhar(valor) -> str:
    if pd.isna(valor): return "N/D"
    return f"{int(valor):,}".replace(",", ".")

def grafico_barras_h(dados: pd.DataFrame, x: str, y: str, titulo: str, cor: str):
    fig = px.bar(dados, x=x, y=y, orientation="h", text=x, title=titulo, color_discrete_sequence=[cor])
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        yaxis=dict(title="", categoryorder="total ascending"),
        xaxis=dict(title=""), margin=dict(l=10, r=40, t=60, b=10),
        height=430, plot_bgcolor="rgba(0,0,0,0)",
        title=dict(x=0.5), title_font_size=18, showlegend=False,
    )
    return fig

# =============================================================================
# 4. TÍTULO E CARGA DOS DADOS
# =============================================================================
st.title("🚀 Painel de Ações e Resultados SINOVA MT")
st.caption("Laboratório de Inovação da SEPLAG/MT — acompanhamento de ações e indicadores de produto.")

try:
    df_acoes = carregar_dados_acoes()
    df_indicadores = carregar_dados_indicadores()
except Exception as erro:
    st.error("**Não foi possível carregar os dados do Google Sheets.**\n\nVerifique se as URLs estão corretas e se a planilha está compartilhada como *Qualquer pessoa com o link — Leitor*.")
    st.exception(erro)
    st.stop()

# =============================================================================
# 5. BARRA LATERAL - FILTROS GERAIS
# =============================================================================
st.sidebar.header("🎛️ Filtros para Ações")
# ... (código dos filtros da barra lateral permanece igual)

# =============================================================================
# 6. LAYOUT COM ABAS
# =============================================================================
tab_acoes, tab_detalhes, tab_indicadores = st.tabs(["📊 Visão Geral de Ações", "📋 Detalhes por Ação", "🏆 Indicadores de Produto"])

with tab_acoes:
    # ... (código da aba de ações permanece igual)
    
with tab_detalhes:
    # ... (código da aba de detalhes permanece igual)

with tab_indicadores:
    st.header("Resultados Consolidados por Produto")
    
    # Extrai o nome do produto base para o filtro
    df_indicadores['Produto_Base'] = df_indicadores['PRODUTOS'].str.extract(r"([a-zA-ZÀ-ú\s]+)", expand=False).str.strip()
    produtos_base = sorted(df_indicadores['Produto_Base'].dropna().unique().tolist())
    
    produto_selecionado_ind = st.selectbox(
        "Selecione um Produto para ver seus resultados",
        options=produtos_base,
        index=0,
        placeholder="Selecione um produto..."
    )

    if produto_selecionado_ind:
        df_ind_filtrado = df_indicadores[df_indicadores['Produto_Base'] == produto_selecionado_ind]
        
        st.subheader(f"KPIs para: {produto_selecionado_ind}")
        
        # --- Exibição de KPIs em Cartões ---
        kpi_cols = st.columns(4) # Cria 4 colunas para os KPIs
        col_idx = 0
        
        # Define o indicador principal para o gráfico de evolução
        indicador_principal = None
        
        for col in df_ind_filtrado.columns:
            if col not in ['PRODUTOS', 'Produto_Base'] and not df_ind_filtrado[col].isnull().all():
                total = df_ind_filtrado[col].sum()
                kpi_cols[col_idx % 4].metric(
                    label=col.replace('_', ' ').title(),
                    value=formatar_milhar(total)
                )
                col_idx += 1
                # Define a primeira métrica encontrada como principal para o gráfico
                if indicador_principal is None:
                    indicador_principal = col

        st.divider()

        # --- Gráfico de Evolução ---
        if indicador_principal:
            st.subheader(f"Evolução de '{indicador_principal.replace('_', ' ').title()}' por Edição")
            df_chart = df_ind_filtrado[['PRODUTOS', indicador_principal]].dropna()
            df_chart = df_chart.sort_values(by='PRODUTOS')
            
            fig = px.bar(df_chart, x='PRODUTOS', y=indicador_principal, text_auto=True,
                         title=f"Evolução de {indicador_principal.replace('_', ' ').title()}")
            fig.update_traces(marker_color=COR_DESTAQUE, textposition='outside')
            fig.update_layout(xaxis_title="Edição/Ano", yaxis_title=indicador_principal.replace('_', ' ').title())
            st.plotly_chart(fig, use_container_width=True)
        
        # --- Tabela de Detalhes ---
        with st.expander("Ver dados completos da tabela"):
            df_tabela = df_ind_filtrado.drop(columns=['Produto_Base']).dropna(axis=1, how='all').set_index('PRODUTOS')
            st.dataframe(df_tabela, use_container_width=True)

