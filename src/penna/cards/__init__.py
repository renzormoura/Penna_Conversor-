"""Fichas do paciente em PDF, renderizadas a partir do próprio modelo ``.xlsx``.

A ficha segue o arquivo modelo (``dados/modelo_ficha_oci_oftalmologia.xlsx``,
aba ``OCI OFTALMOLOGIA``): mesmas linhas, mesclagens, larguras, bordas, fontes
e cores. Cada linha da planilha vira uma ficha; colunas sem campo no formulário
vão para a página final "OUTROS DADOS DA LINHA", para nada se perder.

Camadas (testáveis sem PDF até ``content``):

- :mod:`.template`: leitura do modelo (geometria, estilos, listas);
- :mod:`.content`: ``montar_ficha``, puro, ``row -> sobrescritas de célula + extras``;
- :mod:`.page`, :mod:`.extras`, :mod:`.pdf_text`: desenho em reportlab;
- :mod:`.render`: ``gerar_ficha_pdf`` e ``exportar_fichas``.

Sem ``reportlab`` o pacote segue importável e a geração falha com mensagem
clara: o resto do programa (TXT) nunca é afetado.
"""
from .content import montar_ficha
from .files import nome_arquivo_ficha
from .render import exportar_fichas, gerar_ficha_pdf
from .template import carregar_modelo
from .text import formatar_procedimento

__all__ = [
    "carregar_modelo",
    "exportar_fichas",
    "formatar_procedimento",
    "gerar_ficha_pdf",
    "montar_ficha",
    "nome_arquivo_ficha",
]
