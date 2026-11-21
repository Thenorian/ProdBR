"""Rotas antigas usadas pelo OS-Mechanical e pelo Simple ERP antes da /api/v1. Não podem quebrar."""
import pytest
from fastapi.testclient import TestClient

from server import app as server_app

BARCODE = "7891000100103"


@pytest.fixture
def server():
    return TestClient(server_app)


@pytest.fixture
def old_auth(server):
    token = server.post("/api/v1/contributors", json={"username": "os_mechanical"}).json()["token"]
    return {"X-API-Key": token}


def test_fluxo_do_os_mechanical(server, old_auth, ncm_table):
    created = server.post("/products", json={
        "name": "Óleo 5W30 1L", "ncm": "22030000", "brand": "Marca", "commercial_unit": "UN",
        "source": "OS-Mechanical", "reason": "Cadastro pela oficina",
    }, headers=old_auth)
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]

    identifier = server.post("/identifiers", json={
        "product_id": product_id, "type": "gtin13", "value": BARCODE, "reason": "Código da embalagem",
        "description": "Caixa c/ 12 un",
    }, headers=old_auth)
    assert identifier.status_code == 201, identifier.text

    found = server.get("/products", params={"identifier": BARCODE, "limit": 1}).json()["items"][0]
    assert found["id"] == product_id
    assert found["ncm"] == "22030000"
    assert found["identifiers"][0]["value"] == BARCODE
    assert found["identifiers"][0]["units_per_pack"] == 12


def test_codigo_do_fabricante_pela_rota_antiga(server, old_auth):
    product_id = server.post("/products", json={"name": "Vela", "reason": "teste"}, headers=old_auth).json()["id"]
    server.post("/identifiers", json={"product_id": product_id, "type": "manufacturer_code", "value": "BPR6ES",
                                      "reason": "teste"}, headers=old_auth)
    assert server.get("/products", params={"identifier": "BPR6ES"}).json()["items"][0]["id"] == product_id


def test_completar_campos_pela_rota_antiga(server, old_auth):
    product_id = server.post("/products", json={"name": "Produto", "reason": "teste"}, headers=old_auth).json()["id"]
    response = server.put(f"/products/{product_id}", json={"brand": "Nova", "reason": "Completa"}, headers=old_auth)
    assert response.json()["brand"] == "Nova"


def test_ncm_pela_rota_antiga(server, ncm_table):
    assert server.get("/ncm/22030000").status_code == 200
    assert server.get("/ncm/82055000").status_code == 404


def test_rota_antiga_exige_token_para_escrever(server):
    assert server.post("/products", json={"name": "X", "reason": "teste"}).status_code == 401
