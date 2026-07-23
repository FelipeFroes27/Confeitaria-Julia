# Caju — Doces em família

Base de aplicativo em Streamlit com integração ao Google Sheets.

## Como iniciar

1. Crie e ative um ambiente virtual.
2. Instale as dependências: `pip install -r requirements.txt`.
3. Copie `.streamlit/secrets.example.toml` para `.streamlit/secrets.toml`.
4. Reutilize nesse arquivo a conta de serviço dos demais projetos e informe o ID da nova planilha.
5. Compartilhe a planilha com o e-mail da conta de serviço.
6. Execute: `streamlit run app.py`.

As operações de leitura e gravação ficam centralizadas em `services/google_sheets.py`.

O padrão obrigatório para todas as telas está documentado em `DESIGN_SYSTEM.md` e implementado em `ui/layout.py`.
