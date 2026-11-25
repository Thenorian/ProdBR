"""Tabela do IBPT: importação conferida linha a linha e consulta por NCM e UF."""
import json
from pathlib import Path

import pytest

from database.ibpt import IbptDB
from util import ibpt_data

SMALL_SP_TABLE = Path(__file__).resolve().parent / "files" / "ibpt_sp_pequena.json"


@pytest.fixture
def sp_table(monkeypatch):
    """A tabela pequena de SP no lugar do download: os testes nunca acessam a internet."""
    content = json.loads(SMALL_SP_TABLE.read_text(encoding="utf-8"))
    monkeypatch.setattr(ibpt_data, "download_state_table", lambda uf: content)
    return content


def test_linhas_fora_do_formato_sao_ignoradas(sp_table):
    version, rows = ibpt_data.read_state_table(sp_table, "SP")
    assert version == sp_table["versao"]
    # 22030000 vem duas vezes: sem exceção e com a exceção da TIPI.
    assert sorted((row["code"], row["ex"]) for row in rows)[0] == ("00000000", "")
    assert len(rows) == 3


def test_tabela_de_outra_uf_e_recusada(sp_table):
    with pytest.raises(ValueError):
        ibpt_data.read_state_table(sp_table, "MG")


def test_importa_uma_vez_so_por_versao(sp_table):
    ok, message = ibpt_data.update_state("SP")
    assert ok and "3 linhas" in message

    ok, message = ibpt_data.update_state("SP")
    assert ok and "sem novidade" in message


def test_versao_nova_troca_a_tabela_inteira_da_uf(sp_table):
    ibpt_data.update_state("SP")
    sp_table["versao"] = "99.9.Z"
    sp_table["ncm"] = [item for item in sp_table["ncm"] if item["codigo"] == "00000000"]

    ok, message = ibpt_data.update_state("SP")
    assert ok and "99.9.Z, 1 linhas" in message
    ok, versions = IbptDB().list_versions()
    assert versions == [{"uf": "SP", "version": "99.9.Z", "total": 1, "valid_until": versions[0]["valid_until"]}]


def test_consulta_por_ncm_e_uf(client, sp_table):
    ibpt_data.update_state("SP")

    response = client.get("/ibpt/2203.00.00", params={"uf": "sp"})
    assert response.status_code == 200
    rate = response.json()["items"][0]
    assert rate["code"] == "22030000"
    assert rate["uf"] == "SP"
    assert rate["state_rate"] >= 0

    assert client.get("/ibpt/22030000", params={"uf": "MG"}).status_code == 404
    assert client.get("/ibpt/22030000", params={"uf": "XX"}).status_code == 400


def test_produto_traz_o_ibpt_quando_vem_a_uf(client, auth, sp_table):
    ibpt_data.update_state("SP")
    product = client.post("/products", json={"name": "Cerveja", "ncm": "22030000", "reason": "teste"}, headers=auth).json()

    with_uf = client.get(f"/products/{product['id']}", params={"uf": "SP"}).json()
    assert with_uf["ibpt"]["code"] == "22030000"
    assert client.get(f"/products/{product['id']}").json()["ibpt"] is None


def test_download_da_base_nao_leva_o_ibpt(client, sp_table, tmp_path):
    import sqlite3

    ibpt_data.update_state("SP")
    download_file = tmp_path / "prodbr.sqlite3"
    download_file.write_bytes(client.get("/download/prodbr.sqlite3").content)

    with sqlite3.connect(download_file) as downloaded:
        assert downloaded.execute("SELECT COUNT(*) FROM ibpt_rates").fetchone()[0] == 0
    ok, versions = IbptDB().list_versions()
    assert versions[0]["total"] == 3
