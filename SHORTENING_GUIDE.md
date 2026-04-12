# Guia de Encurtamento de Scripts EN — Langrisser III Translation

## Por que encurtar?

O engine do Sega Saturn lê arquivos por **setor absoluto** na ISO, sem usar o filesystem ISO9660. Isso significa:

1. **D00.DAT não pode crescer nem ser realocado** — deve permanecer no extent original (10528 setores)
2. Cada uma das 125 seções do D00.DAT ocupa um espaço fixo definido pelo gap entre setores adjacentes
3. O texto EN traduzido pela Akari Dawn é **significativamente mais longo** que o JP original
4. Seções EN que excedem o espaço disponível **ficam em JP** (o `patch_d00_inplace()` as pula)
5. O objetivo é encurtar o texto EN de cada seção para que caiba no espaço JP alocado

**Estado atual: 125 de 125 seções cabem em EN. O T10 de encurtamento está concluído.**

---

## Restrições fundamentais

### Entradas são posicionais
Cada linha do script EN corresponde a uma **entrada fixa** no D00.DAT. O jogo acessa entradas por índice.
- **NUNCA adicionar ou remover linhas** — isso desalinha os índices e corrompe os diálogos
- Só é permitido modificar o **texto dentro** de cada entrada existente
- Linhas com `<$FFFF>` são nomes de personagens — geralmente intocáveis
- Linhas com `<$FFFE>` são terminadores de diálogo
- Linhas com `<$FFFC>` são quebras de linha (newline) — intermediárias
- Linhas com `<$FFFD>` são scroll — intermediárias

### Diff alvo
- `diff = Avail - EN_size` (calculado pelo `measure.py`)
- **Diff positivo** = cabe, há espaço sobrando
- **Diff negativo** = overflow, não cabe, precisa cortar
- **Alvo: diff entre 0 e +50** (idealmente +10 a +30)
- Se cortou demais (diff > +100), restaurar texto do Translation Guide
- **Objetivo real:** o ingles deve caber sem overflow de setor, mas sem perder informacao desnecessariamente
- **Texto muito menor que o necessario e defeito editorial**, nao vitoria tecnica

### Bigram encoding
O texto EN usa bigrams (2 chars por tile de 16x16). Cada char EN ocupa **~1 byte** após encoding.
Regra prática: **1 caractere adicionado/removido no script ≈ 1 byte no diff**.

---

## Ferramenta de medição: `measure.py`

```bash
# Medir seções específicas:
python3 measure.py scen038E scen083E scen023E

# Sem argumentos mede scen033E, scen035E, scen107E (default)
python3 measure.py
```

Saída:
```
scen038E: EN= 11364  Avail=  8768  Diff= -2596  [OVERFLOW]  (must cut ~2621 bytes)
```

**SEMPRE medir após cada lote de edições.** O ciclo é:
1. Editar 5-10 entradas
2. `python3 measure.py scenXXXE`
3. Se diff ainda negativo → continuar cortando
4. Se diff entre 0 e +50 → parar, rodar testes
5. Se diff > +100 → cortou demais, reverter ou expandir

---

## Técnicas de encurtamento

### O que cortar (prioridade)
1. **Filler words**: "Well, ", "Anyhow, ", "As a matter of fact", "You know", "I suppose"
2. **Contrações**: "I will" → "I'll", "do not" → "don't", "cannot" → "can't"
3. **Redundância**: "I don't think so, there must be a different reason" → "No, there must be another reason"
4. **Adjetivos desnecessários**: "an especially horrible death" → "a horrible death"
5. **Repetições dramáticas**: se duas entradas dizem a mesma coisa (variantes de escolha), ambas precisam caber
6. **Reformulação concisa**: manter a mesma ideia em menos palavras

### O que NUNCA cortar
1. **Nomes de personagens** (linhas `<$FFFF>`)
2. **Lore e informação de gameplay** — nomes de locais, itens, condições de vitória/derrota
3. **Personalidade dos personagens** — Do Kahni fala em terceira pessoa, Pierre é emotivo, Silver Wolf é cínico
4. **Falas de confissão de amor** (cenários 33/107) — são o coração emocional do jogo
5. **Control codes**: `<$FFFF>`, `<$FFFE>`, `<$FFFC>`, `<$FFFD>`, `<$FFFB>`, `<$F702>`, `<$F703>`, `[diehardt's name]`, `<$fe><$XX>`, `<$ff><$XX>`, `<$f6>`, `<$fc>`
6. **Informação que já existia na tradução EN e ainda cabe no orçamento final**

### Regra editorial central

- Corte apenas o necessario para eliminar overflow.
- Se a seção já cabe, pare.
- Se ficou muito menor que o necessario, restaure parte do texto.
- O alvo é **ingles completo que cabe**, não **ingles minimalista**.

### Exemplo prático

**Antes (verbose demais):**
```
Aren't you one of the Rigüler Generals?<$FFFE>
Right now I'm nothing of the like.<$FFFC>
My sword now is aimed at Altemüller, it is nothing short of a rebellion.<$FFFE>
```

**Depois (conciso, mesmo tom):**
```
Aren't you a Rigüler General?<$FFFE>
Not anymore.<$FFFC>
My sword is aimed at Altemüller now. This is a rebellion.<$FFFE>
```

Economia: ~50 chars ≈ ~50 bytes.

---

## Workflow passo-a-passo

### Para cada seção overflow:

```bash
# 1. Medir o overflow atual
python3 measure.py scen038E
# → scen038E: EN=11364  Avail=8768  Diff=-2596  [OVERFLOW]  (must cut ~2621 bytes)

# 2. Ler o script
# O arquivo está em scripts/en/scen038E.txt

# 3. Editar entradas — encurtar texto, medir a cada ~10 edições
# [fazer edições no arquivo]

python3 measure.py scen038E
# → continuar até diff entre 0 e +50

# 4. Rodar testes
pytest tests/ -q
# → 35 passed

# 5. Passar para a próxima seção
```

### Se cortou demais (diff > +100):
- Consultar o PDF `Langrisser III (Import) Translation Guide.pdf` (by Akari Dawn)
- O PDF tem o texto original completo da tradução, organizado por cenário
- Buscar no PDF pelo conteúdo do cenário (nomes de locais, personagens)
- Expandir entradas que foram cortadas demais, mantendo a posição
- Se o sentido empobreceu mesmo com diff aceitável, expandir do mesmo jeito

### Verificação após cada lote:
```bash
pytest tests/ -q   # deve passar 35 testes
python3 build.py   # deve completar sem erros (opcional, mais lento)
```

---

## Lista de 24 seções finais encurtadas

Todas ficaram no alvo `diff 0` a `+50`.

| Script | Diff final |
|--------|------------|
| scen038E | +32 |
| scen083E | +44 |
| scen023E | +4 |
| scen018E | +4 |
| scen020E | +30 |
| scen051E | +2 |
| scen013E | +10 |
| scen091E | +4 |
| scen016E | +14 |
| scen012E | +38 |
| scen040E | +30 |
| scen008E | +8 |
| scen030E | +2 |
| scen125E | +4 |
| scen002E | +48 |
| scen072E | +8 |
| scen004E | +10 |
| scen011E | +10 |
| scen019E | +44 |
| scen010E | +4 |
| scen015E | +42 |
| scen027E | +48 |
| scen109E | +48 |
| scen042E | +4 |

---

## Referência rápida de control codes

| Code | Significado | Editável? |
|------|-------------|-----------|
| `<$FFFF>` | Terminador (nome/label) | NAO |
| `<$FFFE>` | Fim de diálogo | NAO |
| `<$FFFC>` | Quebra de linha | NAO |
| `<$FFFD>` | Scroll (avança texto) | NAO |
| `<$FFFB>` | Pausa dramática | NAO |
| `[diehardt's name]` | Nome do protagonista | NAO |
| `<$F702>` a `<$F708>` | Efeitos especiais | NAO |
| `<$fe><$XX>` | Temporizadores | NAO |
| `<$ff><$XX>` | Efeitos de texto | NAO |
| `<$f6>...<$fc>` | Wrapper de narrador | NAO |
| `<<` (duplo) | Typo no original | Corrigir para `<` |

---

## Arquivos relevantes

| Arquivo | Descrição |
|---------|-----------|
| `scripts/en/scen???E.txt` | Scripts EN — UM POR CENARIO (125 total) |
| `measure.py` | Medir diff de seções específicas |
| `build.py` | Pipeline completo (gera ISO jogável) |
| `tests/` | 35 testes automatizados |
| `tools/d00_tools.py` | Parser/encoder D00.DAT |
| `Langrisser III (Import) Translation Guide.pdf` | Texto original da tradução (Akari Dawn) |
| `context.md` | Arquitetura e decisões técnicas |
| `todo.md` | Estado atual e tarefas pendentes |
