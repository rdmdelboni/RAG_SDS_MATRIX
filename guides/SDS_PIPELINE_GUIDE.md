# SDS Processing Pipeline

Complete workflow for processing Safety Data Sheets and extracting chemical data.

## Fluxo de Processamento

A pipeline executa 4 etapas:

### 1️⃣ Seleção da Pasta Externa
- Escolhe uma pasta contendo arquivos SDS
- Varre recursivamente todos os subdiretórios
- Suporta formatos: PDF, DOCX, XLSX, XLS, CSV, TXT

### 2️⃣ Criação da Lista de Extração
- Remove arquivos duplicados por:
  - **Hash de conteúdo** - arquivos idênticos
  - **Nome + tamanho** - arquivos similares
- Gera lista de arquivos únicos a processar

### 3️⃣ Extração e Classificação
- Carrega cada arquivo
- Extrai dados SDS (usando RAG + LLM):
  - Nomes químicos e números CAS
  - Classificações de perigo
  - Limites de exposição
  - Requisitos de armazenamento
  - Procedimentos de emergência

### 4️⃣ Processamento
- Deduplica dados químicos
- Constrói matriz de compatibilidade
- Armazena no banco de dados
- Gera relatórios

---

## Como Usar

### Opção 1: Apenas Listar e Verificar Duplicatas

```bash
python scripts/sds_pipeline.py --input /caminho/para/sds --list-only
```

Output:
```
✓ Found 41 files

📋 EXTRACTION LIST (39 files):
1. document1.pdf (1024.0 KB)
2. document2.xlsx (512.0 KB)
...
```

### Opção 2: Extrair Dados (sem processar)

```bash
python scripts/sds_pipeline.py --input /caminho/para/sds --extract-only
```

Extrai dados mas não constrói a matriz.

### Opção 3: Pipeline Completo

```bash
python scripts/sds_pipeline.py --input /caminho/para/sds
```

Executa todas as 4 etapas e salva resultados.

### Opção 4: Custom Output

```bash
python scripts/sds_pipeline.py \
  --input /caminho/para/sds \
  --output /caminho/para/output
```

---

## Exemplo Prático

```bash
# Processar SDS de uma pasta USB
python scripts/sds_pipeline.py --input /mnt/usb/sds_documents

# Processar com saída customizada
python scripts/sds_pipeline.py \
  --input ~/Downloads/SDS \
  --output ~/Desktop/SDS_Results

# Apenas verificar o que tem (sem processar)
python scripts/sds_pipeline.py --input ~/Documents/SDS --list-only
```

---

## Saída Gerada

Após a execução, os resultados são salvos em:
```
data/output/sds_pipeline_results_YYYYMMDD_HHMMSS.json
```

Contém:
- Lista de arquivos processados
- Duplicatas removidas
- Dados extraídos por arquivo
- Químicos únicos encontrados
- Entradas da matriz de compatibilidade
- Erros e avisos

---

## Suporte a Formatos

✅ **PDF** - Mais comum em SDS  
✅ **DOCX** - Microsoft Word  
✅ **XLSX** - Excel moderno (recomendado para dados estruturados)  
✅ **XLS** - Excel legado  
✅ **CSV** - Dados tabulares  
✅ **TXT** - Texto simples  

---

## Detecção de Duplicatas

O pipeline usa 2 estratégias:

### 1. Hash de Conteúdo (SHA256)
Detecta arquivos com conteúdo **idêntico**, mesmo que com nomes diferentes:
```
❌ Removido: documento1.pdf vs documento_v2.pdf (mesmo conteúdo)
```

### 2. Nome + Tamanho
Detecta arquivos **muito similares** (mesma pasta baixa 2x):
```
❌ Removido: dados.xlsx vs dados (1).xlsx (mesmo tamanho, nome parecido)
```

---

## Exemplo de Uso Com Pasta Estruturada

Se seus SDS estão organizados assim:

```
/mnt/external/SDS_Library/
├── USA/
│   ├── chemical_a.pdf
│   └── chemical_b.xlsx
├── EU/
│   ├── document_1.pdf
│   └── document_2.docx
└── Asia/
    ├── specification.xlsx
    └── hazards.csv
```

Execute:
```bash
python scripts/sds_pipeline.py \
  --input /mnt/external/SDS_Library \
  --output ./sds_results
```

O pipeline:
1. ✅ Encontra todos os 7 arquivos (recursivo)
2. ✅ Remove qualquer duplicata
3. ✅ Extrai dados de cada um
4. ✅ Salva resultados em `sds_results/sds_pipeline_results_*.json`

---

## Integração com a RAG

Após processamento, os dados extraídos podem ser:

1. **Ingeridos na RAG**:
   ```bash
   python scripts/ingest_documents.py --folder /resultado/sds
   ```

2. **Consultados** com o rag_records:
   ```bash
   python scripts/rag_records.py --hazards
   python scripts/rag_records.py --incompatibilities
   ```

3. **Usados para construir a matriz**:
   ```bash
   python main.py
   ```

---

## Troubleshooting

### "Folder does not exist"
Verifique se o caminho está correto:
```bash
ls -la /caminho/para/sds
```

### "No content extracted"
Arquivo pode estar corrompido. Verifique manualmente.

### Processo demora muito
- Use `--list-only` para verificar a quantidade
- PDFs grandes (>100MB) levam mais tempo
- LLM extraction depende de Ollama disponível

### Muitas duplicatas removidas
Isso é normal. O pipeline removerá:
- Downloads múltiplos do mesmo arquivo
- Diferentes versões (se conteúdo igual)
- Cópias em subpastas

---

## Próximos Passos

1. Escolha a pasta com seus SDS
2. Execute: `python scripts/sds_pipeline.py --input /pasta --list-only`
3. Verifique a lista de arquivos
4. Execute o pipeline completo
5. Use `rag_records.py` para consultar dados extraídos
6. Construa a matriz com `main.py`
