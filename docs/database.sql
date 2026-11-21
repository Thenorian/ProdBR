-- Schema completo e atual do banco novo do ProdBR (SQLite).
-- Roda inteiro a cada início do app pelo Database().migrate(): cria o que falta
-- (tabela ou coluna nova) e nunca altera tipo, renomeia ou remove coluna.
-- Regras para editar este arquivo estão no docstring de Database.migrate().
--
-- No SQLite não existe "ON UPDATE CURRENT_TIMESTAMP": quem atualiza a linha
-- grava o updated_at junto.


-- Cada vez que a tabela oficial de NCM do Siscomex (Portal Único) é importada.
-- Serve de auditoria: diz qual versão da tabela está no banco e quando entrou.
CREATE TABLE IF NOT EXISTS ncm_imports (
    id CHAR(36) NOT NULL PRIMARY KEY,
    legal_act VARCHAR(150) NOT NULL,
    version_label VARCHAR(100) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    total_codes INTEGER NOT NULL,
    imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- Nomenclatura Comum do Mercosul, com a árvore completa:
--   chapter (2 dígitos)  >  heading (4)  >  subheading_1 (5)  >  subheading_2 (6)  >  item (7)  >  subitem (8)
-- Só o subitem (8 dígitos) é o NCM que vai na nota fiscal e no produto.
-- Os níveis de cima existem para dar sentido à descrição ("Outros" sozinho não diz nada)
-- e para uma categoria poder apontar para um grupo inteiro de NCMs.
CREATE TABLE IF NOT EXISTS ncm (
    code VARCHAR(8) NOT NULL PRIMARY KEY,
    formatted_code VARCHAR(10) NOT NULL,
    level VARCHAR(20) NOT NULL,
    parent_code VARCHAR(8) NULL REFERENCES ncm (code),
    description VARCHAR(1500) NOT NULL,
    full_description TEXT NOT NULL,
    valid_from DATE NOT NULL,
    valid_until DATE NOT NULL,
    act_type VARCHAR(30) NOT NULL,
    act_number VARCHAR(10) NOT NULL,
    act_year VARCHAR(4) NOT NULL,
    in_force BOOLEAN NOT NULL DEFAULT 1,
    import_id CHAR(36) NOT NULL REFERENCES ncm_imports (id),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ncm_parent_code ON ncm (parent_code);
CREATE INDEX IF NOT EXISTS idx_ncm_level ON ncm (level);


-- Categoria de produto, em árvore (parent_id). Ex: Bebidas > Cervejas > Puro malte.
-- ncm_code liga a categoria a um NCM de qualquer nível. A subcategoria sem
-- ncm_code herda o da categoria acima (ver NcmDB.suggest_for_category).
CREATE TABLE IF NOT EXISTS categories (
    id CHAR(36) NOT NULL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    parent_id CHAR(36) NULL REFERENCES categories (id),
    ncm_code VARCHAR(8) NULL REFERENCES ncm (code),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_categories_parent_id ON categories (parent_id);
