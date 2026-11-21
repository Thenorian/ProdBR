"""
Conexão com MySQL e MariaDB.

Todos os métodos devolvem (True, resultado) ou (False, mensagem de erro).
Valores vão sempre separados do SQL (%s) e nomes de tabela e coluna são
validados antes de entrar no comando, o que impede SQL Injection.

O PostgreSQL.py tem exatamente os mesmos métodos.
"""
import re

import mysql.connector as mysql

SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SAFE_SETTING = re.compile(r"^[A-Za-z0-9_./:+-]+$")
WHERE_OPERATORS = ("=", "!=", "<", "<=", ">", ">=", "LIKE", "NOT LIKE")


class MySQL:

    DEFAULT_PORT = 3306

    def __init__(self, host, port, user, password, database):
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.database = self._check_name(database)

        # Fuso fixo: sem ele NOW() usa o fuso do servidor, que em Docker é UTC (3h adiantado).
        self.time_zone = "-03:00"
        self.charset = "utf8mb4"
        self.collation = "utf8mb4_unicode_ci"

    def config(self, time_zone=None, charset=None, collation=None):
        """
        Troca fuso, charset e collation. Só muda o que for passado.

            self.config(time_zone="-04:00")
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
        """Abre uma conexão nova. Quem abre fecha."""
        return mysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database if use_database else None,
            charset=self.charset,
            collation=self.collation,
            time_zone=self.time_zone,
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
            {"price": (">", 10)}    price > 10  (= != < <= > >= LIKE NOT LIKE)

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

        except (ValueError, mysql.Error) as error:
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

        except (ValueError, mysql.Error) as error:
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

        except (ValueError, mysql.Error) as error:
            return False, str(error)

    def insert(self, table, data):
        """
        Insere uma linha e devolve o id: o passado em data["id"] (ex: UUID)
        ou o gerado pelo AUTO_INCREMENT.

            self.insert("products", {"name": "X-Burguer", "price": 25.9})  ->  (True, 12)
            self.insert("users", {"id": str(uuid.uuid4()), ...})          ->  (True, "9b1d...")
        """
        try:
            columns = ", ".join(self._quote(column) for column in data)
            placeholders = ", ".join(["%s"] * len(data))
            sql = f"INSERT INTO {self._quote(table)} ({columns}) VALUES ({placeholders})"
            generated_id = self._execute(sql, tuple(data.values()), "id")
            return True, data.get("id", generated_id)

        except (ValueError, mysql.Error) as error:
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
            changes = ", ".join(f"{self._quote(column)} = VALUES({self._quote(column)})" for column in columns_to_update)
            sql = (
                f"INSERT INTO {self._quote(table)} ({column_list}) VALUES ({placeholders}) "
                f"ON DUPLICATE KEY UPDATE {changes}"
            )
            values = [tuple(row.values()) for row in rows]
            self._execute_many(sql, values)
            return True, len(rows)

        except (ValueError, mysql.Error) as error:
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

        except (ValueError, mysql.Error) as error:
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

        except (ValueError, mysql.Error) as error:
            return False, str(error)

    def create_database(self):
        """Cria o banco, caso ainda não exista."""
        try:
            sql = (
                f"CREATE DATABASE IF NOT EXISTS {self._quote(self.database)} "
                f"CHARACTER SET {self.charset} COLLATE {self.collation}"
            )
            self._execute(sql, None, None, use_database=False)
            return True, None

        except mysql.Error as error:
            return False, str(error)

    def create_table(self, table, columns):
        """
        Cria a tabela, caso ainda não exista.
        Os tipos entram direto no SQL: devem vir do código, nunca do usuário.

            self.create_table("products", {
                "id": "INT AUTO_INCREMENT PRIMARY KEY",
                "name": "VARCHAR(100) NOT NULL",
                "price": "DECIMAL(10, 2) NOT NULL",
            })
        """
        try:
            definitions = []
            for column, column_type in columns.items():
                definitions.append(f"{self._quote(column)} {self._check_type(column_type)}")

            sql = f"CREATE TABLE IF NOT EXISTS {self._quote(table)} ({', '.join(definitions)})"
            self._execute(sql, None, None)
            return True, None

        except (ValueError, mysql.Error) as error:
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

        except (ValueError, mysql.Error) as error:
            return False, str(error)

    def execute_sql(self, sql):
        """
        Executa um comando SQL do jeito que veio, sem parâmetros.
        Só para comandos de arquivo .sql do projeto (run_sql_file e migrate), nunca com dado de usuário.
        """
        try:
            self._execute(sql, None, None)
            return True, None

        except mysql.Error as error:
            return False, str(error)

    def table_exists(self, table):
        """(True, True) se a tabela existe."""
        return self.exists("information_schema.TABLES", {"TABLE_SCHEMA": self.database, "TABLE_NAME": table})

    def column_exists(self, table, column):
        """(True, True) se a coluna existe na tabela."""
        return self.exists(
            "information_schema.COLUMNS",
            {"TABLE_SCHEMA": self.database, "TABLE_NAME": table, "COLUMN_NAME": column},
        )

    def _execute(self, sql, values, fetch, use_database=True):
        """
        Abre a conexão, executa, faz commit e fecha. Erros sobem para quem chamou.

        fetch: "all" (linhas), "one" (uma linha), "id" (id do INSERT),
               "rowcount" (linhas afetadas) ou None (nada).
        """
        connection = self.connect(use_database)
        try:
            cursor = connection.cursor(dictionary=True, buffered=True)
            cursor.execute(sql, values)

            if fetch == "all":
                result = cursor.fetchall()
            elif fetch == "one":
                result = cursor.fetchone()
            elif fetch == "id":
                result = cursor.lastrowid
            elif fetch == "rowcount":
                result = cursor.rowcount
            else:
                result = None

            connection.commit()
            return result

        except mysql.Error:
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

        except mysql.Error:
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
        """Transforma "name DESC" (ou uma lista deles) em " ORDER BY `name` DESC"."""
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
        """Valida e coloca crase no nome. Aceita "tabela.coluna"."""
        return ".".join(f"`{self._check_name(part)}`" for part in name.split("."))

    @staticmethod
    def _check_type(column_type):
        """Tipo de coluna entra direto no SQL, então não pode encadear outro comando."""
        if any(forbidden in column_type for forbidden in (";", "--", "/*", "#")):
            raise ValueError(f"Tipo de coluna inválido: {column_type!r}")
        return column_type

    @staticmethod
    def _check_name(name):
        if not isinstance(name, str) or not SAFE_NAME.match(name):
            raise ValueError(f"Nome inválido: {name!r}")
        return name
