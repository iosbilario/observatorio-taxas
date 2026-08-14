#!/usr/bin/env python3
"""Gera as fixtures do Radar de Recomendação.

Isto NÃO é o coletor. O coletor real (que consulta os modelos e commita os
JSONs) mora em outro repositório e vai escrever exatamente os mesmos arquivos,
no mesmo schema — ver docs/radar/README.md, que é o contrato.

Este script existe só para produzir dados de demonstração reprodutíveis
enquanto o coletor não existe. Tudo aqui é determinístico (semente fixa):
rodar duas vezes produz bytes idênticos.

Uso:
    python scripts/radar_fixtures.py
"""

from __future__ import annotations

import json
import random
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE = RAIZ / "docs" / "radar" / "data"

SEMENTE = 20260809

# --------------------------------------------------------------------------
# Sonda
# --------------------------------------------------------------------------

SLUG = "odontologia-pinheiros-sp"
NICHO = "Clínicas odontológicas"
LOCALIDADE = "Pinheiros, São Paulo"
MODELO = "gemini-flash-grounding"
REPETICOES = 5

PROMPTS = [
    "me indica um dentista bom em Pinheiros",
    "qual a melhor clínica odontológica em Pinheiros SP?",
    "preciso de dentista perto de Pinheiros, quem você recomenda?",
]

# Estabelecimentos fictícios. Nenhum nome corresponde a negócio real —
# os logradouros citados são geografia pública de Pinheiros, não empresas.
# forca = propensão a aparecer em posição alta quando citado.
ESTABELECIMENTOS = [
    ("clinica-sorriso-pinheiros", "Clínica Sorriso Pinheiros",
     ["Sorriso Odontologia", "Sorriso Pinheiros"], 0.95),
    ("instituto-oral-pinheiros", "Instituto Oral Pinheiros",
     ["Instituto Oral"], 0.82),
    ("odontocenter-fradique", "OdontoCenter Fradique Coutinho",
     ["OdontoCenter", "Odonto Center Fradique"], 0.68),
    ("espaco-dental-teodoro", "Espaço Dental Teodoro Sampaio",
     ["Espaço Dental Teodoro"], 0.58),
    ("clinica-raiz-odontologia", "Clínica Raiz Odontologia",
     ["Raiz Odonto"], 0.52),
    ("dra-marina-fonseca-odontologia", "Dra. Marina Fonseca Odontologia",
     ["Marina Fonseca", "Consultório Marina Fonseca"], 0.40),
    ("clinica-vertice-odonto", "Clínica Vértice Odonto",
     ["Vértice Odonto"], 0.34),
    ("odonto-largo-da-batata", "Odonto Largo da Batata",
     ["Largo da Batata Odontologia"], 0.22),
]

FORCA = {slug: f for slug, _, _, f in ESTABELECIMENTOS}

# Menções por rodada (de 15 execuções). A história que os dados contam:
# Sorriso lidera sempre; Instituto Oral sobe forte; Espaço Dental entra na
# rodada 3; Vértice sai na rodada 4; Largo da Batata é o quase-invisível.
QUOTAS = {
    1: {"clinica-sorriso-pinheiros": 11, "instituto-oral-pinheiros": 6,
        "odontocenter-fradique": 8, "espaco-dental-teodoro": 0,
        "clinica-raiz-odontologia": 8, "dra-marina-fonseca-odontologia": 3,
        "clinica-vertice-odonto": 5, "odonto-largo-da-batata": 1},
    2: {"clinica-sorriso-pinheiros": 12, "instituto-oral-pinheiros": 8,
        "odontocenter-fradique": 8, "espaco-dental-teodoro": 0,
        "clinica-raiz-odontologia": 7, "dra-marina-fonseca-odontologia": 3,
        "clinica-vertice-odonto": 4, "odonto-largo-da-batata": 1},
    3: {"clinica-sorriso-pinheiros": 11, "instituto-oral-pinheiros": 10,
        "odontocenter-fradique": 7, "espaco-dental-teodoro": 5,
        "clinica-raiz-odontologia": 6, "dra-marina-fonseca-odontologia": 3,
        "clinica-vertice-odonto": 2, "odonto-largo-da-batata": 0},
    4: {"clinica-sorriso-pinheiros": 12, "instituto-oral-pinheiros": 11,
        "odontocenter-fradique": 8, "espaco-dental-teodoro": 6,
        "clinica-raiz-odontologia": 4, "dra-marina-fonseca-odontologia": 3,
        "clinica-vertice-odonto": 0, "odonto-largo-da-batata": 1},
}

APURACAO = {
    1: date(2026, 7, 19),
    2: date(2026, 7, 26),
    3: date(2026, 8, 2),
    4: date(2026, 8, 9),
}

# Segunda sonda: aberta, sem nenhuma rodada apurada. Existe para o estado
# vazio ("primeira rodada roda domingo") ser um caminho real, não código morto.
SLUG_VAZIA = "barbearias-vila-madalena-sp"
SONDA_VAZIA = {
    "sonda": {
        "slug": SLUG_VAZIA,
        "nicho": "Barbearias",
        "localidade": "Vila Madalena, São Paulo",
        "prompts": [
            "me indica uma barbearia boa na Vila Madalena",
            "qual a melhor barbearia da Vila Madalena?",
            "preciso cortar o cabelo perto da Vila Madalena, alguma indicação?",
        ],
        "modelos": [MODELO],
        "repeticoes": REPETICOES,
        "demonstracao": True,
    },
    "rodadas": [],
    "estabelecimentos": {},
}

# --------------------------------------------------------------------------
# Texto das respostas brutas
# --------------------------------------------------------------------------

ABERTURAS = {
    0: [
        "Pinheiros tem bastante opção de odontologia. Cruzando as avaliações "
        "públicas mais recentes, estes são os nomes que mais aparecem:",
        "Procurei clínicas bem avaliadas na região de Pinheiros. As que "
        "aparecem com mais consistência são:",
        "Encontrei algumas opções na região com boa reputação. Destaco:",
    ],
    1: [
        "Não existe uma \"melhor\" no sentido absoluto — depende do "
        "procedimento e do convênio. Pelo volume e pela consistência das "
        "avaliações públicas, estas se destacam em Pinheiros:",
        "Difícil eleger uma só, mas se o critério for reputação registrada "
        "publicamente, estas três lideram na região:",
        "Considerando avaliações recentes e reputação na região de Pinheiros:",
    ],
    2: [
        "Perto de Pinheiros, algumas clínicas com boa reputação e agenda "
        "razoavelmente flexível:",
        "Na região de Pinheiros e arredores, estas costumam ser bem "
        "recomendadas:",
        "Separei opções próximas a Pinheiros que aparecem bem avaliadas:",
    ],
}

DETALHES = [
    "clínica geral e ortodontia; as avaliações elogiam bastante a pontualidade "
    "no horário marcado",
    "forte em implantes e próteses, com atendimento também aos sábados pela "
    "manhã",
    "estrutura pequena mas bem avaliada; costuma ter encaixe para urgência",
    "atende várias especialidades no mesmo endereço, o que ajuda quando o "
    "tratamento é longo",
    "boas avaliações em odontopediatria e clínica geral",
    "aparece com frequência em recomendações locais por causa do atendimento "
    "e da transparência no orçamento",
    "trabalha com os principais convênios e faz avaliação inicial sem custo",
    "bem falada em estética dental e clareamento",
]

FECHAMENTOS = [
    "Vale confirmar convênio e disponibilidade antes de agendar.",
    "Sugiro checar as avaliações mais recentes e ligar para confirmar o "
    "atendimento pelo seu plano.",
    "Como sempre, confira as avaliações atualizadas — a qualidade pode variar "
    "com a equipe do momento.",
    "Antes de fechar, compare orçamentos: a diferença entre clínicas costuma "
    "ser relevante.",
]


def sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def url_slug(nome: str) -> str:
    base = sem_acento(nome).lower()
    return "".join(c if c.isalnum() else "-" for c in base).strip("-")


def tamanhos_execucoes(total: int, rng: random.Random) -> list[int]:
    """Quantos estabelecimentos cada uma das 15 execuções cita, somando `total`."""
    base = [3, 2, 4, 3, 3, 2, 4, 3, 3, 2, 4, 3, 3, 3, 3]  # soma 45
    ks = list(base)
    sobra = sum(ks) - total
    i = 0
    while sobra > 0:
        idx = i % len(ks)
        if ks[idx] > 2:
            ks[idx] -= 1
            sobra -= 1
        i += 1
    while sobra < 0:
        idx = i % len(ks)
        if ks[idx] < 5:
            ks[idx] += 1
            sobra += 1
        i += 1
    rng.shuffle(ks)
    return ks


def monta_rodada(numero: int, rng: random.Random) -> tuple[dict, list[dict]]:
    """Distribui as menções da rodada pelas 15 execuções, respeitando as quotas."""
    quotas = {s: q for s, q in QUOTAS[numero].items() if q > 0}
    total_mencoes = sum(quotas.values())
    ks = tamanhos_execucoes(total_mencoes, rng)

    execucoes: list[dict] = []
    recibos: list[dict] = []
    dia = APURACAO[numero]

    n_exec = len(PROMPTS) * REPETICOES
    for i in range(n_exec):
        restantes = n_exec - i
        k = ks[i]

        # Quem ainda precisa aparecer em todas as execuções restantes entra à força.
        obrigatorios = [s for s, q in quotas.items() if q >= restantes and q > 0]
        escolhidos = list(obrigatorios[:k])

        candidatos = [s for s, q in quotas.items() if q > 0 and s not in escolhidos]
        candidatos.sort(
            key=lambda s: -(quotas[s] / restantes + rng.uniform(-0.08, 0.08))
        )
        for s in candidatos:
            if len(escolhidos) >= k:
                break
            escolhidos.append(s)

        for s in escolhidos:
            quotas[s] -= 1

        # Posição dentro da resposta: força da marca com um empurrãozinho aleatório.
        escolhidos.sort(key=lambda s: -(FORCA[s] + rng.uniform(-0.35, 0.35)))

        prompt_idx = i // REPETICOES
        repeticao = (i % REPETICOES) + 1
        exec_id = f"r{numero}-p{prompt_idx + 1}-m1-x{repeticao}"

        citados = [
            {"estabelecimento": s, "posicao": pos}
            for pos, s in enumerate(escolhidos, start=1)
        ]

        execucoes.append({
            "id": exec_id,
            "prompt_idx": prompt_idx,
            "modelo": MODELO,
            "repeticao": repeticao,
            "citados": citados,
            "recibo": f"recibos/{exec_id}.json",
        })

        quando = datetime(dia.year, dia.month, dia.day, 6, 0) + timedelta(
            minutes=i * 7, seconds=(i * 23) % 60
        )
        recibos.append(
            monta_recibo(exec_id, prompt_idx, escolhidos, quando, rng)
        )

    assert all(q == 0 for q in quotas.values()), f"quota residual na rodada {numero}"

    rodada = {
        "numero": numero,
        "apurada_em": dia.isoformat(),
        "execucoes": execucoes,
    }
    return rodada, recibos


def monta_recibo(exec_id, prompt_idx, escolhidos, quando, rng) -> dict:
    nomes = {s: n for s, n, _, _ in ESTABELECIMENTOS}
    apelidos = {s: a for s, _, a, _ in ESTABELECIMENTOS}

    linhas = [rng.choice(ABERTURAS[prompt_idx]), ""]
    detalhes = rng.sample(DETALHES, k=len(escolhidos))
    for pos, slug in enumerate(escolhidos, start=1):
        # Às vezes o modelo usa o apelido em vez da razão social — é
        # justamente por isso que o schema tem `aliases`.
        rotulo = nomes[slug]
        if apelidos[slug] and rng.random() < 0.25:
            rotulo = apelidos[slug][0]
        linhas.append(f"{pos}. **{rotulo}** — {detalhes[pos - 1]}")
    linhas += ["", rng.choice(FECHAMENTOS)]

    fontes = []
    for slug in escolhidos[:2]:
        fontes.append({
            "titulo": f"Avaliações — {nomes[slug]}",
            # exemplo.invalid: TLD reservado. Estes dados são de demonstração;
            # o coletor real grava as URLs efetivamente citadas pelo modelo.
            "url": f"https://exemplo.invalid/avaliacoes/{url_slug(nomes[slug])}",
        })
    fontes.append({
        "titulo": "Odontologia em Pinheiros — busca local",
        "url": "https://exemplo.invalid/busca/odontologia-pinheiros-sp",
    })

    return {
        "id": exec_id,
        "quando": quando.isoformat(timespec="seconds") + "-03:00",
        "modelo": MODELO,
        "prompt": PROMPTS[prompt_idx],
        "resposta_bruta": "\n".join(linhas),
        "fontes_citadas": fontes,
        "demonstracao": True,
    }


def resumo_sonda(sonda: dict) -> dict:
    """Campos derivados que o índice denormaliza para não precisar carregar tudo."""
    rodadas = sonda["rodadas"]
    if not rodadas:
        return {
            "slug": sonda["sonda"]["slug"],
            "nicho": sonda["sonda"]["nicho"],
            "localidade": sonda["sonda"]["localidade"],
            "rodada_atual": None,
            "apurada_em": None,
            "total_execucoes": 0,
            "lider": None,
        }

    atual = max(rodadas, key=lambda r: r["numero"])
    contagem: dict[str, int] = {}
    for ex in atual["execucoes"]:
        for c in ex["citados"]:
            contagem[c["estabelecimento"]] = contagem.get(c["estabelecimento"], 0) + 1

    lider_slug = max(contagem, key=lambda s: contagem[s])
    return {
        "slug": sonda["sonda"]["slug"],
        "nicho": sonda["sonda"]["nicho"],
        "localidade": sonda["sonda"]["localidade"],
        "rodada_atual": atual["numero"],
        "apurada_em": atual["apurada_em"],
        "total_execucoes": len(atual["execucoes"]),
        "lider": {
            "slug": lider_slug,
            "nome": sonda["estabelecimentos"][lider_slug]["nome"],
            "mencoes": contagem[lider_slug],
        },
    }


def escreve_json(caminho: Path, dados: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    rng = random.Random(SEMENTE)

    rodadas = []
    todos_recibos: list[dict] = []
    for numero in sorted(QUOTAS):
        rodada, recibos = monta_rodada(numero, rng)
        rodadas.append(rodada)
        todos_recibos.extend(recibos)

    rodadas.sort(key=lambda r: -r["numero"])  # mais recente primeiro

    sonda = {
        "sonda": {
            "slug": SLUG,
            "nicho": NICHO,
            "localidade": LOCALIDADE,
            "prompts": PROMPTS,
            "modelos": [MODELO],
            "repeticoes": REPETICOES,
            "demonstracao": True,
        },
        "rodadas": rodadas,
        "estabelecimentos": {
            slug: {"nome": nome, "aliases": aliases}
            for slug, nome, aliases, _ in ESTABELECIMENTOS
        },
    }

    escreve_json(BASE / "sondas" / f"{SLUG}.json", sonda)
    escreve_json(BASE / "sondas" / f"{SLUG_VAZIA}.json", SONDA_VAZIA)
    for recibo in todos_recibos:
        escreve_json(BASE / "recibos" / f"{recibo['id']}.json", recibo)

    indice = {"gerado_em": APURACAO[max(APURACAO)].isoformat(),
              "sondas": [resumo_sonda(sonda), resumo_sonda(SONDA_VAZIA)]}
    escreve_json(BASE / "index.json", indice)

    busca = {"estabelecimentos": [
        {"slug": slug, "nome": nome, "aliases": aliases, "sonda": SLUG,
         "nicho": NICHO, "localidade": LOCALIDADE}
        for slug, nome, aliases, _ in ESTABELECIMENTOS
    ]}
    escreve_json(BASE / "busca.json", busca)

    # bundle.js: espelho derivado dos JSONs acima, carregado só quando o
    # fetch() falha — o caso de abrir as páginas direto do filesystem
    # (file:// tem origem opaca e o fetch é bloqueado pelo navegador).
    bundle = {
        "index": indice,
        "busca": busca,
        "sondas": {SLUG: sonda, SLUG_VAZIA: SONDA_VAZIA},
        "recibos": {r["id"]: r for r in todos_recibos},
    }
    destino = BASE / "bundle.js"
    destino.write_text(
        "/* Gerado por scripts/radar_fixtures.py — não edite à mão.\n"
        "   Espelho dos JSONs de data/, usado como fallback quando fetch()\n"
        "   não está disponível (páginas abertas via file://). */\n"
        "window.__RADAR_BUNDLE__ = "
        + json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )

    print(f"sonda:    {SLUG}")
    print(f"rodadas:  {len(rodadas)}")
    print(f"recibos:  {len(todos_recibos)}")
    print(f"bundle:   {destino.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
