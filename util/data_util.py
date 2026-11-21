import json
import re
from datetime import datetime
from pathlib import Path

from database.ncm import NcmDB

# A tabela oficial tem uns 3 MB. O limite só evita carregar na memória um arquivo absurdo por engano.
MAX_NCM_FILE_SIZE_MB = 50

# Quantidade de dígitos do código  ->  nível na nomenclatura do NCM.
LEVEL_BY_DIGIT_COUNT = {
    2: "chapter",
    4: "heading",
    5: "subheading_1",
    6: "subheading_2",
    7: "item",
    8: "subitem",
}

HTML_TAG = re.compile(r"<[^>]+>")
LEVEL_DASHES_AT_START = re.compile(r"^[-\s]+")


class DataUtil:
    def __init__(self):
        pass

    def import_ncm_file(self, path):
        """
        Lê o JSON da tabela de NCM do Portal Único Siscomex e grava no banco.

            ok, summary = DataUtil().import_ncm_file("Tabela_NCM_Vigente_20261121.json")

        Pode rodar de novo com uma tabela mais nova: atualiza o que mudou.
        """
        ok, table = self.read_ncm_file(path)
        if not ok:
            return False, table

        return NcmDB().save_table(table, Path(path).name)

    def import_ncm_content(self, content, origin_name):
        """
        Mesmo que import_ncm_file, mas com o JSON já carregado (ex: baixado agora do Siscomex).
        Se essa mesma versão da tabela já foi importada, não grava de novo.

            ok, summary = DataUtil().import_ncm_content(json_baixado, "Siscomex (download diário)")
            summary  ->  {"saved": 15157, ...}  ou  {"already_imported": True}
        """
        ok, table = self.read_ncm_content(content)
        if not ok:
            return False, table

        ncm_db = NcmDB()
        ok, already_imported = ncm_db.exists(
            "ncm_imports", where={"legal_act": table["legal_act"], "version_label": table["version_label"]}
        )
        if not ok:
            return False, already_imported
        if already_imported:
            return True, {"already_imported": True, **{key: table[key] for key in ("legal_act", "version_label")}}

        return ncm_db.save_table(table, origin_name)

    def read_ncm_file(self, path):
        """
        Lê o JSON da tabela de NCM e devolve os códigos limpos, sem gravar nada.

        Formato do arquivo (baixado em portalunico.siscomex.gov.br):
            {
              "Data_Ultima_Atualizacao_NCM": "Vigente em 21/11/2026",
              "Ato": "Resolução Gecex nº 926/2026",
              "Nomenclaturas": [
                {"Codigo": "0101.21.00", "Descricao": "-- Reprodutores de raça pura",
                 "Data_Inicio": "01/04/2022", "Data_Fim": "31/12/9999",
                 "Tipo_Ato_Ini": "Res Gecex", "Numero_Ato_Ini": "272", "Ano_Ato_Ini": "2021"},
                ...
              ]
            }

        Devolve (True, {"legal_act", "version_label", "codes": [...]}) ou (False, erro).
        Se qualquer código vier fora do padrão, o arquivo inteiro é recusado,
        para nunca gravar uma tabela pela metade.
        """
        ok, content = self._load_json_file(path)
        if not ok:
            return False, content

        return self.read_ncm_content(content)

    def read_ncm_content(self, content):
        """Mesmo que read_ncm_file, com o JSON já carregado na memória."""
        if not isinstance(content, dict):
            return False, "O JSON precisa ser um objeto com a chave \"Nomenclaturas\"."

        entries = content.get("Nomenclaturas")
        if not isinstance(entries, list) or not entries:
            return False, "O arquivo não tem a lista \"Nomenclaturas\". Não parece ser a tabela de NCM do Siscomex."

        codes = []
        for position, entry in enumerate(entries, start=1):
            ok, ncm = self._read_ncm_entry(entry)
            if not ok:
                return False, f"Item {position} da lista: {ncm}"
            codes.append(ncm)

        # Ordem do código põe o pai antes do filho ("01" < "0101" < "01012100"),
        # que é o que o banco precisa para aceitar o parent_code.
        codes.sort(key=lambda ncm: ncm["code"])

        repeated_codes = self._find_repeated_codes(codes)
        if repeated_codes:
            return False, f"Códigos repetidos no arquivo: {', '.join(repeated_codes[:10])}"

        self._fill_parent_and_full_description(codes)

        return True, {
            "legal_act": str(content.get("Ato") or "Não informado")[:150],
            "version_label": str(content.get("Data_Ultima_Atualizacao_NCM") or "Não informado")[:100],
            "codes": codes,
        }

    def _load_json_file(self, path):
        file = Path(path)
        if not file.is_file():
            return False, f"Arquivo não encontrado: {path}"

        size_in_mb = file.stat().st_size / (1024 * 1024)
        if size_in_mb > MAX_NCM_FILE_SIZE_MB:
            return False, f"Arquivo com {size_in_mb:.0f} MB, maior que o limite de {MAX_NCM_FILE_SIZE_MB} MB."

        try:
            with open(file, encoding="utf-8") as opened_file:
                content = json.load(opened_file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            return False, f"Não foi possível ler o JSON: {error}"

        if not isinstance(content, dict):
            return False, "O JSON precisa ser um objeto com a chave \"Nomenclaturas\"."

        return True, content

    def _read_ncm_entry(self, entry):
        """Transforma um item da lista do Siscomex numa linha da tabela ncm."""
        if not isinstance(entry, dict):
            return False, "não é um objeto"

        formatted_code = str(entry.get("Codigo", "")).strip()
        code = formatted_code.replace(".", "")
        level = LEVEL_BY_DIGIT_COUNT.get(len(code))

        if not code.isdigit() or level is None:
            return False, f"código fora do padrão do NCM: {formatted_code!r}"

        description = self._clean_description(entry.get("Descricao"))
        if not description:
            return False, f"NCM {formatted_code} sem descrição"

        ok, valid_from = self._read_date(entry.get("Data_Inicio"))
        if not ok:
            return False, f"NCM {formatted_code}: data de início inválida ({entry.get('Data_Inicio')!r})"

        ok, valid_until = self._read_date(entry.get("Data_Fim"))
        if not ok:
            return False, f"NCM {formatted_code}: data de fim inválida ({entry.get('Data_Fim')!r})"

        return True, {
            "code": code,
            "formatted_code": formatted_code[:10],
            "level": level,
            "parent_code": None,
            "description": description[:1500],
            "full_description": description,
            "valid_from": valid_from,
            "valid_until": valid_until,
            "act_type": str(entry.get("Tipo_Ato_Ini") or "")[:30],
            "act_number": str(entry.get("Numero_Ato_Ini") or "")[:10],
            "act_year": str(entry.get("Ano_Ato_Ini") or "")[:4],
        }

    def _clean_description(self, description):
        """
        Tira o HTML (<i>, <sup>, <sub>) e os traços do começo, que no arquivo
        só indicam o nível ("-- Outros" vira "Outros"). O nível já fica na coluna level.
        """
        text = HTML_TAG.sub("", str(description or ""))
        text = LEVEL_DASHES_AT_START.sub("", text)
        return " ".join(text.split())

    def _read_date(self, text):
        """Converte "31/12/2026" em "2026-12-31", o formato de data que o banco entende e ordena certo."""
        try:
            return True, datetime.strptime(str(text).strip(), "%d/%m/%Y").date().isoformat()
        except ValueError:
            return False, None

    def _find_repeated_codes(self, codes_sorted_by_code):
        repeated = []
        for previous, current in zip(codes_sorted_by_code, codes_sorted_by_code[1:]):
            if previous["code"] == current["code"]:
                repeated.append(current["formatted_code"])
        return repeated

    def _fill_parent_and_full_description(self, codes_sorted_by_code):
        """
        O pai de um código é o código mais longo do arquivo que é o começo dele.
        Nem todo nível existe: o pai de "0101.21.00" é "0101.2", porque "0101.21" não está na tabela.

        A descrição completa junta a do pai com a do filho, para "Outros" virar algo como:
        "Animais vivos > Cavalos, asininos e muares, vivos > Cavalos > Outros"
        """
        ncm_by_code = {}

        for ncm in codes_sorted_by_code:
            for prefix_size in range(len(ncm["code"]) - 1, 1, -1):
                parent = ncm_by_code.get(ncm["code"][:prefix_size])
                if parent:
                    ncm["parent_code"] = parent["code"]
                    parent_path = parent["full_description"].rstrip(".:; ")
                    ncm["full_description"] = f"{parent_path} > {ncm['description'].rstrip('.:; ')}"
                    break

            ncm_by_code[ncm["code"]] = ncm
