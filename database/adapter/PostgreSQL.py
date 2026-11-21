"""
Conexão com PostgreSQL.

Todos os métodos devolvem (True, resultado) ou (False, mensagem de erro).
Valores vão sempre separados do SQL (%s) e nomes de tabela e coluna são
validados antes de entrar no comando, o que impede SQL Injection.

O MySQL.py tem exatamente os mesmos métodos.
"""
import re

import psycopg
from psycopg.rows import dict_row

# Só minúsculas: o Postgres converte para minúscula nomes sem aspas.
SAFE_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")
SAFE_SETTING = re.compile(r"^[A-Za-z0-9_./:+-]+$")
WHERE_OPERATORS = ("=", "!=", "<", "<=", ">", ">=", "LIKE", "NOT LIKE", "ILIKE")


class PostgreSQL:

    DEFAULT_PORT = 5432

    def __init__(self, host, port, user, password, database):
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.database = self._check_name(database)

        # Fuso fixo: sem ele NOW() usa o fuso do servidor, que em Docker é UTC (3h adiantado).
        # Nome da região em vez de "-03:00": no Postgres o sinal do offset em texto é invertido.
        self.time_zone = "America/Sao_Paulo"
        self.charset = "UTF8"
        self.collation = None  # None usa a do servidor. Ex: "pt_BR.UTF-8"

    def config(self, time_zone=None, charset=None, collation=None):
        """
        Troca fuso, charset e collation. Só muda o que for passado.
        Charset e collation só valem na criação do banco (create_database).

            self.config(time_zone="America/Manaus")
        """
        settings = {"time_zone": time_zone, "charset": charset, "collation": collation}

        for name, value in settings.items():
            if value is not None and not SAFE_SETTING.match(str(value)):
                return False, f"Valor inválido para {name}: {value!r}"

        for name, value in settings.items():
            if value is not None:
                setattr(self, name, value)

        return True, None

    def connect(self, use_database=True):
        """
        Abre uma conexão nova. Quem abre fecha.
        Com use_database=False conecta no banco "postgres", que todo servidor tem,
        em autocommit (CREATE DATABASE não roda dentro de transação).
        """
        return psycopg.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            dbname=self.database if use_database else "postgres",
            client_encoding=self.charset,
            options=f"-c TimeZone={self.time_zone}",
            autocommit=not use_database,
        )

    def select(self, table, columns="*", where=None, order_by=None, limit=None, offset=None, fetch="all"):
        """
        Busca linhas de uma tabela. Cada linha vem como dicionário.

            self.select("products")
            self.select("products", where={"active": True}, order_by="name")
            self.select("products", ["id", "name"], where={"id": 5}, fetch="one")
            self.select("orders", order_by="created_at DESC", limit=20, offset=40)

        fetch="all" devolve a lista de linhas.
        fetch="one" devolve só a primeira linha (ou None) e já busca com LIMIT 1.

        where (todas as condições são unidas com AND):
            {"id": 5}               id = 5
            {"deleted_at": None}    deleted_at IS NULL
            {"id": [1, 2, 3]}       id IN (1, 2, 3)
            {"price": (">", 10)}    price > 10  (= != < <= > >= LIKE NOT LIKE ILIKE)

        order_by: "name", "name DESC" ou uma lista: ["category", "name DESC"]
        """
        try:
            if fetch not in ("all", "one"):
                raise ValueError(f"fetch deve ser 'all' ou 'one', recebido {fetch!r}")

            if fetch == "one":
                limit = 1

            if columns == "*":
                column_list = "*"
            else:
                column_list = ", ".join(self._quote(column) for column in columns)

            where_sql, values = self._where(where)
            sql = f"SELECT {column_list} FROM {self._quote(table)}{where_sql}{self._order_by(order_by)}"

            if limit is not None:
                sql += " LIMIT %s"
                values += (int(limit),)

            if offset is not None:
                sql += " OFFSET %s"
                values += (int(offset),)

            return True, self._execute(sql, values, fetch)

        except (ValueError, psycopg.Error) as error:
            return False, str(error)

    def count(self, table, where=None):
        """
        Conta as linhas. Mesmo where do select.

            self.count("orders", where={"status": "open"})  ->  (True, 7)
        """
        try:
            where_sql, values = self._where(where)
            sql = f"SELECT COUNT(*) AS total FROM {self._quote(table)}{where_sql}"
            return True, self._execute(sql, values, "one")["total"]

        except (ValueError, psycopg.Error) as error:
            return False, str(error)

    def exists(self, table, where):
        """
        Diz se existe ao menos uma linha. Mesmo where do select.

            self.exists("users", where={"email": email})  ->  (True, False)
        """
        try:
            where_sql, values = self._where(where)
            sql = f"SELECT 1 FROM {self._quote(table)}{where_sql} LIMIT 1"
            return True, self._execute(sql, values, "one") is not None

        except (ValueError, psycopg.Error) as error:
            return False, str(error)

    def insert(self, table, data):
        """
        Insere uma linha e devolve o id: o passado em data["id"] (ex: UUID)
        ou o gerado pelo SERIAL (None se a tabela não tiver coluna id).

            self.insert("products", {"name": "X-Burguer", "price": 25.9})  ->  (True, 12)
            self.insert("users", {"id": str(uuid.uuid4()), ...})          ->  (True, "9b1d...")
        """
        try:
            columns = ", ".join(self._quote(column) for column in data)
            placeholders = ", ".join(["%s"] * len(data))
            # O Postgres não tem lastrowid: a linha inserida volta pelo RETURNING.
            sql = f"INSERT INTO {self._quote(table)} ({columns}) VALUES ({placeholders}) RETURNING *"
            row = self._execute(sql, tuple(data.values()), "one")
            return True, row.get("id")

        except (ValueError, psycopg.Error) as error:
            return False, str(error)

    def insert_or_update_many(self, table, rows, key_columns):
        """
        Grava várias linhas numa única conexão e transação: a linha que ainda
        não existe é inserida, a que já existe (mesma chave) é atualizada.
        Se uma linha falhar, nenhuma é gravada. Devolve quantas linhas foram enviadas.

            self.insert_or_update_many("ncm", [{"code": "01", "description": "Animais vivos"}], ["code"])

        Todas as linhas precisam ter as mesmas colunas.
        key_columns são as colunas da PRIMARY KEY ou UNIQUE que identificam a linha;
        elas não são atualizadas.
        """
        try:
            if not rows:
                return True, 0

            columns = list(rows[0])
            for row in rows:
                if list(row) != columns:
                    raise ValueError("Todas as linhas precisam ter as mesmas colunas, na mesma ordem")

            columns_to_update = [column for column in columns if column not in key_columns]
            if not columns_to_update:
                raise ValueError("Não há coluna para atualizar além das colunas-chave")

            column_list = ", ".join(self._quote(column) for column in columns)
            placeholders = ", ".join(["%s"] * len(columns))
            conflict_columns = ", ".join(self._quote(column) for column in key_columns)
            changes = ", ".join(f"{self._quote(column)} = EXCLUDED.{self._quote(column)}" for column in columns_to_update)
            sql = (
                f"INSERT INTO {self._quote(table)} ({column_list}) VALUES ({placeholders}) "
                f"ON CONFLICT ({conflict_columns}) DO UPDATE SET {changes}"
            )
            values = [tuple(row.values()) for row in rows]
            self._execute_many(sql, values)
            return True, len(rows)

        except (ValueError, psycopg.Error) as error:
            return False, str(error)

    def update(self, table, data, where):
        """
        Atualiza as linhas e devolve quantas mudaram. Mesmo where do select.
        where é obrigatório, para nunca alterar a tabela inteira por engano.

            self.update("products", {"price": 27.9}, where={"id": 12})  ->  (True, 1)
        """
        try:
            if not where:
                raise ValueError("update sem where não é permitido")

            changes = ", ".join(f"{self._quote(column)} = %s" for column in data)
            where_sql, where_values = self._where(where)
            sql = f"UPDATE {self._quote(table)} SET {changes}{where_sql}"
            return True, self._execute(sql, tuple(data.values()) + where_values, "rowcount")

        except (ValueError, psycopg.Error) as error:
            return False, str(error)

    def delete(self, table, where):
        """
        Apaga as linhas e devolve quantas foram apagadas. Mesmo where do select.
        where é obrigatório, para nunca apagar a tabela inteira por engano.

            self.delete("products", where={"id": 12})  ->  (True, 1)
        """
        try:
            if not where:
                raise ValueError("delete sem where não é permitido")

            where_sql, values = self._where(where)
            sql = f"DELETE FROM {self._quote(table)}{where_sql}"
            return True, self._execute(sql, values, "rowcount")

        except (ValueError, psycopg.Error) as error:
            return False, str(error)

    def create_database(self):
        """Cria o banco, caso ainda não exista."""
        try:
            # O Postgres não tem CREATE DATABASE IF NOT EXISTS, então consulta antes.
            found = self._execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (self.database,), "one", use_database=False
            )
            if found:
                return True, None

            sql = f"CREATE DATABASE {self._quote(self.database)} ENCODING '{self.charset}' TEMPLATE template0"
            if self.collation:
                sql += f" LC_COLLATE '{self.collation}' LC_CTYPE '{self.collation}'"

            self._execute(sql, None, None, use_database=False)
            return True, None

        except psycopg.Error as error:
            return False, str(error)

    def create_table(self, table, columns):
        """
        Cria a tabela, caso ainda não exista.
        Os tipos entram direto no SQL: devem vir do código, nunca do usuário.

            self.create_table("products", {
                "id": "SERIAL PRIMARY KEY",
                "name": "VARCHAR(100) NOT NULL",
                "price": "NUMERIC(10, 2) NOT NULL",
            })
        """
        try:
            definitions = []
            for column, column_type in columns.items():
                definitions.append(f"{self._quote(column)} {self._check_type(column_type)}")

            sql = f"CREATE TABLE IF NOT EXISTS {self._quote(table)} ({', '.join(definitions)})"
            self._execute(sql, None, None)
            return True, None

        except (ValueError, psycopg.Error) as error:
            return False, str(error)

    def add_column(self, table, column, column_type):
        """
        Adiciona uma coluna numa tabela que já existe. Usado pela migração.
        Coluna NOT NULL nova precisa de DEFAULT, senão falha em tabela com dados.

            self.add_column("products", "photo", "VARCHAR(255) NULL")
        """
        try:
            sql = f"ALTER TABLE {self._quote(table)} ADD COLUMN {self._quote(column)} {self._check_type(column_type)}"
            self._execute(sql, None, None)
            return True, None

        except (ValueError, psycopg.Error) as error:
            return False, str(error)

    def execute_sql(self, sql):
        """
        Executa um comando SQL do jeito que veio, sem parâmetros.
        Só para comandos de arquivo .sql do projeto (run_sql_file e migrate), nunca com dado de usuário.
        """
        try:
            self._execute(sql, None, None)
            return True, None

        except psycopg.Error as error:
            return False, str(error)

    def table_exists(self, table):
        """(True, True) se a tabela existe."""
        return self.exists("information_schema.tables", {"table_schema": "public", "table_name": table})

    def column_exists(self, table, column):
        """(True, True) se a coluna existe na tabela."""
        return self.exists(
            "information_schema.columns",
            {"table_schema": "public", "table_name": table, "column_name": column},
        )

    def _execute(self, sql, values, fetch, use_database=True):
        """
        Abre a conexão, executa, faz commit e fecha. Erros sobem para quem chamou.

        fetch: "all" (linhas), "one" (uma linha), "rowcount" (linhas afetadas)
               ou None (nada).
        """
        connection = self.connect(use_database)
        try:
            cursor = connection.cursor(row_factory=dict_row)
            cursor.execute(sql, values)

            if fetch == "all":
                result = cursor.fetchall()
            elif fetch == "one":
                result = cursor.fetchone()
            elif fetch == "rowcount":
                result = cursor.rowcount
            else:
                result = None

            connection.commit()
            return result

        except psycopg.Error:
            connection.rollback()
            raise

        finally:
            connection.close()

    def _execute_many(self, sql, list_of_values):
        """Executa o mesmo comando para cada conjunto de valores, tudo numa transação só."""
        connection = self.connect()
        try:
            cursor = connection.cursor()
            cursor.executemany(sql, list_of_values)
            connection.commit()

        except psycopg.Error:
            connection.rollback()
            raise

        finally:
            connection.close()

    def _where(self, where):
        """Transforma o dicionário do where em (" WHERE ...", valores)."""
        if not where:
            return "", ()

        conditions = []
        values = []

        for column, value in where.items():
            column = self._quote(column)

            if value is None:
                conditions.append(f"{column} IS NULL")

            elif isinstance(value, list):
                if not value:
                    conditions.append("1 = 0")  # IN de lista vazia: nenhuma linha
                else:
                    conditions.append(f"{column} IN ({', '.join(['%s'] * len(value))})")
                    values.extend(value)

            elif isinstance(value, tuple):
                operator, operand = value
                operator = operator.upper()
                if operator not in WHERE_OPERATORS:
                    raise ValueError(f"Operador inválido: {operator!r}")
                conditions.append(f"{column} {operator} %s")
                values.append(operand)

            else:
                conditions.append(f"{column} = %s")
                values.append(value)

        return " WHERE " + " AND ".join(conditions), tuple(values)

    def _order_by(self, order_by):
        """Transforma "name DESC" (ou uma lista deles) em ' ORDER BY "name" DESC'."""
        if not order_by:
            return ""

        if isinstance(order_by, str):
            order_by = [order_by]

        parts = []
        for item in order_by:
            column, _, direction = item.strip().partition(" ")
            direction = direction.strip().upper() or "ASC"
            if direction not in ("ASC", "DESC"):
                raise ValueError(f"Direção inválida no order_by: {item!r}")
            parts.append(f"{self._quote(column)} {direction}")

        return " ORDER BY " + ", ".join(parts)

    def _quote(self, name):
        """Valida e coloca aspas duplas no nome. Aceita "tabela.coluna"."""
        return ".".join(f'"{self._check_name(part)}"' for part in name.split("."))

    @staticmethod
    def _check_type(column_type):
        """Tipo de coluna entra direto no SQL, então não pode encadear outro comando."""
        if any(forbidden in column_type for forbidden in (";", "--", "/*")):
            raise ValueError(f"Tipo de coluna inválido: {column_type!r}")
        return column_type

    @staticmethod
    def _check_name(name):
        if not isinstance(name, str) or not SAFE_NAME.match(name):
            raise ValueError(f"Nome inválido: {name!r}")
        return name
