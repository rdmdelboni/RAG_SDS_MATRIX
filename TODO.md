# RAG SDS Matrix - Detailed TODO

## Dados MRLP (Regras/Hazards)
- [ ] Criar JSONL reais de incompatibilidades (UNIFAL/CAMEO/NFPA) com `cas_a`, `cas_b`, `rule` (I/R/C), `source`, `justification` (opcional), `group_a/group_b` (opcional).
- [ ] Criar JSONL reais de hazards (NIOSH/CETESB) com `cas`, `hazard_flags` (ex.: {"dangerous": true}), `env_risk`, `idlh/pel/rel`, `source`.
- [ ] Colocar os JSONL em `data/datasets/mrlp/` e rodar:
  ```
  source venv/bin/activate
  python scripts/ingest_mrlp.py \
    --incompatibilities data/datasets/mrlp/incompatibilities_real.jsonl \
    --hazards data/datasets/mrlp/hazards_real.jsonl
  ```
- [ ] Validar contagens com `python scripts/status.py` (regras, hazards, snapshots, decisões).
- [ ] Criar job/cron para reingestão automática (varrer `data/datasets/mrlp/*.jsonl`, chamar `ingest_mrlp.py`, depois `status.py`).

## Corpus de normas (Chroma)
- [ ] Colocar PDFs de NBR 14725 (partes 2 e 4), NR-26/20, CETESB em `data/knowledge_base/`.
- [ ] Ingerir normas no Chroma (criar script `scripts/ingest_norms.py` ou usar `KnowledgeIngestionService`).
- [ ] Implementar gate: habilitar RAG apenas se `collection_stats.document_count >= MIN_CHUNKS` (config em settings/UI).

## Matriz e auditoria
- [ ] Exportar justificativas/fonte por célula: usar `MatrixExporter.export_decisions_long()` e adicionar CLI se necessário.
- [ ] Garantir logging por célula (já em `matrix_decisions`), incluir no relatório final da matriz.
- [ ] Expor métricas (regras, hazards, snapshots, decisões, corpus Chroma) em uma aba/endpoint de status na UI.

## Configurações/thresholds
- [ ] Tornar `HAZARD_IDLH_THRESHOLD` e flag de `env_risk` configuráveis via `.env` e documentar.

## Testes e smoke end-to-end
- [ ] Adicionar smoke test: ingest structured (regras/hazards) + process SDS + gerar matriz + export decisions.
- [ ] Testar elevação por hazard com dados reais (IDLH/env_risk) e regra binária priorizada.

## Permissões/Logging
- [ ] Garantir permissão de escrita em `data/logs` (mkdir/chmod) ou usar logging somente em console se não disponível.
