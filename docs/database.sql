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
-- Igual ao Simple ERP, a categoria guarda os dados fiscais padrão dos produtos dela.
-- O produto usa o próprio NCM, CEST e origem; o que estiver vazio vem da categoria,
-- e se a categoria também não tiver, da categoria acima (ver CategoryDB.inherited_fiscal_data).
-- NCM sem FK pelo mesmo motivo do produto: é uma Wiki.
CREATE TABLE IF NOT EXISTS categories (
    id CHAR(36) NOT NULL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    parent_id CHAR(36) NULL REFERENCES categories (id),
    ncm_code VARCHAR(8) NULL,
    cest VARCHAR(7) NULL,
    origin INTEGER NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_categories_parent_id ON categories (parent_id);


-- O produto é o centro de tudo. Tudo que um ERP precisa para preencher o cadastro
-- vem daqui ou das tabelas ligadas a ele (códigos de barras, NCM, fiscal, preço).
-- NCM é opcional e sem FK: é uma Wiki, então aceita produto sem NCM ou com um NCM
-- que ainda não está na tabela oficial (a API só avisa).
CREATE TABLE IF NOT EXISTS products (
    id CHAR(36) NOT NULL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    brand VARCHAR(120) NULL,
    manufacturer VARCHAR(120) NULL,
    manufacturer_code VARCHAR(60) NULL,
    description VARCHAR(2000) NULL,
    category_id CHAR(36) NULL REFERENCES categories (id),
    ncm_code VARCHAR(8) NULL,
    cest VARCHAR(7) NULL,
    origin INTEGER NULL,
    commercial_unit VARCHAR(10) NOT NULL DEFAULT 'UN',
    source VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_products_ncm_code ON products (ncm_code);
CREATE INDEX IF NOT EXISTS idx_products_manufacturer ON products (manufacturer);
CREATE INDEX IF NOT EXISTS idx_products_manufacturer_code ON products (manufacturer_code);
CREATE INDEX IF NOT EXISTS idx_products_category_id ON products (category_id);
CREATE INDEX IF NOT EXISTS idx_products_updated_at ON products (updated_at);


-- Códigos de barras (GTIN-8, 12, 13 ou 14). Um produto pode ter vários
-- (unidade, caixa, fardo), mas um código pertence a um produto só.
-- Cada código é uma embalagem: package_description é o texto como o fabricante
-- escreve ("6x350ml"); os outros campos são lidos dele quando dá certeza (util/packaging.py).
-- net_unit: mg, g, kg, ml, l ou un.
CREATE TABLE IF NOT EXISTS product_barcodes (
    barcode VARCHAR(14) NOT NULL PRIMARY KEY,
    product_id CHAR(36) NOT NULL REFERENCES products (id),
    package_description VARCHAR(120) NULL,
    net_quantity REAL NULL,
    net_unit VARCHAR(5) NULL,
    units_per_pack INTEGER NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_product_barcodes_product_id ON product_barcodes (product_id);


-- Preços informados por quem usa o produto. A API devolve a média dos últimos 12 meses.
-- Valor em centavos (inteiro) para não ter erro de arredondamento.
CREATE TABLE IF NOT EXISTS price_reports (
    id CHAR(36) NOT NULL PRIMARY KEY,
    product_id CHAR(36) NOT NULL REFERENCES products (id),
    price_cents INTEGER NOT NULL,
    uf VARCHAR(2) NULL,
    contributor VARCHAR(40) NOT NULL,
    reported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_price_reports_product_id ON price_reports (product_id, reported_at);


-- Regras fiscais de referência. São por NCM, não por produto: a lei tributa a
-- classificação, então todo produto com o mesmo NCM usa as mesmas regras.
-- uf, tax_regime e cest vazios valem para todos; a regra mais específica vem primeiro.
-- tax_regime: simples_nacional, lucro_presumido ou lucro_real.
CREATE TABLE IF NOT EXISTS fiscal_rules (
    id CHAR(36) NOT NULL PRIMARY KEY,
    ncm_code VARCHAR(8) NOT NULL,
    cest VARCHAR(7) NULL,
    uf VARCHAR(2) NULL,
    tax_regime VARCHAR(20) NULL,
    icms_cst VARCHAR(3) NULL,
    csosn VARCHAR(3) NULL,
    icms_rate REAL NULL,
    fcp_rate REAL NULL,
    icms_st_mva_rate REAL NULL,
    ipi_cst VARCHAR(2) NULL,
    ipi_rate REAL NULL,
    pis_cofins_cst VARCHAR(2) NULL,
    pis_rate REAL NULL,
    cofins_rate REAL NULL,
    cbs_rate REAL NULL,
    ibs_rate REAL NULL,
    ii_rate REAL NULL,
    notes VARCHAR(500) NULL,
    valid_from DATE NOT NULL,
    valid_until DATE NULL,
    source VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fiscal_rules_ncm_code ON fiscal_rules (ncm_code);


-- Histórico público de alterações, como um "git log": uma linha por campo alterado.
-- entity_type: product, category ou fiscal_rule. contributor é o nome de usuário de quem alterou.
CREATE TABLE IF NOT EXISTS revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type VARCHAR(20) NOT NULL,
    entity_id CHAR(36) NOT NULL,
    contributor VARCHAR(40) NULL,
    action VARCHAR(10) NOT NULL,
    field VARCHAR(60) NULL,
    old_value TEXT NULL,
    new_value TEXT NULL,
    reason VARCHAR(300) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_revisions_entity ON revisions (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_revisions_contributor ON revisions (contributor);
