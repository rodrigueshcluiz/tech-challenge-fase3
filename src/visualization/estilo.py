"""Tokens visuais e helpers de gráfico.

Paleta categórica validada: usamos apenas os três primeiros slots, que são os
que passam em todos os pares de cores (inclusive para daltonismo) em modo claro
e escuro. Acima de três séries, a leitura deixa de ser segura — nesse caso o
caminho é facetar, não acrescentar cor.

Regras aplicadas em todos os gráficos: um eixo só, marcas finas, grade
recessiva, rótulos diretos em vez de número em cada ponto, e texto sempre em
tinta neutra — a cor pertence à marca, não ao texto.
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
TINTA_3 = "#8a8983"
GRADE = "#e6e5e1"

SERIE = ["#2a78d6", "#eb6834", "#1baf7a"]      # azul, laranja, água
AZUL_CLARO, AZUL_ESCURO = "#9ec5f4", "#184f95"  # rampa sequencial


def aplicar_estilo() -> None:
    mpl.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "savefig.bbox": "tight", "savefig.dpi": 160,
        "font.size": 10, "font.family": "sans-serif",
        "text.color": TINTA, "axes.labelcolor": TINTA_2,
        "xtick.color": TINTA_2, "ytick.color": TINTA_2,
        "axes.titlesize": 12.5, "axes.titleweight": "semibold",
        "axes.titlecolor": TINTA, "axes.titlelocation": "left", "axes.titlepad": 14,
        "axes.edgecolor": GRADE, "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "grid.color": GRADE, "grid.linewidth": 0.8,
        "xtick.major.size": 0, "ytick.major.size": 0,
        "legend.frameon": False, "legend.fontsize": 9.5,
        "lines.linewidth": 2, "lines.markersize": 8,
    })


def titular(ax, titulo: str, subtitulo: str = "") -> None:
    """Título curto acima, contexto em tinta secundária logo abaixo.

    O padding do título cresce quando há subtítulo, senão os dois colidem.
    """
    ax.set_title(titulo, pad=30 if subtitulo else 12)
    if subtitulo:
        ax.text(0, 1.015, subtitulo, transform=ax.transAxes, fontsize=9.5,
                color=TINTA_2, va="bottom")


def num(valor: float, casas: int = 1, sinal: bool = False) -> str:
    """Número no padrão brasileiro: vírgula decimal."""
    texto = f"{valor:+.{casas}f}" if sinal else f"{valor:.{casas}f}"
    return texto.replace(".", ",")


def milhar(valor: int) -> str:
    """Inteiro no padrão brasileiro: ponto como separador de milhar."""
    return f"{valor:,}".replace(",", ".")


def pct(fracao: float, casas: int = 1) -> str:
    """Fração como percentual no padrão brasileiro: 0.625 -> '62,5%'."""
    return f"{fracao * 100:.{casas}f}".replace(".", ",") + "%"


def eixo_decimal(ax, casas: int = 1, eixo: str = "x") -> None:
    """Vírgula decimal nos rótulos do eixo, para não destoar dos rótulos diretos."""
    from matplotlib.ticker import FuncFormatter
    alvo = ax.xaxis if eixo == "x" else ax.yaxis
    alvo.set_major_formatter(FuncFormatter(lambda v, _: num(v, casas)))


def salvar(fig, destino, nome: str) -> str:
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"{nome}.png"
    fig.savefig(caminho)
    plt.close(fig)
    return caminho.name
