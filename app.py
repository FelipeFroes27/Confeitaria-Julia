from pathlib import Path
import runpy

import streamlit as st


try:
    runpy.run_path(
        str(Path(__file__).with_name("application.py")),
        run_name="__main__",
    )
except Exception as error:
    st.error(
        "A aplicação encontrou um problema durante a inicialização, "
        "mas o processo permaneceu ativo."
    )
    st.exception(error)
