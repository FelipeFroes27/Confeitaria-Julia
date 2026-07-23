# Padrão visual — Caju

Este é o padrão obrigatório para todas as telas do aplicativo.

## Identidade

- Fundo integral amarelo `#F9D334`, igual ao fundo do logo.
- Textos, ícones e contornos em preto `#111111`.
- Logo no canto superior direito do cabeçalho e no topo do menu lateral.
- Menu lateral amarelo, separado do conteúdo por uma única linha preta.

## Componentes

- Cada componente deve ter apenas uma borda preta.
- Não usar sombras deslocadas ou efeitos que pareçam bordas duplicadas.
- Campos de texto, seleção, cartões e formulários usam cantos arredondados.
- Campos numéricos formatados são entradas de texto com conversão para o padrão brasileiro.
- Botões que executam ações usam fundo preto e texto amarelo.
- Links do menu permanecem amarelos, com borda preta e indicação discreta da tela ativa.

## Formulários

- Agrupar campos relacionados em seções com títulos em caixa alta.
- Usar um único painel externo com borda preta.
- Exibir cálculos automáticos em um quadro interno com uma única borda.
- Valores monetários usam vírgula decimal e prefixo `R$`.
- Mudanças que afetam cálculos devem atualizar o resultado imediatamente.

## Implementação

- Os estilos compartilhados ficam em `ui/layout.py`.
- Novas páginas devem chamar `configure_page`, `render_sidebar` e `render_page_header`.
- Regras visuais devem ser específicas ao componente; evitar seletores genéricos de contêineres internos do Streamlit.
