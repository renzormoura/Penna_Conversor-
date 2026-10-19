"""Design system do Penna — paleta de cores e constantes visuais.

Único lugar onde as cores, fontes e textos da UI são definidos.
Todos os outros módulos de UI importam daqui.

Paleta:
    Branco como cor estrutural principal e azul #2e75c4 (extraído do ícone)
    como cor de destaque. Complementado por tons Slate do Tailwind CSS.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Azuis (acento oficial da marca)
# ---------------------------------------------------------------------------
COR_AZUL_PRINCIPAL = "#2e75c4"    # Azul oficial extraído do ícone (RGB: 46, 117, 196)
COR_AZUL_HOVER     = "#2462a6"    # Azul mais escuro no hover
COR_AZUL_ACTIVE    = "#1b528c"    # Azul pressionado
COR_AZUL_TINT      = "#eff6fc"    # Azul ultra-suave para fundos e badges
COR_AZUL_BORDA     = "#cfe2f7"    # Borda sutil de destaque
COR_AZUL_DASH      = "#9ec1ea"    # Borda tracejada da área de arraste

# ---------------------------------------------------------------------------
# Estruturais
# ---------------------------------------------------------------------------
COR_BRANCO = "#ffffff"            # Cor estrutural principal
COR_FUNDO  = "#f8fafc"            # Fundo da janela (Slate 50)
COR_CARD   = "#ffffff"            # Painel central em branco puro
COR_BORDA  = "#e2e8f0"            # Borda sutil (Slate 200)

# ---------------------------------------------------------------------------
# Tipografia
# ---------------------------------------------------------------------------
COR_TEXTO_TITULO = "#0f172a"      # Títulos (Slate 900)
COR_TEXTO_CORPO  = "#334155"      # Corpo e labels (Slate 700)
COR_TEXTO_MEDIO  = "#64748b"      # Secundários e legendas (Slate 500)
COR_TEXTO_HINT   = "#94a3b8"      # Dicas e notas (Slate 400)

# ---------------------------------------------------------------------------
# Semânticas
# ---------------------------------------------------------------------------
COR_SUCESSO       = "#059669"     # Verde confirmação
COR_SUCESSO_BG    = "#f0fdf4"     # Fundo verde suave
COR_SUCESSO_BORDA = "#86efac"     # Borda verde suave
COR_ERRO          = "#dc2626"     # Vermelho erro
COR_ERRO_BG       = "#fef2f2"     # Fundo vermelho suave

# ---------------------------------------------------------------------------
# Aliases de retrocompatibilidade (nomes antigos usados em código externo)
# ---------------------------------------------------------------------------
COR_HEADER_TOPO  = COR_BRANCO
COR_HEADER_BASE  = COR_BRANCO
COR_BORDA_CARD   = COR_BORDA
COR_TEXTO_ESCURO = COR_TEXTO_TITULO
COR_ACENTO       = COR_AZUL_PRINCIPAL
COR_ACENTO_HOVER = COR_AZUL_HOVER

# ---------------------------------------------------------------------------
# Textos de UI
# ---------------------------------------------------------------------------
WINDOW_TITLE = "Penna - Gerador de Arquivo Fiscal"
DROP_HINT    = "SOLTE O ARQUIVO EXCEL AQUI"
APP_BRAND    = "Penna"
APP_SUBTITLE = "Gerador e Validador de Arquivo Fiscal • SUS"

MSG_BLOQUEIO = (
    "A geração foi bloqueada pelo controle de consistência. "
    "Corrija os {n_err} erro(s) listados na tela e execute novamente. "
    "O arquivo TXT só é gerado quando a planilha passa sem erros "
    "(idêntico ao sistema antigo APAC-MAG)."
)
MSG_AVISOS = (
    "Planilha aceita com {n_avs} aviso(s) de inconsistência (AVS). "
    "Avisos NÃO bloqueiam a geração, igual ao sistema antigo, mas confira "
    "os itens listados antes de enviar o arquivo."
)
