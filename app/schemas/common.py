from pydantic import Field

# Toda escrita na base pública pede um motivo - ele vai pro histórico
# público (revisions.reason), igual à mensagem de um commit.
REASON = Field(..., min_length=3, max_length=300, description="Motivo da alteração (obrigatório).")
