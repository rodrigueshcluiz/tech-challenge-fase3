"""Coleta das verificações de cada etapa e decisão de aprovar ou reprovar."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


class Relatorio:
    def __init__(self) -> None:
        self.linhas: list[tuple[str, str, str, str]] = []
        self.falhas: list[str] = []
        self.etapa_atual = ""

    def etapa(self, nome: str) -> None:
        self.etapa_atual = nome
        print(f"\n{'=' * 78}\n{nome}\n{'=' * 78}", flush=True)

    def info(self, texto: str) -> None:
        self.linhas.append((self.etapa_atual, "INFO", texto, ""))
        print(f"  {texto}", flush=True)

    def check(self, nome: str, ok, detalhe: str = "", bloqueante: bool = True) -> bool:
        ok = bool(ok)
        marca = "OK" if ok else ("FALHA" if bloqueante else "AVISO")
        if not ok and bloqueante:
            self.falhas.append(f"[{self.etapa_atual}] {nome}: {detalhe}")
        self.linhas.append((self.etapa_atual, marca, nome, detalhe))
        print(f"  [{marca:5s}] {nome}" + (f" — {detalhe}" if detalhe else ""), flush=True)
        return ok

    def contagem(self) -> dict[str, int]:
        return {m: sum(1 for _, x, _, _ in self.linhas if x == m)
                for m in ("OK", "AVISO", "FALHA")}

    def markdown(self, run_id: str, fontes: Path) -> str:
        agora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        c = self.contagem()
        cab = [
            "# Relatório de verificação — camada Gold (fontes oficiais INEP)", "",
            f"- Execução: `{run_id}`", f"- Data: {agora}", f"- Fontes: `{fontes}`",
            f"- Resultado: **{c['FALHA']} falhas**, {c['AVISO']} avisos, "
            f"{c['OK']} verificações aprovadas", "",
        ]
        corpo, anterior = [], None
        for etapa, marca, nome, detalhe in self.linhas:
            if etapa != anterior:
                corpo += ["", f"## {etapa}", "", "| | Verificação | Detalhe |", "|---|---|---|"]
                anterior = etapa
            corpo.append(f"| {'' if marca == 'INFO' else marca} | {nome} | {detalhe} |")
        return "\n".join(cab + corpo) + "\n"
