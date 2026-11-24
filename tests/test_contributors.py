def test_cria_contribuidor_e_token_funciona(client):
    response = client.post("/contributors", json={"username": "maria"})
    assert response.status_code == 201
    token = response.json()["token"]

    response = client.get("/contributors/me", headers={"X-API-Key": token})
    assert response.json() == {"username": "maria", "changes_need_votes": True}

    response = client.post("/products", json={"name": "Produto", "reason": "teste"}, headers={"X-API-Key": token})
    assert response.status_code == 202


def test_nome_repetido_e_recusado(client):
    client.post("/contributors", json={"username": "maria"})
    assert client.post("/contributors", json={"username": "maria"}).status_code == 400


def test_nome_invalido_e_recusado(client):
    assert client.post("/contributors", json={"username": "a b"}).status_code == 400


def test_api_nao_mostra_reputacao(client, auth):
    client.post("/products", json={"name": "Produto", "reason": "teste"}, headers=auth)
    api_description = client.get("/openapi.json").text
    assert "reputation" not in api_description
    assert "ranking" not in api_description


def test_limite_de_contribuidores_novos_por_hora(client):
    statuses = [client.post("/contributors", json={"username": f"user{number}"}).status_code for number in range(7)]
    assert statuses.count(429) == 2


def test_download_da_base_publica(client):
    response = client.get("/download/prodbr.sqlite3")
    assert response.status_code == 200
    assert response.content.startswith(b"SQLite format 3")


def test_limite_separa_pessoas_atras_do_cloudflare(client):
    same_cloudflare_ip = {"x-real-ip": "172.70.0.1"}
    for number in range(5):
        client.post("/contributors", json={"username": f"a{number}xx"}, headers={**same_cloudflare_ip, "cf-connecting-ip": "200.1.1.1"})
    other_person = client.post("/contributors", json={"username": "outra_pessoa"}, headers={**same_cloudflare_ip, "cf-connecting-ip": "200.2.2.2"})
    assert other_person.status_code == 201
