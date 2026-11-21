from util.packaging import read_package_text


def test_formatos_que_da_para_entender():
    assert read_package_text("15 kg") == {"net_quantity": 15.0, "net_unit": "kg"}
    assert read_package_text("10,1kg") == {"net_quantity": 10.1, "net_unit": "kg"}
    assert read_package_text("6x350ml") == {"units_per_pack": 6, "net_quantity": 350.0, "net_unit": "ml"}
    assert read_package_text("2 Litros") == {"net_quantity": 2.0, "net_unit": "l"}
    assert read_package_text("Cx c/ 12 un") == {"units_per_pack": 12, "net_quantity": 12.0, "net_unit": "un"}
    assert read_package_text("500 g c/ 10 un") == {"net_quantity": 500.0, "net_unit": "g", "units_per_pack": 10}


def test_na_duvida_fica_vazio():
    assert read_package_text("1.000 g") == {}
    assert read_package_text("6x350ml + 1 l") == {}
    assert read_package_text("1 kg ou 2 kg") == {}
    assert read_package_text("embalagem grande") == {}
    assert read_package_text("") == {}
