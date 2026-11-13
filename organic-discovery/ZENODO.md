# Zenodo: arquivamento e DOI

O Zenodo arquiva cada release publicada no GitHub e emite dois tipos de DOI:

- **DOI da versão:** identifica exatamente uma release (por exemplo, v1.6.0).
  Use para citar um resultado reproduzível.
- **DOI conceito (todas as versões):** aponta sempre para a versão mais recente.
  Use para citar o projeto de forma geral.

| DOI | Valor | Registro |
| --- | --- | --- |
| Conceito (todas as versões) | [10.5281/zenodo.24151062](https://doi.org/10.5281/zenodo.24151062) | sempre resolve para a versão mais recente |
| Versão v1.8.0 | [10.5281/zenodo.24208300](https://doi.org/10.5281/zenodo.24208300) | [zenodo.org/records/24208300](https://zenodo.org/records/24208300) |
| Versão v1.7.0 | [10.5281/zenodo.24195784](https://doi.org/10.5281/zenodo.24195784) | [zenodo.org/records/24195784](https://zenodo.org/records/24195784) |
| Versão v1.6.0 | [10.5281/zenodo.24151063](https://doi.org/10.5281/zenodo.24151063) | [zenodo.org/records/24151063](https://zenodo.org/records/24151063) |

## Situação (13/11/2026)

| Item | Estado |
| --- | --- |
| Integração GitHub–Zenodo | Ligada pelo proprietário |
| Primeira release arquivada | v1.6.0, publicada no GitHub em 12/11/2026 no commit `300c48a4` ([notas](RELEASE-v1.6.0.md)) |
| Registro no Zenodo | Conferido pela API (`/api/records/24151063`): título "Observatório de Taxas", versão v1.6.0, tipo Software, licença MIT, criador "Pereira, Leandro Borges", um arquivo `iosbilario/observatorio-taxas-v1.6.0.zip` de 1.063.032 bytes, relacionado a `tree/v1.6.0` |
| Segunda release arquivada | v1.7.0 (servidor MCP), publicada no GitHub em 13/11/2026 no commit `a286ffae` ([notas](RELEASE-v1.7.0.md)) |
| Registro da v1.7.0 | Conferido pela API (`/api/records/24195784`): título "Observatório de Taxas", versão v1.7.0, tipo Software, licença MIT, criador "Pereira, Leandro Borges", DOI conceito 10.5281/zenodo.24151062, um arquivo `iosbilario/observatorio-taxas-v1.7.0.zip` de 1.169.276 bytes |
| Terceira release arquivada | v1.8.0 (indicadores, comparador, simulador de CDI), publicada no GitHub em 13/11/2026 no commit `af433151` ([notas](RELEASE-v1.8.0.md)), registro `/api/records/24208300` conferido |
| Releases anteriores | v1.0.0 a v1.5.0, sem DOI (publicadas antes da integração) |

A busca textual da API (`/api/records?q=...`) demorou a indexar o registro
novo; a consulta direta pelo id respondeu logo após a publicação.

## O que é depositado

A integração baixa o **source archive** que o GitHub gera para a tag da
release (o mesmo "Source code (zip)" da página da release). Arquivos anexados
manualmente à release ("assets") não substituem esse arquivo.

O GitHub gera o source archive com `git archive`, que respeita o
[`.gitattributes`](../.gitattributes). Os caminhos marcados com
`export-ignore` contêm valores de séries de terceiros e ficam fora:

| Fora do depósito | Motivo |
| --- | --- |
| `data/`, `docs/data/` | Séries do IBGE (IPCA, INPC, desocupação) e da FGV IBRE (IGP-M, IGP-DI) junto com as do BCB |
| `docs/reajuste/`, `docs/correcao/` | Páginas geradas com esses valores |
| `CHANGELOG.md` | Registro de mudanças de valores das séries |
| `tests/fixtures/valores_baseline.json` | Acumulados derivados das séries |

Conferido em 12/11/2026 baixando o source archive real da `main`
(`https://github.com/iosbilario/observatorio-taxas/archive/refs/heads/main.zip`):
93 arquivos, 1,05 MB, nenhum dos caminhos acima. O site em produção não muda:
`export-ignore` só afeta o pacote, não o repositório nem o GitHub Pages.

### Por que os dados ficam fora

| Fonte | Termos verificados | Conclusão para o depósito |
| --- | --- | --- |
| Banco Central (Selic, TR, poupança, câmbio, IBC-Br) | Publicadas no Portal de Dados Abertos do BCB sob ODbL 1.0 | Redistribuíveis com atribuição e compartilhamento pela mesma licença; não sob MIT |
| IBGE (IPCA, INPC, PNAD) | Séries não aparecem com licença no portal do BCB; o portal do IBGE bloqueia leitura automatizada e a página de termos não traz cláusula de reutilização legível | Sem autorização clara verificada para redistribuir sob MIT |
| FGV IBRE (IGP-M, IGP-DI) | Os termos do portal da FGV IBRE proíbem reproduzir conteúdo do portal sem autorização | Sem autorização clara; não depositar |

O depósito recebe uma única licença (MIT, do `CITATION.cff`). Incluir os dados
rotularia como MIT séries que não são MIT. Detalhes por série em
[`LICENSE-DADOS.md`](../LICENSE-DADOS.md).

**Arquivar as séries do BCB à parte (opcional, futuro):** um depósito Zenodo
separado, do tipo dataset, sob ODbL 1.0, só com as séries do Banco Central.
Não faz parte desta release.

## Como acompanhar o arquivamento

Depois de publicar a release no GitHub:

1. Em [zenodo.org/account/settings/github](https://zenodo.org/account/settings/github/),
   o repositório mostra a release e o status do depósito (normalmente em minutos).
2. Pela API pública, sem login:

   ```bash
   curl -s "https://zenodo.org/api/records?q=%22observatorio-taxas%22&sort=mostrecent" \
     | python -c "import json,sys; [print(h['doi'], h['metadata']['version']) for h in json.load(sys.stdin)['hits']['hits']]"
   ```

3. Conferir no registro: título, criador "Pereira, Leandro Borges", licença
   MIT, versão igual à tag e lista de arquivos (sem `data/`).
4. Anotar o DOI da versão e o DOI conceito (aparece como "Cite all versions").

**Se o depósito não aparecer em 1 hora:** a página de configuração do GitHub no
Zenodo mostra o erro. Causas comuns: `CITATION.cff` inválido (validar com
`cffconvert --validate -i CITATION.cff`), release publicada antes de ligar o
repositório, ou release marcada como pre-release/draft. Corrigir e publicar uma
nova release (por exemplo v1.6.1), em vez de mexer na tag já publicada.

## Metadados

Fonte única: [`CITATION.cff`](../CITATION.cff). Não há `.zenodo.json`; se um
for criado, o Zenodo passa a ignorar o `CITATION.cff`. Campos usados pelo
Zenodo: `title`, `version`, `license`, `type`, `abstract`, `message`,
`authors` e `keywords`.

```bash
pip install cffconvert
cffconvert --validate -i CITATION.cff
cffconvert -i CITATION.cff -f zenodo     # prévia do que o Zenodo vai registrar
```

## A cada release

1. No PR da release: `version` e `date-released` no `CITATION.cff` iguais à
   tag e ao dia da publicação; notas em `organic-discovery/RELEASE-vX.Y.Z.md`.
2. `cffconvert --validate`, testes e conferência do source archive
   (`git archive --format=zip HEAD | unzip -l /dev/stdin` ou o teste
   `tests/test_zenodo.py`).
3. Merge, criar a tag `vX.Y.Z` no commit aprovado e publicar a release (não
   draft, não pre-release).
4. Acompanhar o depósito (seção acima).

## Depois de cada nova release

- O DOI conceito não muda; o badge do README usa ele.
- Acrescentar o DOI da versão nova em `identifiers` no `CITATION.cff` e na
  tabela acima, num PR depois que o Zenodo emitir o registro.
