from __future__ import annotations

from pathlib import Path

import streamlit as st


PROJECT_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = PROJECT_DIR / "Icones" / "Logo Confeirtaria.jpeg"
# Cor predominante medida diretamente no fundo do arquivo do logo: RGB(249, 211, 52).
CAJU_YELLOW = "#F9D334"


def configure_page(title: str = "Caju | Doces em família") -> None:
    """Configura a página e aplica o tema comum antes de renderizar conteúdo."""
    st.set_page_config(
        page_title=title,
        page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🧁",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _mark_page_as_notranslate()
    _apply_global_styles()


def _mark_page_as_notranslate() -> None:
    """Sinaliza ao tradutor sem manipular o DOM controlado pelo Streamlit."""
    st.markdown(
        """
        <meta name="google" content="notranslate">
        <span class="notranslate" translate="no" style="display:none">
            Aplicação originalmente em português do Brasil.
        </span>
        """,
        unsafe_allow_html=True,
    )


def _navigate_to(page: str) -> None:
    """Troca a tela dentro da sessão, sem recarregar o navegador."""
    st.query_params.clear()
    if page != "inicio":
        st.query_params["pagina"] = page


def _refresh_sheet_data() -> None:
    """Limpa leituras em cache e força a recarga dos registros abertos."""
    st.cache_data.clear()
    # Mantemos as seleções da receita/ingrediente, mas removemos os marcadores
    # de hidratação para que os dados sejam relidos da planilha no novo rerun.
    st.session_state.pop("edit_recipe_editor_context", None)
    st.session_state.pop("edit_ingredient_context", None)
    st.toast("Dados atualizados com a planilha.")


def render_sidebar(active_page: str = "inicio") -> None:
    """Exibe o menu lateral padrão da aplicação."""
    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)

        st.markdown('<p class="menu-title">CARDÁPIO</p>', unsafe_allow_html=True)
        menu_items = (
            ("inicio", "⌂", "Início"),
            ("ingredientes", "＋", "Ingredientes"),
            ("receitas", "≡", "Receitas"),
        )
        normalized_active_page = (
            "ingredientes" if active_page == "materia-prima" else active_page
        )
        for page, icon, label in menu_items:
            state = "active" if page == normalized_active_page else "inactive"
            st.button(
                f"{icon}  {label}",
                key=f"sidebar_nav_{page}_{state}",
                use_container_width=True,
                on_click=_navigate_to,
                args=(page,),
            )


def render_page_header(title: str, subtitle: str | None = None) -> None:
    """Exibe título à esquerda e o logo padrão no canto superior direito."""
    text_column, refresh_column, logo_column = st.columns(
        [5, 1.25, 1],
        vertical_alignment="center",
    )

    with text_column:
        st.markdown(f'<h1 class="page-title">{title}</h1>', unsafe_allow_html=True)
        if subtitle:
            st.markdown(
                f'<p class="page-subtitle">{subtitle}</p>',
                unsafe_allow_html=True,
            )

    with refresh_column:
        st.button(
            "↻ Atualizar dados",
            key=f"refresh_data_{title}",
            use_container_width=True,
            on_click=_refresh_sheet_data,
        )

    with logo_column:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)

    st.markdown('<div class="header-line"></div>', unsafe_allow_html=True)


def _apply_global_styles() -> None:
    st.markdown(
        f"""
        <style>
            :root {{
                --caju-yellow: {CAJU_YELLOW};
                --caju-black: #111111;
                --caju-shadow: rgba(17, 17, 17, 0.16);
            }}

            .stApp,
            [data-testid="stAppViewContainer"],
            [data-testid="stHeader"],
            [data-testid="stMain"],
            [data-testid="stMainBlockContainer"] {{
                background: var(--caju-yellow);
            }}

            [data-testid="stHeader"] {{
                background: color-mix(in srgb, var(--caju-yellow) 92%, transparent);
            }}

            [data-testid="stSidebar"],
            [data-testid="stSidebarContent"] {{
                background: var(--caju-yellow);
            }}

            [data-testid="stSidebar"] {{
                border-right: 2px solid var(--caju-black);
            }}

            [data-testid="stSidebar"] img {{
                border-radius: 14px;
            }}

            [data-testid="stSidebar"] [class*="st-key-sidebar_nav_"] button {{
                min-height: 3rem;
                margin: 0.1rem 0;
                padding: 0.65rem 0.85rem;
                justify-content: flex-start;
                color: var(--caju-black) !important;
                background: var(--caju-yellow) !important;
                border: 2px solid var(--caju-black) !important;
                border-radius: 12px !important;
                box-shadow: none !important;
                font-weight: 800;
            }}

            [data-testid="stSidebar"] [class*="st-key-sidebar_nav_"] button:hover,
            [data-testid="stSidebar"] [class*="st-key-sidebar_nav_"][class*="_active"] button {{
                color: var(--caju-black) !important;
                background: rgba(17, 17, 17, 0.08) !important;
            }}

            [data-testid="stSidebar"] [class*="st-key-sidebar_nav_"] button p,
            [data-testid="stSidebar"] [class*="st-key-sidebar_nav_"] button span {{
                color: var(--caju-black) !important;
            }}

            .menu-title {{
                margin: 1rem 0 0.5rem;
                color: var(--caju-black);
                font-size: 0.78rem;
                font-weight: 900;
                letter-spacing: 0.16em;
            }}

            .page-title {{
                margin: 0;
                color: var(--caju-black);
                font-size: clamp(2rem, 4vw, 3.4rem);
                font-weight: 900;
                letter-spacing: -0.045em;
            }}

            .page-subtitle {{
                margin: 0.35rem 0 0;
                color: var(--caju-black);
                font-size: 1.05rem;
            }}

            .header-line {{
                width: 100%;
                height: 2px;
                margin: 0.4rem 0 1.6rem;
                background: var(--caju-black);
            }}

            .caju-card {{
                min-height: 150px;
                padding: 1.35rem 1.5rem;
                color: var(--caju-black);
                background: var(--caju-yellow);
                border: 2px solid var(--caju-black);
                border-radius: 16px;
                box-shadow: none;
            }}

            .caju-card h3 {{ margin-top: 0; }}

            /* Padrão global para todos os botões que executam ações. */
            .stButton > button,
            .stDownloadButton > button,
            .stFormSubmitButton > button {{
                min-height: 3rem;
                color: var(--caju-yellow) !important;
                background: var(--caju-black) !important;
                border: 2px solid var(--caju-black);
                border-radius: 11px;
                box-shadow: none;
                font-weight: 800;
                transition: background 120ms ease;
            }}

            .stButton > button:hover,
            .stDownloadButton > button:hover,
            .stFormSubmitButton > button:hover {{
                color: var(--caju-yellow) !important;
                background: #242424 !important;
                border-color: var(--caju-black) !important;
                box-shadow: none;
            }}

            .stButton > button:focus,
            .stButton > button:focus-visible,
            .stDownloadButton > button:focus,
            .stDownloadButton > button:focus-visible,
            .stFormSubmitButton > button:focus,
            .stFormSubmitButton > button:focus-visible {{
                color: var(--caju-yellow) !important;
                background: var(--caju-black) !important;
                border-color: var(--caju-black);
                outline: 2px solid var(--caju-black);
                outline-offset: 2px;
                box-shadow: none;
            }}

            .stButton > button:disabled,
            .stDownloadButton > button:disabled,
            .stFormSubmitButton > button:disabled {{
                color: rgba(249, 211, 52, 0.62) !important;
                background: rgba(17, 17, 17, 0.72) !important;
                border-color: var(--caju-black) !important;
                opacity: 1;
            }}

            .stButton > button p,
            .stButton > button span,
            .stDownloadButton > button p,
            .stDownloadButton > button span,
            .stFormSubmitButton > button p,
            .stFormSubmitButton > button span {{
                color: var(--caju-yellow) !important;
            }}

            [data-testid="stAlert"] {{
                color: var(--caju-black);
                background: var(--caju-yellow);
                border: 2px solid var(--caju-black);
                border-radius: 12px;
            }}

            [data-testid="stTabs"] [data-baseweb="tab-list"] {{
                gap: 0.4rem;
                padding: 0.3rem;
                background: var(--caju-yellow);
                border: 2px solid var(--caju-black);
                border-radius: 12px;
            }}

            [data-testid="stTabs"] button[data-baseweb="tab"] {{
                min-height: 2.8rem;
                padding: 0.55rem 1.2rem;
                color: var(--caju-black) !important;
                background: var(--caju-yellow) !important;
                border: 0 !important;
                border-radius: 8px !important;
                font-weight: 800;
            }}

            [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {{
                color: var(--caju-yellow) !important;
                background: var(--caju-black) !important;
            }}

            [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] p,
            [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] span {{
                color: var(--caju-yellow) !important;
            }}

            [data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
                display: none;
            }}

            [data-testid="stTextInput"] div[data-baseweb="input"],
            [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
            [data-testid="stTextArea"] textarea {{
                background: var(--caju-yellow) !important;
                border: 2px solid var(--caju-black) !important;
                border-radius: 11px !important;
                box-shadow: none !important;
                overflow: hidden;
            }}

            [data-testid="stNumberInput"] div[data-baseweb="input"] {{
                background: var(--caju-yellow) !important;
                border: 0 !important;
                border-radius: 11px 0 0 11px !important;
                box-shadow: none !important;
                overflow: visible !important;
            }}

            [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
            [data-testid="stNumberInput"] div[data-baseweb="input"]:focus-within,
            [data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within,
            [data-testid="stTextArea"] textarea:focus {{
                outline: 2px solid var(--caju-black) !important;
                outline-offset: 2px;
            }}

            [data-testid="stTextInput"] input,
            [data-testid="stNumberInput"] input {{
                color: var(--caju-black) !important;
                background: transparent !important;
                font-weight: 600;
            }}

            [data-testid="stNumberInput"] input {{
                min-height: 3rem;
                box-sizing: border-box;
                background: var(--caju-yellow) !important;
                border: 2px solid var(--caju-black) !important;
                border-radius: 11px 0 0 11px !important;
                outline: 0 !important;
            }}

            [data-testid="stNumberInput"] input:focus {{
                border-color: var(--caju-black) !important;
                outline: 2px solid var(--caju-black) !important;
                outline-offset: 2px;
            }}

            [data-testid="stTextInput"] input::placeholder {{
                color: rgba(17, 17, 17, 0.52) !important;
            }}

            [data-testid="stFileUploaderDropzone"] {{
                color: var(--caju-black) !important;
                background: var(--caju-yellow) !important;
                border: 2px dashed var(--caju-black) !important;
                border-radius: 12px !important;
            }}

            [data-testid="stFileUploaderDropzone"] small,
            [data-testid="stFileUploaderDropzone"] span {{
                color: var(--caju-black) !important;
            }}

            [data-testid="stNumberInput"] button {{
                min-width: 2.5rem;
                min-height: 3rem;
                color: var(--caju-yellow) !important;
                background: var(--caju-black) !important;
                border: 0 !important;
                border-radius: 0 !important;
            }}

            [data-testid="stNumberInput"] button:last-child {{
                border-radius: 0 11px 11px 0 !important;
            }}

            [data-testid="stNumberInput"] button:hover {{
                color: var(--caju-yellow) !important;
                background: #242424 !important;
            }}

            [data-testid="stNumberInput"] button svg {{
                fill: var(--caju-yellow) !important;
            }}

            [data-testid="stForm"] {{
                padding: 1.65rem;
                border: 2px solid var(--caju-black);
                border-radius: 16px;
                box-shadow: none;
            }}

            .st-key-material_form_panel,
            .st-key-ingredient_edit_form_panel {{
                padding: 1.65rem;
                border: 2px solid var(--caju-black) !important;
                border-radius: 16px !important;
                background: var(--caju-yellow) !important;
                box-shadow: none !important;
            }}

            [class*="st-key-recipe_form_panel_"] {{
                padding: 1.65rem;
                border: 2px solid var(--caju-black) !important;
                border-radius: 16px !important;
                background: var(--caju-yellow) !important;
                box-shadow: none !important;
            }}

            [class*="st-key-recipe_item_"] {{
                padding: 1rem;
                border: 2px solid var(--caju-black) !important;
                border-radius: 12px !important;
                background: var(--caju-yellow) !important;
                box-shadow: none !important;
            }}

            .form-section-title {{
                margin: 0 0 0.25rem;
                font-size: 0.78rem;
                font-weight: 900;
                letter-spacing: 0.12em;
                text-transform: uppercase;
            }}

            .cost-summary {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 1rem;
                margin: 0.8rem 0 1.2rem;
                padding: 1rem 1.15rem;
                border: 2px solid var(--caju-black);
                border-radius: 12px;
            }}

            .cost-summary-label {{
                margin: 0;
                font-size: 0.9rem;
                font-weight: 700;
            }}

            .cost-summary-value {{
                margin: 0;
                font-size: clamp(1.35rem, 2.4vw, 2rem);
                font-weight: 900;
                letter-spacing: -0.025em;
                white-space: nowrap;
            }}

            p, label, h1, h2, h3, h4, span {{ color: var(--caju-black); }}

            @media (max-width: 768px) {{
                .page-title {{ font-size: 2rem; }}
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )
