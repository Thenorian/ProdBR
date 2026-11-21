from tests.conftest import SMALL_NCM_TABLE, public_database
from util.data_util import DataUtil


def test_le_a_tabela_e_monta_a_arvore():
    ok, table = DataUtil().read_ncm_file(SMALL_NCM_TABLE)
    assert ok
    codes = {ncm["code"]: ncm for ncm in table["codes"]}

    assert codes["82075011"]["parent_code"] == "820750"
    assert codes["82075011"]["description"] == "Helicoidais, de diâmetro inferior ou igual a 52 mm"
    assert codes["820750"]["description"] == "Ferramentas de furar"
    assert codes["22030000"]["full_description"] == "Bebidas, líquidos alcoólicos e vinagres > Cervejas de malte"


def test_recusa_arquivo_com_codigo_fora_do_padrao(tmp_path):
    broken_file = tmp_path / "quebrado.json"
    broken_file.write_text('{"Nomenclaturas": [{"Codigo": "12.3", "Descricao": "x"}]}', encoding="utf-8")

    ok, error = DataUtil().read_ncm_file(broken_file)
    assert not ok
    assert "fora do padrão" in error


def test_reimportar_marca_o_que_saiu_da_tabela(ncm_table, tmp_path):
    smaller_table = tmp_path / "menor.json"
    smaller_table.write_text(SMALL_NCM_TABLE.read_text(encoding="utf-8").replace('"Codigo":"2203.00.00"', '"Codigo":"2204.00.00"'), encoding="utf-8")

    ok, summary = DataUtil().import_ncm_file(smaller_table)
    assert ok, summary
    assert summary["no_longer_in_force"] == 1

    ok, beer = public_database().select("ncm", where={"code": "22030000"}, fetch="one")
    assert beer["in_force"] == 0
