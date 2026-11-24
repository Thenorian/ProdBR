"""Fila de votação: Iniciante não grava direto, a comunidade decide com votos."""
import sqlite3

from database.contributor import ContributorDB
from database.database import Database
from database.setup import COMMUNITY_SCHEMA
from tests.conftest import TEST_FOLDER, create_contributor

NEW_PRODUCT = {"name": "Café Torrado 500g", "brand": "Marca Boa", "reason": "Produto novo"}


def voters(client, count, moderator=False):
    return [
        {"X-API-Key": create_contributor(client, f"votante{number}", moderator=moderator)}
        for number in range(count)
    ]


def send_new_product(client, beginner_auth):
    response = client.post("/products", json=NEW_PRODUCT, headers=beginner_auth)
    assert response.status_code == 202, response.text
    return response.json()["pending_change"]


def vote(client, pending_change_id, value, auth):
    return client.post(f"/pending-changes/{pending_change_id}/votes", json={"vote": value}, headers=auth)


def reputation_of(username):
    ok, contributor = ContributorDB().get_by_username(username)
    return contributor["reputation"]


def test_iniciante_vai_para_a_fila_e_nada_e_gravado(client, beginner_auth):
    pending_change = send_new_product(client, beginner_auth)

    assert pending_change["status"] == "pending"
    assert pending_change["action"] == "create_product"
    assert pending_change["contributor"] == "iniciante"
    assert pending_change["payload"] == {"name": "Café Torrado 500g", "brand": "Marca Boa"}
    assert client.get("/products", params={"q": "Café"}).json()["total"] == 0

    queue = client.get("/pending-changes").json()
    assert [item["id"] for item in queue["items"]] == [pending_change["id"]]


def test_tres_votos_a_favor_aplicam_em_nome_do_autor(client, beginner_auth):
    pending_change = send_new_product(client, beginner_auth)

    for voter_auth in voters(client, 3):
        response = vote(client, pending_change["id"], 1, voter_auth)
        assert response.status_code == 200

    assert response.json()["status"] == "approved"
    product = client.get("/products", params={"q": "Café"}).json()["items"][0]
    history = client.get(f"/products/{product['id']}/revisions").json()["items"]
    assert {revision["contributor"] for revision in history} == {"iniciante"}
    # 3 votos a favor + 2 campos aplicados (name e brand)
    assert reputation_of("iniciante") == 5


def test_tres_votos_contra_descartam(client, beginner_auth):
    pending_change = send_new_product(client, beginner_auth)

    for voter_auth in voters(client, 3):
        response = vote(client, pending_change["id"], -1, voter_auth)

    assert response.json()["status"] == "rejected"
    assert client.get("/products", params={"q": "Café"}).json()["total"] == 0
    assert reputation_of("iniciante") == -3


def test_trocar_e_retirar_voto_nao_conta_duas_vezes(client, beginner_auth):
    pending_change = send_new_product(client, beginner_auth)
    voter_auth = voters(client, 1)[0]

    assert vote(client, pending_change["id"], 1, voter_auth).json()["score"] == 1
    assert vote(client, pending_change["id"], 1, voter_auth).json()["score"] == 1
    assert vote(client, pending_change["id"], -1, voter_auth).json()["score"] == -1
    assert vote(client, pending_change["id"], 0, voter_auth).json()["score"] == 0
    assert reputation_of("iniciante") == 0


def test_autor_nao_vota_na_propria_alteracao(client, beginner_auth):
    pending_change = send_new_product(client, beginner_auth)
    assert vote(client, pending_change["id"], 1, beginner_auth).status_code == 403


def test_conta_com_menos_de_24_horas_nao_vota(client, beginner_auth):
    pending_change = send_new_product(client, beginner_auth)
    new_account = {"X-API-Key": create_contributor(client, "conta_nova", hours_ago=1)}
    assert vote(client, pending_change["id"], 1, new_account).status_code == 403


def test_moderador_decide_sozinho(client, beginner_auth):
    pending_change = send_new_product(client, beginner_auth)
    moderator = voters(client, 1, moderator=True)[0]

    response = vote(client, pending_change["id"], 1, moderator)
    assert response.json()["status"] == "approved"
    assert client.get("/products", params={"q": "Café"}).json()["total"] == 1


def test_alteracao_decidida_nao_recebe_mais_voto(client, beginner_auth):
    pending_change = send_new_product(client, beginner_auth)
    moderator, other = voters(client, 2, moderator=True)
    vote(client, pending_change["id"], -1, moderator)
    assert vote(client, pending_change["id"], 1, other).status_code == 409


def test_edicao_de_produto_que_nao_existe_nem_entra_na_fila(client, beginner_auth):
    response = client.put("/products/nao-existe", json={"brand": "X", "reason": "teste"}, headers=beginner_auth)
    assert response.status_code == 404
    assert client.get("/pending-changes").json()["total"] == 0


def test_dado_invalido_e_recusado_antes_da_fila(client, beginner_auth):
    response = client.post("/products", json={"name": "X", "ncm": "123", "reason": "teste"}, headers=beginner_auth)
    assert response.status_code == 400
    assert client.get("/pending-changes").json()["total"] == 0


def test_categoria_nao_e_criada_enquanto_espera_votos(client, beginner_auth):
    product = {**NEW_PRODUCT, "category": "Bebidas > Cafés"}
    assert client.post("/products", json=product, headers=beginner_auth).status_code == 202
    assert client.get("/categories").json()["items"] == []


def test_aprovada_mas_impossivel_de_aplicar_fica_como_falha(client, auth, beginner_auth):
    category = client.post("/categories", json={"path": "Limpeza", "reason": "teste"}, headers=auth).json()
    response = client.put(
        f"/categories/{category['id']}", json={"name": "Limpeza Geral", "reason": "nome melhor"}, headers=beginner_auth
    )
    pending_change = response.json()["pending_change"]

    client.request("DELETE", f"/categories/{category['id']}", json={"reason": "duplicada"}, headers=auth)
    moderator = voters(client, 1, moderator=True)[0]

    response = vote(client, pending_change["id"], 1, moderator)
    assert response.json()["status"] == "failed"
    assert response.json()["result_message"] == "Categoria não encontrada."


def test_editor_grava_direto(client, beginner_auth):
    ContributorDB().update("contributors", {"reputation": 50}, where={"username": "iniciante"})
    assert client.post("/products", json=NEW_PRODUCT, headers=beginner_auth).status_code == 201


def test_confiavel_grava_direto(client, auth):
    assert client.post("/products", json=NEW_PRODUCT, headers=auth).status_code == 201


def test_regra_fiscal_de_iniciante_vai_para_a_fila(client, beginner_auth):
    rule = {"ncm": "09012100", "valid_from": "2026-01-01", "source": "TIPI", "ipi_rate": 0, "reason": "teste"}
    response = client.post("/fiscal-rules", json=rule, headers=beginner_auth)
    assert response.status_code == 202
    assert response.json()["pending_change"]["action"] == "create_fiscal_rule"


def test_quem_ja_existia_continua_gravando_direto_depois_da_migracao():
    """Banco da comunidade de antes da votação: ao ganhar a coluna trusted, todos viram confiáveis."""
    old_database_path = TEST_FOLDER / "comunidade_antiga.sqlite3"
    old_database_path.unlink(missing_ok=True)
    with sqlite3.connect(old_database_path) as connection:
        connection.execute(
            "CREATE TABLE contributors (id CHAR(36) PRIMARY KEY, username VARCHAR(40) NOT NULL UNIQUE, "
            "reputation INTEGER NOT NULL DEFAULT 0, edit_count INTEGER NOT NULL DEFAULT 0, "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, last_contribution_at DATETIME NULL)"
        )
        connection.execute("INSERT INTO contributors (id, username) VALUES ('1', 'simple_erp')")

    old_database = Database(path=str(old_database_path))
    ok, changes = old_database.migrate(str(COMMUNITY_SCHEMA))
    assert ok, changes
    assert "coluna adicionada: contributors.trusted" in changes

    ok, contributor = old_database.select("contributors", where={"username": "simple_erp"}, fetch="one")
    assert contributor["trusted"] == 1
    assert contributor["moderator"] == 0


def test_conta_importada_da_versao_antiga_tambem_vota(client, beginner_auth):
    pending_change = send_new_product(client, beginner_auth)
    old_account = {"X-API-Key": create_contributor(client, "conta_antiga")}
    ContributorDB().update("contributors", {"created_at": "2026-08-08T15:03:11.123456"}, where={"username": "conta_antiga"})
    assert vote(client, pending_change["id"], 1, old_account).status_code == 200
