"""
Classe mãe de todas as classes de banco do sistema (DataUser, DataProduct...).

Para trocar de banco, troque só o import abaixo:
    MySQL ou MariaDB:  from database.adapter.MySQL import MySQL as Data
    PostgreSQL:        from database.adapter.PostgreSQL import PostgreSQL as Data

Exemplo de classe filha:

    class DataProduct(Database):

        def list_active(self, page=1):
            return self.select("products", where={"active": True}, order_by="name", limit=20, offset=(page - 1) * 20)

        def get(self, product_id):
            return self.select("products", where={"id": product_id}, fetch="one")

        def create(self, name, price):
            return self.insert("products", {"name": name, "price": price})

Métodos disponíveis com self. (ver docstring de cada um em database/adapter/):
    select, count, exists, insert, insert_or_update_many, update, delete,
    create_database, create_table, add_column, table_exists, column_exists, config
E aqui mesmo: migrate, run_sql_file

Variáveis de ambiente:
    obrigatórias: DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
    opcionais:    DB_PORT, DB_TIME_ZONE, DB_CHARSET, DB_COLLATION
"""
import os
import re

from dotenv import load_dotenv

load_dotenv()

from database.adapter.MySQL import MySQL as Data

# Palavras que começam uma linha de CREATE TABLE que não é coluna (chaves, índices, regras).
NOT_A_COLUMN = ("PRIMARY", "KEY", "INDEX", "UNIQUE", "CONSTRAINT", "FOREIGN", "CHECK", "FULLTEXT", "SPATIAL")

CREATE_TABLE = re.compile(
    r"^CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?(\w+)[`\"]?\s*\((.*)\)[^)]*$",
    re.IGNORECASE | re.DOTALL,
)


class Database(Data):

    def __init__(self):
        # Os dados de acesso vêm do .env, por isso Database() não recebe argumentos.
        missing = [name for name in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME") if not os.getenv(name)]
        if missing:
            raise RuntimeError(f"Variáveis de ambiente não definidas: {', '.join(missing)}")

        super().__init__(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT") or Data.DEFAULT_PORT,
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
        )

        ok, error = self.config(
            time_zone=os.getenv("DB_TIME_ZONE") or None,
            charset=os.getenv("DB_CHARSET") or None,
            collation=os.getenv("DB_COLLATION") or None,
        )
        if not ok:
            raise RuntimeError(error)

    def migrate(self, path):
        """
        Deixa o banco igual ao database.sql. Roda toda vez que o app inicia.

            ok, changes = Database().migrate("database.sql")
            changes  ->  ["tabela criada: products", "coluna adicionada: products.photo"]

        O que faz, comando por comando, na ordem do arquivo:
            CREATE TABLE de tabela que ainda não existe:  cria a tabela.
            CREATE TABLE de tabela que já existe:         adiciona só as colunas que faltam.
            Qualquer outro comando:                       executa.
        Para no primeiro erro.

        Regras do database.sql, pois ele roda inteiro a cada início:
            - Sempre CREATE TABLE IF NOT EXISTS.
            - Chaves, índices e FKs dentro do CREATE TABLE (só são criados junto com a tabela).
            - Dados iniciais com INSERT IGNORE (MySQL) ou ON CONFLICT DO NOTHING (Postgres).
            - Coluna nova NOT NULL precisa de DEFAULT.
            - Mudar tipo, renomear ou remover coluna não é automático (risco de perder dados).
        """
        ok, error = self.create_database()
        if not ok:
            return False, error

        ok, statements = self.read_sql_file(path)
        if not ok:
            return False, statements

        changes = []

        for statement in statements:
            table, columns = parse_create_table(statement)

            if table is None:
                ok, error = self.execute_sql(statement)
                if not ok:
                    return False, f"{error}\nComando: {statement[:300]}"
                continue

            ok, table_exists = self.table_exists(table)
            if not ok:
                return False, table_exists

            if not table_exists:
                ok, error = self.execute_sql(statement)
                if not ok:
                    return False, f"Erro ao criar a tabela {table}: {error}"
                changes.append(f"tabela criada: {table}")
                continue

            for column, column_type in columns.items():
                ok, column_exists = self.column_exists(table, column)
                if not ok:
                    return False, column_exists
                if column_exists:
                    continue

                ok, error = self.add_column(table, column, column_type)
                if not ok:
                    return False, f"Erro ao adicionar a coluna {table}.{column}: {error}"
                changes.append(f"coluna adicionada: {table}.{column}")

        return True, changes

    def run_sql_file(self, path):
        """
        Executa todos os comandos de um arquivo .sql, na ordem. Para no primeiro erro.

            self.run_sql_file("files/seed.sql")
        """
        ok, statements = self.read_sql_file(path)
        if not ok:
            return False, statements

        for statement in statements:
            ok, error = self.execute_sql(statement)
            if not ok:
                return False, f"{error}\nComando: {statement[:300]}"

        return True, None

    def read_sql_file(self, path):
        """
        Lê um arquivo .sql e devolve a lista de comandos, sem os comentários.

        CREATE DATABASE e USE são ignorados: o nome do banco vem sempre do DB_NAME.
        Comentários aceitos: "-- até o fim da linha" e "/* bloco */".
        """
        try:
            with open(path, encoding="utf-8") as file:
                text = file.read()
        except OSError as error:
            return False, f"Não foi possível ler {path}: {error}"

        statements = []
        for statement in split_sql(text):
            first_words = " ".join(statement.split()[:2]).upper()
            if first_words == "CREATE DATABASE" or first_words.startswith("USE "):
                continue
            statements.append(statement)

        return True, statements


def split_sql(text):
    """
    Separa o texto em comandos pelo ";" e tira os comentários.
    Ignora ";", "--" e "/*" que estejam dentro de texto entre aspas ou crases.
    """
    statements = []
    current = []
    quote = None  # aspa que abriu o texto atual: ' " ou `
    i = 0

    while i < len(text):
        char = text[i]
        pair = text[i:i + 2]

        if quote:
            current.append(char)
            if char == quote:
                quote = None
            i += 1

        elif char in ("'", '"', "`"):
            quote = char
            current.append(char)
            i += 1

        elif pair == "--":
            end = text.find("\n", i)
            i = len(text) if end == -1 else end

        elif pair == "/*":
            end = text.find("*/", i + 2)
            i = len(text) if end == -1 else end + 2

        elif char == ";":
            statements.append("".join(current).strip())
            current = []
            i += 1

        else:
            current.append(char)
            i += 1

    statements.append("".join(current).strip())
    return [statement for statement in statements if statement]


def parse_create_table(statement):
    """
    Lê um CREATE TABLE e devolve (tabela, {coluna: tipo}).
    Se o comando não for CREATE TABLE, devolve (None, None).

        CREATE TABLE IF NOT EXISTS products (id INT PRIMARY KEY, name VARCHAR(100) NOT NULL)
        ->  ("products", {"id": "INT PRIMARY KEY", "name": "VARCHAR(100) NOT NULL"})
    """
    match = CREATE_TABLE.match(statement.strip())
    if not match:
        return None, None

    table, body = match.groups()
    columns = {}

    for line in split_by_comma(body):
        name, column_type = (line.split(None, 1) + [""])[:2]
        if name.upper() in NOT_A_COLUMN:
            continue
        columns[name.strip('`"')] = column_type.strip()

    return table, columns


def split_by_comma(text):
    """Separa por vírgula, ignorando as que estão dentro de parênteses ou aspas. Ex: DECIMAL(10, 2)."""
    parts = []
    current = []
    depth = 0
    quote = None

    for char in text:
        if quote:
            if char == quote:
                quote = None
        elif char in ("'", '"', "`"):
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue

        current.append(char)

    parts.append("".join(current))
    return [part for part in parts if part.strip()]
