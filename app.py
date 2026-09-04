# -*- coding: utf-8 -*-
"""
Painel de Ações SINOVA MT v2.0
==============================
Dashboard interativo (Streamlit) para consulta das ações do SINOVA.
v2.0:
- Adiciona abas para melhor organização.
- Limpa categorias genéricas dos gráficos para focar em parcerias.
- Unifica categorias ("Reunião" e "Reuniões").
- Melhora a estética dos gráficos.
"""

import unicodedata
import pandas as pd
import plotly.express as px
import streamlit as st

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# =============================================================================
st.set_page_config(
    page_title="🚀 Painel de Ações SINOVA MT",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# 2. FONTES DE DADOS E CONSTANTES
# =============================================================================
# URLs da planilha do Google Sheets (já preenchidas)
URL_ABA_INTERNO = "https://docs.google.com/spreadsheets/d/1RAfdxYZOQYMGWRnWONSraUWyzh7vSOAyVJTtBMGXz6o/export?format=csv&gid=0"
URL_ABA_EXTERNO = "https://docs.google.com/spreadsheets/d/1RAfdxYZOQYMGWRnWONSraUWyzh7vSOAyVJTtBMGXz6o/export?format=csv&gid=600618779"

# Paleta de cores para os gráficos
COR_PRIMARIA = "#1F6FEB"
COR_SECUNDARIA = "#00A88F"
COR_DESTAQUE = "#F2A33C"

# Categorias a serem excluídas dos gráficos de órgãos para focar em parcerias
ORGAOS_A_EXCLUIR = [
    "ÓRGÃOS E ENTIDADES DO ESTADO",
    "Não informado",
    "PESSOAS SENSIBILIZADAS",
    "GESTÃO DE PESSOA",
]

# =============================================================================
# 3. ETL - CARGA, PADRONIZAÇÃO E LIMPEZA
# =============================================================================

def _normalizar(nome: str) -> str:
    texto = str(nome)
    for simbolo in ("º", "°", "ª"):
        texto = texto.replace(simbolo, "")
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.upper().split())

MAPA_COLUNAS = {
    "PRODUTOS": "Produto", "PRODUTO": "Produto", "TIPO": "Produto",
    "DATA/MES": "Data", "DATA / MES": "Data", "DATA": "Data", "MES": "Data",
    "N DE PARTICIPANTES": "Participantes", "N. DE PARTICIPANTES": "Participantes",
    "NUMERO DE PARTICIPANTES": "Participantes", "PARTICIPANTES": "Participantes",
    "ORGAO": "Orgao", "ORGAOS": "Orgao",
    "CATEGORIA": "Categoria", "ATIVIDADE": "Atividade",
}

def _padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    renomear = {}
    for coluna in df.columns:
        chave = _normalizar(coluna)
        renomear[coluna] = MAPA_COLUNAS.get(chave, str(coluna).strip())
    df = df.rename(columns=renomear)
    return df.loc[:, ~df.columns.duplicated()]

@st.cache_data(ttl=600, show_spinner="Carregando e tratando dados do Google Sheets...")
def carregar_dados() -> pd.DataFrame:
    df_interno = pd.read_csv(URL_ABA_INTERNO)
    df_externo = pd.read_csv(URL_ABA_EXTERNO, skiprows=1)

    df_interno = _padronizar_colunas(df_interno)
    df_externo = _padronizar_colunas(df_externo)

    df_interno["Origem"] = "Interno"
    df_externo["Origem"] = "Externo"

    df_full = pd.concat([df_interno, df_externo], ignore_index=True, sort=False)

    colunas_esperadas = ["Data", "Produto", "Atividade", "Orgao", "Categoria", "Participantes"]
    for coluna in colunas_esperadas:
        if coluna not in df_full.columns:
            df_full[coluna] = pd.NA

    df_full = df_full.dropna(how="all")
    df_full["Data"] = pd.to_datetime(df_full["Data"], errors="coerce", dayfirst=True)
    df_full = df_full.dropna(subset=["Data"])
    df_full["MES_ANO"] = df_full["Data"].dt.strftime("%Y-%m")
    df_full["Participantes"] = pd.to_numeric(df_full["Participantes"], errors="coerce").fillna(0).astype(int)

    for coluna in ["Produto", "Orgao", "Categoria", "Atividade"]:
        df_full[coluna] = df_full[coluna].astype("string").str.strip().replace({"": pd.NA}).fillna("Não informado")

    df_full['Categoria'] = df_full['Categoria'].str.replace('REUNIÕES', 'REUNIÃO', case=False)
    
    return df_full.sort_values("Data").reset_index(drop=True)

def formatar_milhar(valor) -> str:
    return f"{int(valor):,}".replace(",", ".")

def grafico_barras_h(dados: pd.DataFrame, x: str, y: str, titulo: str, cor: str):
    fig = px.bar(
        dados, x=x, y=y, orientation="h", text=x, title=titulo,
        color_discrete_sequence=[cor]
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        yaxis=dict(title="", categoryorder="total ascending"),
        xaxis=dict(title=""),
        margin=dict(l=10, r=40, t=60, b=10),
        height=430,
        plot_bgcolor="rgba(0,0,0,0)",
        title=dict(x=0.5),
        title_font_size=18,
        showlegend=False,
    )
    return fig

# =============================================================================
# 4. TÍTULO E CARGA DOS DADOS
# =============================================================================
st.title("🚀 Painel de Ações SINOVA MT")
st.caption("Laboratório de Inovação da SEPLAG/MT — acompanhamento das ações internas e externas.")

try:
    df_full = carregar_dados()
except Exception as erro:
    st.error(
        "**Não foi possível carregar os dados do Google Sheets.**\n\n"
        "Verifique se as URLs de exportação CSV estão preenchidas corretamente e "
        "se a planilha está compartilhada como *Qualquer pessoa com o link — Leitor*."
    )
    st.exception(erro)
    st.stop()

# =============================================================================
# 5. BARRA LATERAL - FILTROS
# =============================================================================
st.sidebar.header("🎛️ Filtros")

produtos_disponiveis = sorted(df_full["Produto"].unique().tolist())
orgaos_disponiveis = sorted(df_full["Orgao"].unique().tolist())
meses_disponiveis = sorted(df_full["MES_ANO"].unique().tolist())

produtos_selecionados = st.sidebar.multiselect("Produto", options=produtos_disponiveis, default=[], placeholder="Todos os produtos")
orgaos_selecionados = st.sidebar.multiselect("Órgão", options=orgaos_disponiveis, default=[], placeholder="Todos os órgãos")

if len(meses_disponiveis) > 1:
    periodo_inicio, periodo_fim = st.sidebar.select_slider("Período (mês/ano)", options=meses_disponiveis, value=(meses_disponiveis[0], meses_disponiveis[-1]))
else:
    periodo_inicio = periodo_fim = meses_disponiveis[0]

df_filtrado = df_full[df_full["MES_ANO"].between(periodo_inicio, periodo_fim)].copy()
if produtos_selecionados:
    df_filtrado = df_filtrado[df_filtrado["Produto"].isin(produtos_selecionados)]
if orgaos_selecionados:
    df_filtrado = df_filtrado[df_filtrado["Orgao"].isin(orgaos_selecionados)]

# =============================================================================
# 6. LAYOUT COM ABAS
# =============================================================================
tab1, tab2 = st.tabs(["📊 Visão Geral", "📋 Detalhes por Ação"])

with tab1:
    if df_filtrado.empty:
        st.warning("⚠️ Nenhuma ação encontrada para os filtros selecionados.")
        st.stop()

    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    col_kpi1.metric("Total de Ações Realizadas", formatar_milhar(len(df_filtrado)))
    col_kpi2.metric("Total de Participações", formatar_milhar(df_filtrado["Participantes"].sum()))
    col_kpi3.metric("Órgãos Parceiros Envolvidos", formatar_milhar(df_filtrado["Orgao"].nunique()))
    st.divider()

    col_esq, col_dir = st.columns(2)

    with col_esq:
        df_orgaos_grafico = df_filtrado[~df_filtrado["Orgao"].isin(ORGAOS_A_EXCLUIR)]
        acoes_por_orgao = df_orgaos_grafico["Orgao"].value_counts().head(15).rename_axis("Orgao").reset_index(name="Ações").sort_values("Ações", ascending=True)
        st.plotly_chart(grafico_barras_h(acoes_por_orgao, x="Ações", y="Orgao", titulo="🏛️ Ações por Órgão Parceiro (Top 15)", cor=COR_PRIMARIA), use_container_width=True)

    with col_dir:
        acoes_por_categoria = df_filtrado["Categoria"].value_counts().rename_axis("Categoria").reset_index(name="Ações").sort_values("Ações", ascending=True)
        st.plotly_chart(grafico_barras_h(acoes_por_categoria, x="Ações", y="Categoria", titulo="🗂️ Ações por Categoria", cor=COR_SECUNDARIA), use_container_width=True)

    top_acoes = df_filtrado.nlargest(10, "Participantes").copy()
    top_acoes["Ação"] = top_acoes["Atividade"].where(top_acoes["Atividade"] != "Não informado", top_acoes["Produto"]).str.slice(0, 60)
    top_acoes["Ação"] = top_acoes["Ação"] + " (" + top_acoes["Data"].dt.strftime("%m/%Y") + ")"
    top_acoes = top_acoes.sort_values("Participantes", ascending=True)
    st.plotly_chart(grafico_barras_h(top_acoes, x="Participantes", y="Ação", titulo="🏆 Top 10 Ações Mais Impactantes", cor=COR_DESTAQUE), use_container_width=True)

with tab2:
    st.subheader("Tabela de Ações Registradas")
    colunas_exibicao = ["Data", "Produto", "Atividade", "Orgao", "Categoria", "Participantes", "Origem"]
    st.dataframe(
        df_filtrado[colunas_exibicao].sort_values("Data", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Participantes": st.column_config.NumberColumn("Participantes", format="%d"),
        },
    )
    st.download_button(
        "⬇️ Baixar dados filtrados em CSV",
        data=df_filtrado[colunas_exibicao].to_csv(index=False).encode("utf-8-sig"),
        file_name="sinova_acoes_filtradas.csv",
        mime="text/csv",
    )
