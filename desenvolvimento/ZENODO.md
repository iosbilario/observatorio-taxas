# Zenodo: DOI e citação de versões

O Zenodo arquiva cada release publicada no GitHub e atribui um DOI à versão,
mais um DOI "conceito" que sempre aponta para a versão mais recente.

## O que vai para o arquivo

O Zenodo recebe o zip da release, que o GitHub gera com `git archive`. O
[`.gitattributes`](../.gitattributes) marca como `export-ignore` tudo o que
contém valores de séries de terceiros:

| Fora do arquivo | Motivo |
| --- | --- |
| `data/`, `docs/data/` | Séries do IBGE e da FGV IBRE junto com as do BCB; termos diferentes da MIT |
| `docs/reajuste/`, `docs/correcao/` | Páginas geradas com os valores dessas séries |
| `CHANGELOG.md` | Registro de mudanças de valores das séries |
| `tests/fixtures/valores_baseline.json` | Acumulados publicados, derivados das séries |

Fica no arquivo o software: `scripts/`, `tests/` (sem a fixture de valores),
`.github/`, `config.yml`, `partials/`, as páginas escritas à mão em `docs/`,
`assets/`, a documentação, `LICENSE`, `LICENSE-DADOS.md` e `CITATION.cff`.
Medido em 12/11/2026: 109 arquivos, 1,0 MB (o zip completo tinha 5,7 MB).

Esses arquivos continuam no repositório, no site e no histórico do Git. A
exclusão vale só para o pacote arquivado. Algumas telas incluídas (a captura do
README, o card social, o boletim da página inicial) mostram poucos valores do
dia como ilustração, não como conjunto de dados.

**Reproduzir os dados de uma versão:** clonar o repositório, `git checkout
vX.Y.Z` (os dados da data estão no Git) ou rodar `python scripts/backfill.py`
e o pipeline do [guia](GUIA.md) para buscá-los de novo no SGS. O SGS pode ter
revisado valores depois; a tag é a referência exata.

## Metadados

Fonte única: [`CITATION.cff`](../CITATION.cff) (não há `.zenodo.json`; se um
for criado, o Zenodo passa a ignorar o `CITATION.cff`). Campos lidos pelo
Zenodo: `title`, `version`, `license`, `type`, `abstract`, `message`,
`authors` (`given-names`, `family-names`, `affiliation`, `orcid`) e `keywords`.

Validar antes de cada release:

```bash
pip install cffconvert
cffconvert --validate -i CITATION.cff
cffconvert -i CITATION.cff -f zenodo     # prévia do que o Zenodo vai registrar
```

Não preencher `doi` nem `identifiers` antes de o Zenodo emitir o DOI. Um ORCID
só entra se o autor tiver um e quiser associá-lo.

## Ativar a integração (uma vez)

1. Entrar em [zenodo.org](https://zenodo.org/) com a conta do GitHub `iosbilario`.
2. **Account → GitHub**: sincronizar e ligar o repositório `iosbilario/observatorio-taxas`.
3. Conferir que o repositório continua público (o Zenodo só acessa repositórios públicos).

Releases anteriores à ativação (v1.0.0 a v1.5.0) não são arquivadas. O
primeiro DOI será o da próxima release.

## A cada release

1. No mesmo PR da release, atualizar `version` e `date-released` no `CITATION.cff`.
2. Rodar `cffconvert --validate` e os testes.
3. Merge, criar a tag `vX.Y.Z` e publicar a release no GitHub.
4. Conferir no Zenodo o depósito novo: criador, licença MIT, versão e lista de arquivos.
5. Depois do primeiro DOI: acrescentar ao `CITATION.cff` o DOI conceito em
   `identifiers` (tipo `doi`) e o badge/link no README, num PR próprio.

## Como citar

Antes do DOI, o GitHub mostra a citação gerada pelo `CITATION.cff`:

> Pereira, L. B. (2026). *Observatório de Taxas* (versão 1.5.0) [Software]. https://github.com/iosbilario/observatorio-taxas

Depois do DOI, cite a versão usada pelo DOI da versão, e o produtor de cada
índice usado (ver [`LICENSE-DADOS.md`](../LICENSE-DADOS.md)).
