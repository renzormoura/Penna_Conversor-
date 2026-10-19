# -*- mode: python ; coding: utf-8 -*-
# =====================================================================
# PENNA CONVERSOR — build do executavel standalone
#   pyinstaller Conversor.spec        (ou use build_exe.bat)
#   -> dist/PennaConversor.exe  (onefile, unico arquivo, igual ao original)
#
# Incluido no bundle:
#   - icones (apac_icon.ico / .png / header)
#   - penna_config.json (configuracao do estabelecimento; incluido no
#     bundle so quando presente — o arquivo real nao e versionado)
#   - pacote penna/      (src/penna, resolvido via pathex: core, config, reference,
#     layout, validation, remittance, cards, services e ui)
#   - dados/bases_sia/   (SIGTAP versionado: S_PA, S_PAPA, S_PAHA, S_CID,
#     S_PAREGR, S_DEPARA, XUPSHA) — validador com regras SIGTAP ativas
#   - dados/modelo_ficha_oci_oftalmologia.xlsx (template da ficha PDF)
#
# Apos o build, compile o instalador com:
#   ISCC.exe installer.iss   (ou use build_installer.bat)
# =====================================================================

import os

a = Analysis(
    ['src/penna/__main__.py'],
    pathex=['src', '.'],
    binaries=[],
    datas=[
        # Icones
        ('apac_icon.ico', '.'),
        ('apac_icon.png', '.'),
        ('apac_icon_header.png', '.'),
        ('penna.ico', '.'),
        ('penna.png', '.'),
        ('penna_header.png', '.'),
        # Configuracao do estabelecimento (so quando existe — o arquivo
        # real com dados do prestador nao e versionado; sem ele o app usa
        # os valores de fabrica de penna/config/factory.py)
        ("penna_config.example.json", "."),
        *([("penna_config.json", ".")]
          if os.path.exists(os.path.join(SPECPATH, "penna_config.json"))
          else []),
        # Bases SIGTAP versionadas (validador/remessa)
        ('dados/bases_sia/S_PA.DBF', 'dados/bases_sia'),
        ('dados/bases_sia/S_DEPARA.DBF', 'dados/bases_sia'),
        ('dados/bases_sia/S_PAHA.ZBF', 'dados/bases_sia'),
        ('dados/bases_sia/S_PAPA.ZBF', 'dados/bases_sia'),
        ('dados/bases_sia/S_PAREGR.ZBF', 'dados/bases_sia'),
        ('dados/bases_sia/S_CID.ZBF', 'dados/bases_sia'),
        ('dados/bases_sia/XUPSHA.DBF', 'dados/bases_sia'),
        # Modelo da ficha PDF (template da aba OCI OFTALMOLOGIA)
        ('dados/modelo_ficha_oci_oftalmologia.xlsx', 'dados'),
    ],
    hiddenimports=[
        # O PyInstaller segue os imports do pacote penna (src/penna via pathex);
        # estes garantem os pontos de entrada e os importados tardiamente.
        'penna.ui.main',
        'penna.ui.app',
        'penna.remittance',
        'penna.cards',
        'penna.reference.sigtap',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PennaConversor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='apac_icon.ico',
)
