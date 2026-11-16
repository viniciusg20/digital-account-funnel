"""Executa sql/duckdb/01 + sql/02..08 sobre os Parquet locais e exporta as tabelas."""
from __future__ import annotations

import logging

import duckdb

from .config import CPA_AFILIADO, GA4, MARGEM_SOBRE_DEPOSITO, MIDIA, MMP, OUT, SAMPLE, SQL

log = logging.getLogger(__name__)
TABELAS = ["sessoes", "funil_sessao", "funil_etapas", "erros_formulario", "jornadas", "atribuicao_regras",
           "caminhos", "coortes", "eficiencia_canal", "eficiencia_campanha", "qa_tracking", "app_por_midia",
           "reconciliacao_mmp"]


def _p(x) -> str:
    return str(x).replace("\\", "/")


def conectar(amostra: bool = False) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    origem = SAMPLE if amostra else GA4
    con.execute(f"CREATE VIEW events AS SELECT * FROM read_parquet('{_p(origem)}/events_*.parquet')")
    con.execute(f"CREATE VIEW backend AS SELECT * FROM '{_p(MIDIA.parent)}/backend_contas.parquet'")
    con.execute(f"CREATE VIEW midia AS SELECT * FROM '{_p(MIDIA)}/custo_midia_diario.parquet'")
    con.execute(f"CREATE VIEW installs AS SELECT * FROM '{_p(MMP)}/installs.parquet'")
    con.execute(f"CREATE VIEW in_app_events AS SELECT * FROM '{_p(MMP)}/in_app_events.parquet'")
    con.execute("CREATE TABLE params AS SELECT ?::DOUBLE AS cpa_afiliado, ?::DOUBLE AS margem",
                [CPA_AFILIADO, MARGEM_SOBRE_DEPOSITO])
    return con


def rodar(con: duckdb.DuckDBPyConnection | None = None) -> duckdb.DuckDBPyConnection:
    con = con or conectar()
    arquivos = [SQL / "duckdb" / "01_stg_events.sql", *sorted(SQL.glob("0[2-9]_*.sql"))]
    for arq in arquivos:
        log.info("executando %s", arq.name)
        con.execute(arq.read_text(encoding="utf-8"))
    for t in TABELAS:
        con.execute(f"COPY {t} TO '{_p(OUT)}/{t}.parquet' (FORMAT PARQUET)")
    log.info("tabelas exportadas para data/processed/")
    return con
