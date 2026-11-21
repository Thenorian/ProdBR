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
    last_contribution_at DATETIME NULL
);


-- Só o hash SHA-256 do token é guardado. O token em si aparece uma única vez, na criação.
CREATE TABLE IF NOT EXISTS contributor_tokens (
    token_hash CHAR(64) NOT NULL PRIMARY KEY,
    contributor_id CHAR(36) NOT NULL REFERENCES contributors (id),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contributor_tokens_contributor_id ON contributor_tokens (contributor_id);
