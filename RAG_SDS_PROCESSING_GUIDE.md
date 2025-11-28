# RAG-Enhanced SDS Processing

Process Safety Data Sheets (SDS) using **all the knowledge from your RAG knowledge base**.

## O que faz

O processador RAG-SDS combina:

✅ **Extração de SDS** - Carrega e processa cada arquivo SDS  
✅ **Consultas RAG** - Para cada químico encontrado, consulta todo o conhecimento da RAG  
✅ **Enriquecimento** - Adiciona dados de perigo e incompatibilidade encontrados  
✅ **Análise** - Detecta incompatibilidades entre químicos no mesmo SDS  
✅ **Relatórios** - Gera análises estruturadas em JSON  

## Como usar

### Opção 1: Linha de Comando (Mais Simples)

```bash
./process_sds_with_rag.sh /caminho/para/sds
```

### Opção 2: Python (Mais Controle)

```bash
python scripts/rag_sds_processor.py --input /caminho/para/sds
```

### Opção 3: Salvar em Arquivo Customizado

```bash
python scripts/rag_sds_processor.py \
  --input /caminho/para/sds \
  --output ~/Desktop/resultados.json
```

### Opção 4: Processar Um Arquivo

```bash
python scripts/rag_sds_processor.py --file /caminho/para/documento.pdf
```

---

## Fluxo de Processamento

### Para cada SDS:

1. **Carrega o arquivo**
   - Suporta: PDF, DOCX, XLSX, XLS, CSV, TXT
   - Varre recursivamente subpastas

2. **Extrai químicos**
   - Nome do químico
   - Número CAS
   - Classificações de perigo
   - Limites de exposição

3. **Consulta RAG para cada químico**
   - Busca por hazards (NIOSH, CETESB, CAMEO)
   - Busca por incompatibilidades
   - Recupera exposição limits (IDLH, PEL, REL)
   - Retorna todas as fontes de dados

4. **Enriquece com dados RAG**
   - Adiciona hazards conhecidos
   - Adiciona incompatibilidades documentadas
   - Marca se químico foi encontrado na RAG

5. **Analisa incompatibilidades internas**
   - Verifica se os químicos no mesmo SDS são compatíveis
   - Gera avisos se mistura perigosa detectada

6. **Salva resultados**
   - JSON estruturado com todos os dados
   - Resumo em formato legível

---

## Exemplo Prático

Suponha que você tenha uma pasta com 3 SDS:

```
/mnt/usb/sds_documents/
├── corrosive_cleaner.pdf     → Contém HCl + H2O2 + NaOH
├── paint_stripper.xlsx       → Contém Acetone + Methylene Chloride
└── safety_data/
    └── hazardous_waste.pdf   → Contém Formaldehyde + Benzene
```

Execute:

```bash
./process_sds_with_rag.sh /mnt/usb/sds_documents
```

### Saída:

```json
{
  "file": "corrosive_cleaner.pdf",
  "status": "success",
  "chemicals_extracted": 3,
  "rag_matches": 3,
  "chemicals": [
    {
      "name": "Hydrochloric acid",
      "cas_number": "7647-01-0",
      "rag_enrichment": {
        "found_in_rag": true,
        "hazards": {
          "idlh": 25.0,
          "pel": 2.0,
          "source": "NIOSH"
        },
        "incompatibilities": [
          {
            "cas_a": "7647-01-0",
            "cas_b": "7732-18-5",
            "rule": "I",
            "source": "CAMEO"
          }
        ]
      }
    },
    // ... mais químicos
  ],
  "incompatibility_analysis": {
    "warning_count": 2,
    "pairs": [
      {
        "cas_a": "7697-37-2",
        "cas_b": "7732-18-5",
        "rule": "I",
        "source": "UNIFAL"
      }
    ]
  }
}
```

---

## Entendendo o Output

### Estrutura de Cada Resultado

```json
{
  "file": "documento.pdf",                    // Nome do arquivo
  "status": "success",                        // success ou error
  "chemicals_extracted": 5,                   // Quantidade de químicos
  "rag_matches": 4,                           // Quantos estão na RAG
  "chemicals": [
    {
      "name": "Formaldehyde",
      "cas_number": "50-00-0",
      "rag_enrichment": {
        "found_in_rag": true,
        "hazards": { /* dados NIOSH, CETESB, etc */ },
        "incompatibilities": [ /* lista de incomp conhecidas */ ]
      }
    }
  ],
  "incompatibility_analysis": {
    "warning_count": 2,                       // Avisos de incomp internas
    "pairs": [                                // Pares incompatíveis
      {
        "cas_a": "...",
        "cas_b": "...",
        "rule": "I",                          // I/R/C
        "source": "CAMEO"                     // Fonte do conhecimento
      }
    ]
  }
}
```

### Resumo Final

```
📊 RAG-SDS PROCESSING COMPLETE
===================================
Files processed: 3
Successful: 3
Failed: 0

Chemicals extracted: 12
RAG matches: 11 (91.7%)
Incompatibility warnings: 5
```

---

## Dados Usados da RAG

O processador consulta 3 fontes de dados da RAG:

### 1. **Hazards** (`rag_hazards`)
- CAS number
- Hazard flags (toxic, flammable, etc.)
- IDLH (Immediately Dangerous to Life or Health)
- PEL (Permissible Exposure Limit)
- REL (Recommended Exposure Limit)
- Fonte: NIOSH, CETESB, CAMEO

### 2. **Incompatibilities** (`rag_incompatibilities`)
- CAS pair A + B
- Rule (I=Incompatible, R=Reactive, C=Conditional)
- Justification
- Source: NFPA, UNIFAL, CAMEO, NIOSH, OSHA, etc.

### 3. **Documents** (`rag_documents`)
- Document metadata
- Chemical references
- URLs and sources

---

## Casos de Uso

### 1. Auditoria de Conformidade
Verifique quais químicos no seu estoque estão documentados em regulações conhecidas:
```bash
./process_sds_with_rag.sh ~/my_chemicals --output audit_report.json
```

### 2. Análise de Risco
Identifique misturas perigosas nos SDS:
```bash
python scripts/rag_sds_processor.py --input ./storage_area
```
Procure por `incompatibility_analysis.warning_count > 0`

### 3. Integração com Sistema
Processe novos SDS recebidos e integre com seu fluxo:
```bash
./process_sds_with_rag.sh ~/new_sds_uploads
# Resultados em data/output/rag_sds_results_*.json
```

---

## Dicas

✨ **Paralelo com RAG Viewer**  
Depois de processar, use o rag_records.py para investigar:
```bash
python scripts/rag_records.py --hazards --cas 50-00-0
python scripts/rag_records.py --incompatibilities --rule I
```

✨ **Armazenar Resultados**  
Combine com rag_backup.py para arquivar:
```bash
python scripts/rag_backup.py --output /mnt/external/backups
```

✨ **Monitorar Processamento**  
Os logs mostram exatamente o que foi encontrado:
```
[INFO] Querying RAG for: Formaldehyde
[INFO] ✓ Extracted 5 chemicals
[INFO] Found 3 incompatibilities
```

---

## Próximos Passos

1. Escolha pasta com SDS
2. Execute: `./process_sds_with_rag.sh /pasta`
3. Revise os resultados
4. Use dados para:
   - Atualizar matriz de compatibilidade
   - Auditoria de conformidade
   - Relatórios de risco
   - Integração com sistema de estoque

## Troubleshooting

**"No content extracted"**
→ Arquivo corrompido. Verifique manualmente.

**Muitos "found_in_rag: false"**
→ Normal. Significa que esses químicos não estão ainda na sua RAG.
→ Use `rag_backup.py` para expandir a base de dados.

**Processamento muito lento**
→ LLM extraction depende de Ollama
→ Verifique: `ollama list` e `ollama serve`

**JSON output muito grande**
→ Isso é normal! Contém todos os dados. Use `| jq '.'` para navegar.
