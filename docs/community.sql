-- Schema completo e atual do banco da comunidade (SQLite).
-- Fica só no servidor e nunca vai no download público.
-- Roda inteiro a cada início do app pelo CommunityDatabase().migrate().
--
-- O acesso é parecido com o Git: a pessoa escolhe um nome de usuário e recebe um token.
-- Não tem e-mail nem senha. O nome aparece no histórico público; o token assina as alterações.


CREATE TABLE IF NOT EXISTS contributors (
    id CHAR(36) NOT NULL PRIMARY KEY,
    username VARCHAR(40) NOT NULL UNIQUE,
    reputation INTEGER NOT NULL DEFAULT 0,
    edit_count INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_contribution_at DATETIME NULL,
    -- Confiável grava direto, sem passar pela fila de votação (ERPs e bots da Thenorian).
    -- O DEFAULT é 1 de propósito: quando a coluna foi criada, todo mundo que já existia
    -- continuou gravando direto. Quem se cadastra depois entra com 0 (ver ContributorDB.create).
    trusted INTEGER NOT NULL DEFAULT 1,
    -- Moderador decide sozinho uma alteração da fila com um único voto.
    moderator INTEGER NOT NULL DEFAULT 0
);


-- Só o hash SHA-256 do token é guardado. O token em si aparece uma única vez, na criação.
CREATE TABLE IF NOT EXISTS contributor_tokens (
    token_hash CHAR(64) NOT NULL PRIMARY KEY,
    contributor_id CHAR(36) NOT NULL REFERENCES contributors (id),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contributor_tokens_contributor_id ON contributor_tokens (contributor_id);


-- Fila de votação: alteração de quem ainda é Iniciante espera aqui até a comunidade decidir.
-- action diz o que será feito (ex: create_product, update_product) e payload guarda,
-- em JSON, exatamente os campos que a pessoa enviou. Aprovada, a alteração é aplicada
-- em nome de quem enviou, como se tivesse gravado direto.
-- status: pending (esperando votos), approved (aplicada), rejected (descartada)
--         ou failed (aprovada, mas não deu para aplicar; o motivo fica em result_message).
CREATE TABLE IF NOT EXISTS pending_changes (
    id CHAR(36) NOT NULL PRIMARY KEY,
    action VARCHAR(40) NOT NULL,
    target_id CHAR(36) NULL,
    payload TEXT NOT NULL,
    reason VARCHAR(300) NOT NULL,
    contributor_id CHAR(36) NOT NULL REFERENCES contributors (id),
    status VARCHAR(10) NOT NULL DEFAULT 'pending',
    score INTEGER NOT NULL DEFAULT 0,
    result_message TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME NULL
);

CREATE INDEX IF NOT EXISTS idx_pending_changes_status ON pending_changes (status, created_at);


-- Um voto por pessoa em cada alteração da fila: 1 a favor, -1 contra. Pode trocar ou retirar.
CREATE TABLE IF NOT EXISTS pending_change_votes (
    pending_change_id CHAR(36) NOT NULL REFERENCES pending_changes (id),
    contributor_id CHAR(36) NOT NULL REFERENCES contributors (id),
    vote INTEGER NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pending_change_id, contributor_id)
);
