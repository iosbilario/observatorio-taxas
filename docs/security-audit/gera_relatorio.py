# -*- coding: utf-8 -*-
"""
gera_relatorio.py — Gera docs/security-audit/relatorio-auditoria-seguranca.pdf.

Relatório da auditoria de segurança de 31/08/2026 (5 categorias adaptadas à
stack: site estático GitHub Pages + geradores Python + GitHub Actions).

Uso (ambiente isolado, nada global):
    python -m venv venv-audit
    venv-audit/Scripts/pip install reportlab matplotlib
    venv-audit/Scripts/python docs/security-audit/gera_relatorio.py

Os achados estão declarados em ACHADOS/PONTOS_FORTES/ISSUES abaixo — edite lá
e rode de novo para regerar.
"""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, PageBreak, PageTemplate, Paragraph, Spacer,
    Table, TableStyle,
)

AQUI = Path(__file__).resolve().parent
SAIDA = AQUI / "relatorio-auditoria-seguranca.pdf"

TITULO = "Relatório de Auditoria de Segurança — Observatório de Taxas"
DATA = date(2026, 8, 31).strftime("%d/%m/%Y")

# Paleta pedida
COR = {
    "critica": colors.HexColor("#B91C1C"),
    "alta": colors.HexColor("#EA580C"),
    "media": colors.HexColor("#D97706"),
    "baixa": colors.HexColor("#2563EB"),
    "informativa": colors.HexColor("#6B7280"),
    "forte": colors.HexColor("#059669"),
    "tinta": colors.HexColor("#1F2430"),
    "mut": colors.HexColor("#5B6472"),
    "linha": colors.HexColor("#D8DCE3"),
    "fundo": colors.HexColor("#F4F5F7"),
}
ROTULO_SEV = {"critica": "CRÍTICA", "alta": "ALTA", "media": "MÉDIA",
              "baixa": "BAIXA", "informativa": "INFORMATIVA"}

# --------------------------------------------------------------------------- #
# Conteúdo da auditoria
# --------------------------------------------------------------------------- #

ESCOPO = (
    "Repositório iosbilario/observatorio-taxas, branch desliga-radar (HEAD 4e5de0b), "
    "auditado em 31/08/2026. Cobertura: scripts Python de coleta e geração "
    "(scripts/*.py, 10 arquivos), workflow de CI (.github/workflows/monitor.yml, "
    "dependabot.yml), configuração (config.yml, requirements.txt, .claude/*), todas as "
    "páginas HTML/JS servidas em docs/ (landing, embed, var, rebobinar, retransmissora, "
    "admin, correcao/*, reajuste/*, radar/* + radar.js), robots.txt, SECURITY.md e o "
    "histórico git completo (varredura de padrões de segredo em todas as revisões)."
)

METODOLOGIA = [
    ("1. Banco sem tranca (isolamento de inquilino/dono)",
     "A stack não tem banco de dados, backend nem sessões: é um site 100% estático no "
     "GitHub Pages, alimentado por robô (GitHub Actions) que commita JSONs públicos. "
     "Não existe mecanismo de isolamento a auditar — categoria NÃO APLICÁVEL. "
     "O SECURITY.md já prescreve RLS insert-only para o futuro backend Supabase "
     "(palpite.html), registrado como ponto forte."),
    ("2. Permissão definida no navegador",
     "Sem servidor, não há endpoint privilegiado a cruzar com a UI. O equivalente na "
     "stack é o painel /admin/: página 'interna' protegida apenas por obscuridade "
     "(noindex + robots.txt). Foi auditado o que ela expõe e como."),
    ("3. IDOR",
     "Não há rotas de backend nem objetos por dono: todos os handlers de 'dados' são "
     "fetches de JSON estático público por desenho (dados oficiais do BACEN). "
     "Percorridos todos os pontos de fetch do frontend — nenhum acessa recurso "
     "sensível parametrizado. Categoria NÃO APLICÁVEL."),
    ("4. Chaves expostas (hardcode)",
     "Mapeado para: código-fonte, config.yml, workflow do Actions, .claude/, "
     "docs/ servido (bundle do 'frontend') e histórico git completo (git grep em todas "
     "as revisões por sk-ant-, ghp_, AKIA, chaves privadas, etc.). Auditados também os "
     "defaults e o manuseio de secrets no CI."),
    ("5. Inputs sem tratamento (XSS)",
     "Stack: JavaScript vanilla com innerHTML — todos os 100+ pontos de innerHTML "
     "foram enumerados e cada interpolação rastreada até a origem (URLSearchParams, "
     "location.hash, JSONs de dados, API do GoatCounter). Verificada a função esc() de "
     "cada página, as allowlists de parâmetros e as CSPs por página."),
]

# (sev, arquivo:linha, titulo, descricao, exploravel, condicao)
ACHADOS = [
    dict(
        id="A1", sev="media", cat="5. XSS",
        onde="docs/radar/radar.js:352",
        titulo="href de fontes citadas aceita URL javascript:",
        trecho='return \'<li><a href="\' + esc(f.url) + \'" target="_blank" ...',
        desc=(
            "fontesHTML() monta links com esc(f.url). esc() escapa &<>\"' — impede "
            "quebrar o atributo — mas não valida o ESQUEMA da URL: um valor "
            "javascript:... vira link executável ao clique (a CSP das páginas do Radar "
            "tem 'unsafe-inline', que também libera URLs javascript:). O campo "
            "fontes_citadas dos recibos virá de respostas de modelos de IA coletadas "
            "pelo futuro coletor — conteúdo de terceiros, influenciável por quem "
            "otimiza páginas para ser citado por IA."),
        cond=(
            "Hoje os recibos são fixtures commitadas (exemplo.invalid) e o Radar está "
            "fora do menu/sitemap — não explorável no estado atual. Torna-se "
            "explorável assim que o coletor real passar a escrever recibos com fontes "
            "vindas dos modelos."),
    ),
    dict(
        id="A2", sev="media", cat="4. Chaves/supply chain",
        onde="requirements.txt:1-3 · .github/workflows/monitor.yml:44,50",
        titulo="Dependências sem pinagem instaladas em job com permissão de escrita",
        trecho="requests\npyyaml\npillow   (sem versão nem hash)",
        desc=(
            "O job do cron instala requests, pyyaml, pillow (e anthropic, quando há "
            "chave) sempre na última versão publicada, sem pin nem --require-hashes. "
            "O mesmo job tem permissions: contents: write e os secrets no ambiente: "
            "uma release maliciosa no PyPI executaria com poder de commitar no repo e "
            "ler ANTHROPIC_API_KEY / GOATCOUNTER_TOKEN. Contrasta com o zelo do resto "
            "do projeto (Actions pinadas por SHA, SRI no CDN). O Dependabot está "
            "configurado para pip, mas sem versões pinadas ele não tem o que atualizar."),
        cond="Requer comprometimento de pacote no PyPI (supply chain) — probabilidade "
             "baixa, impacto alto.",
    ),
    dict(
        id="A3", sev="baixa", cat="4. Chaves/supply chain",
        onde=".github/workflows/monitor.yml:29-31",
        titulo="Secrets expostos como env do job inteiro",
        trecho="env:\n  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}\n  GOATCOUNTER_TOKEN: ${{ secrets.GOATCOUNTER_TOKEN }}",
        desc=(
            "As duas chaves ficam no ambiente de TODOS os steps — inclusive pip "
            "install e os geradores de página que não precisam delas. Qualquer código "
            "executado em qualquer step (ver A2) consegue lê-las. O escopo correto é "
            "por step: ANTHROPIC_API_KEY só em fetch.py, GOATCOUNTER_TOKEN só em "
            "fetch_stats.py (o if: env.X != '' pode ser resolvido com um step curto "
            "que publica um output)."),
        cond="Só vira vazamento combinado com execução de código no job (A2).",
    ),
    dict(
        id="A4", sev="baixa", cat="5. XSS (defesa em profundidade)",
        onde="docs/index.html:8 · docs/admin/index.html:8 · docs/embed.html:10 · demais páginas",
        titulo="CSP com script-src 'unsafe-inline' em todas as páginas",
        trecho="script-src 'self' 'unsafe-inline' https://gc.zgo.at",
        desc=(
            "Toda página libera script inline irrestrito, então a CSP não bloqueia "
            "injeção de <script> nem URLs javascript: — a proteção anti-XSS fica "
            "inteiramente na disciplina do esc() (que hoje é consistente). Como o site "
            "usa scripts inline por desenho (sem build), o endurecimento viável é CSP "
            "por hash (sha256 dos blocos inline, gerado pelos builders) ou externar os "
            "scripts. O guard anti-clickjacking via JS (if top!==self) também é "
            "contornável por iframe sandbox — limitação conhecida de site sem headers."),
        cond="Sem efeito isolado; reduz a margem de erro caso um esc() seja esquecido "
             "no futuro.",
    ),
    dict(
        id="A5", sev="informativa", cat="2. Permissão no navegador",
        onde="docs/admin/index.html · docs/robots.txt:3",
        titulo="Painel /admin/ público, protegido só por obscuridade (decisão documentada)",
        trecho="Disallow: /admin/",
        desc=(
            "O painel de acessos é acessível a qualquer pessoa que conheça a URL — e o "
            "robots.txt anuncia o caminho. Não há dado pessoal: só contagens agregadas "
            "do GoatCounter, e o docs/data/stats.json que o alimenta já é público de "
            "qualquer forma. O próprio HTML documenta a decisão (nota de segurança "
            "correta: senha em JS seria teatro) e aponta o caminho certo se um dia "
            "precisar de sigilo real. Registrado para visibilidade, sem ação exigida."),
        cond="Aceitável enquanto stats.json contiver apenas agregados.",
    ),
]

PONTOS_FORTES = [
    ("Escape de saída consistente (anti-XSS)",
     "Todos os ~100 usos de innerHTML interpolando dado dinâmico passam por esc() "
     "(&<>\"') ou recebem apenas números formatados — verificado página a página "
     "(index, embed, var, rebobinar, admin, correcao/*, reajuste/*, radar/*)."),
    ("Allowlist rigorosa de parâmetros de URL",
     "var.html:295-309 valida cada parâmetro (s contra códigos conhecidos, op/cmp por "
     "enum, datas por regex, sha por ^[0-9a-f]{7,40}$) e DESCARTA o inválido. "
     "embed.html:122-128 idem (Number(), regex aaaa-mm, enum de tema). sonda.html usa "
     "o slug só em fetch same-origin e textContent."),
    ("Dados de terceiros escapados no painel admin",
     "Os paths vindos da API do GoatCounter (manipuláveis por qualquer visitante que "
     "forje pageviews) são renderizados com esc(pathCurto(...)) em "
     "docs/admin/index.html:178 — o vetor de data poisoning → XSS está fechado."),
    ("Nenhum segredo hardcoded — código, configs e histórico git",
     "git grep em TODAS as revisões por padrões de chave (sk-ant-, ghp_, github_pat_, "
     "AKIA, xox*, BEGIN PRIVATE KEY): zero ocorrências. Secrets só via GitHub Actions "
     "secrets; goatcounter_code em config.yml é identificador público por desenho, "
     "documentado como tal."),
    ("Supply chain do frontend e do CI acima da média",
     "Actions pinadas por SHA de commit (monitor.yml:35,39); Chart.js pinado por "
     "versão exata com SRI + crossorigin (admin/index.html:32-34); Dependabot semanal "
     "para pip e github-actions; fontes self-hosted."),
    ("Parsing seguro nos coletores Python",
     "yaml.safe_load em todos os pontos (fetch.py:52, fetch_stats.py:62, builders); "
     "HTTPS em todas as chamadas; timeouts; falha de série não derruba o job; "
     "fetch_stats.py não sobrescreve stats.json bom quando a API falha."),
    ("CSP por página + higiene de links",
     "Toda página define CSP via meta (default-src 'self', object-src 'none', "
     "base-uri 'self'), referrer strict-origin-when-cross-origin, guard anti-frame "
     "(exceto embed.html, embutível por produto e documentado), e "
     "rel=\"noopener noreferrer\" em todo target=_blank."),
    ("SECURITY.md vivo e correto",
     "Política publicada com regras vigentes (escape, allowlist, CSP, supply chain), "
     "canal de reporte + .well-known/security.txt, e regras já escritas para o futuro "
     "backend Supabase: service key só no Actions, RLS insert-only para anon, CHECK "
     "de faixa no banco."),
    ("Admin sem dado pessoal",
     "O pipeline de estatísticas só grava agregados (totais, grupos, top páginas, "
     "série diária) — nada de IP, user-agent ou identificador de visitante."),
]

RECOMENDACOES = [
    ("P1", "Pinar dependências do CI (versões exatas + pip --require-hashes; "
           "pip-compile gera o lock) e escopar os secrets por step em monitor.yml — "
           "fecha A2 e A3 de uma vez, sem mudar comportamento."),
    ("P2", "Antes de ligar o coletor real do Radar: validar esquema de URL em "
           "fontesHTML (permitir só http(s), senão renderizar como texto) — fecha A1 "
           "no contrato de dados, não na sorte."),
    ("P3", "Endurecer a CSP das páginas de maior tráfego trocando 'unsafe-inline' por "
           "hashes sha256 gerados pelos builders (começar por index.html e embed.html) "
           "— reduz A4 gradualmente."),
    ("P4", "Quando o palpite.html/Supabase entrar: aplicar exatamente as regras já "
           "escritas no SECURITY.md (RLS insert-only, service key só no Actions, "
           "CHECK no banco) e auditar de novo as categorias 1 e 3, que passarão a "
           "existir."),
]

ISSUES = [
    ("ISSUE 1", """\
Título: [Segurança] XSS via URL javascript: nas fontes citadas do recibo do Radar
Labels: security, severity:media

## Problema

`fontesHTML()` em `docs/radar/radar.js` monta os links das fontes citadas com
`esc(f.url)`. O `esc()` escapa `&<>"'` (impede quebrar o atributo), mas não
valida o **esquema** da URL: um valor `javascript:...` vira um link que executa
script no clique. A CSP das páginas do Radar inclui `'unsafe-inline'`, que
também libera navegação `javascript:`.

Hoje os recibos são fixtures commitadas (inofensivas), mas o campo
`fontes_citadas` virá do coletor real, com URLs extraídas de respostas de
modelos de IA — conteúdo de terceiros que pode ser influenciado por quem
otimiza páginas para ser citado.

## Evidência

`docs/radar/radar.js:352`

```js
return '<li><a href="' + esc(f.url) + '" target="_blank" rel="noopener noreferrer nofollow">' +
       esc(f.titulo || f.url) + "</a></li>";
```

## Impacto

Execução de JavaScript arbitrário no contexto do site para quem clicar numa
fonte de um recibo envenenado (roubo de nada sensível hoje, mas defacement,
phishing e abuso da origem do domínio).

## Correção sugerida

Validar o esquema antes de renderizar como link; caso contrário, texto puro:

```js
function urlSegura(u) {
  return /^https?:\\/\\//i.test(String(u || "")) ? u : null;
}
// em fontesHTML():
var u = urlSegura(f.url);
if (!u) return "<li>" + esc(f.titulo || f.url) + "</li>";
```

## Critérios de aceite

- [ ] URL com esquema diferente de http/https é renderizada como texto, nunca como href
- [ ] Fixture de teste com `javascript:alert(1)` em fontes_citadas não produz link clicável
- [ ] Contrato de dados do coletor (docs/radar/README.md) documenta a regra
- [ ] Nenhuma regressão nos recibos existentes (fixtures continuam renderizando)
"""),
    ("ISSUE 2", """\
Título: [Segurança] Pinar dependências do CI e escopar secrets por step no monitor.yml
Labels: security, severity:media

## Problema

Dois achados relacionados no mesmo workflow (agrupados para não gerar spam):

1. **Dependências sem pinagem** — `requirements.txt` lista `requests`, `pyyaml`
   e `pillow` sem versão nem hash, e o workflow ainda faz `pip install anthropic`
   solto. Cada execução do cron (a cada 6 h) instala a última versão publicada
   no PyPI. O job tem `permissions: contents: write`: uma release maliciosa
   executaria com poder de commitar no repositório.
2. **Secrets com escopo largo** — `ANTHROPIC_API_KEY` e `GOATCOUNTER_TOKEN` são
   env do job inteiro; todos os steps (inclusive o `pip install`) conseguem
   lê-los, ampliando o impacto do item 1 para vazamento de chaves.

Contrasta com o resto do projeto, que pina Actions por SHA e usa SRI no CDN.
O Dependabot já monitora pip, mas sem versões pinadas não tem o que atualizar.

## Evidência

`requirements.txt:1-3`

```
requests
pyyaml
pillow
```

`.github/workflows/monitor.yml:29-31`

```yaml
env:
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  GOATCOUNTER_TOKEN: ${{ secrets.GOATCOUNTER_TOKEN }}
```

`.github/workflows/monitor.yml:44,50` — `pip install -r requirements.txt` /
`pip install anthropic` sem pin.

## Impacto

Comprometimento de pacote PyPI (supply chain) vira execução de código com
escrita no repo + leitura das duas chaves. Probabilidade baixa, impacto alto.

## Correção sugerida

- Pinar versões exatas e hashes: `pip-compile --generate-hashes` e
  `pip install --require-hashes -r requirements.txt` (o Dependabot passa a
  propor os bumps).
- Pinar `anthropic==X.Y.Z` no mesmo lock (extra opcional).
- Mover cada secret para o env do único step que o usa; para os `if:`, um step
  inicial pode publicar `has_anthropic`/`has_goat` como outputs.

## Critérios de aceite

- [ ] requirements.txt (ou lock derivado) com versão exata + hash de todas as deps
- [ ] Workflow instala com --require-hashes e falha se um hash divergir
- [ ] ANTHROPIC_API_KEY visível apenas no step "Coletar séries" (e no install opcional)
- [ ] GOATCOUNTER_TOKEN visível apenas no step "Coletar estatísticas"
- [ ] Cron continua verde por 2 execuções seguidas após a mudança
"""),
    ("ISSUE 3", """\
Título: [Segurança] Endurecer a CSP: substituir 'unsafe-inline' por hashes nos scripts inline
Labels: security, severity:baixa

## Problema

Todas as páginas publicam CSP via `<meta>` com
`script-src 'self' 'unsafe-inline' ...`. Com `'unsafe-inline'`, a CSP não
bloqueia `<script>` injetado nem URLs `javascript:` — a defesa anti-XSS fica
inteiramente no `esc()` (hoje consistente, mas sem rede de segurança para um
esquecimento futuro). Como o site usa scripts inline por desenho (sem build,
legível via file://), o endurecimento viável é CSP por hash.

## Evidência

`docs/index.html:8` (padrão repetido em todas as páginas)

```
script-src 'self' 'unsafe-inline' https://gc.zgo.at
```

## Impacto

Nenhum isoladamente — é defesa em profundidade. Se um novo ponto de
interpolação esquecer o `esc()`, a CSP atual não segura nada.

## Correção sugerida

- Gerar `sha256-...` dos blocos `<script>` inline nos builders
  (`build_pages.py`, `build_correcao.py`, `render_index.py`) e escrever
  `script-src 'self' 'sha256-...' https://gc.zgo.at`.
- Começar pelas páginas de maior tráfego (index.html, embed.html) e expandir.
- Manter `'unsafe-inline'` apenas em style-src (inofensivo em comparação).

## Critérios de aceite

- [ ] index.html e embed.html sem 'unsafe-inline' em script-src, com hashes válidos
- [ ] Páginas carregam sem erro de CSP no console (verificado nos dois temas do embed)
- [ ] Builders regeneram os hashes automaticamente quando o script inline muda
- [ ] SECURITY.md atualizado descrevendo a regra nova
"""),
]

# --------------------------------------------------------------------------- #
# Gráficos (matplotlib -> PNG em memória)
# --------------------------------------------------------------------------- #

def hexc(c):
    return "#%02X%02X%02X" % (int(c.red * 255), int(c.green * 255), int(c.blue * 255))


def grafico_rosca():
    ordem = ["critica", "alta", "media", "baixa", "informativa"]
    cont = {s: sum(1 for a in ACHADOS if a["sev"] == s) for s in ordem}
    labels = [f"{ROTULO_SEV[s].title()} ({cont[s]})" for s in ordem if cont[s]]
    vals = [cont[s] for s in ordem if cont[s]]
    cores = [hexc(COR[s]) for s in ordem if cont[s]]

    fig, ax = plt.subplots(figsize=(4.6, 3.2), dpi=200)
    wedges, _ = ax.pie(vals, colors=cores, startangle=90,
                       wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2))
    ax.text(0, 0.08, str(sum(vals)), ha="center", va="center",
            fontsize=26, fontweight="bold", color="#1F2430")
    ax.text(0, -0.24, "achados", ha="center", va="center", fontsize=9, color="#5B6472")
    ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5),
              frameon=False, fontsize=9)
    ax.set(aspect="equal")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


def grafico_barras():
    cats = [
        ("1. Banco sem\ntranca", 0, True),
        ("2. Permissão no\nnavegador", sum(1 for a in ACHADOS if a["cat"].startswith("2")), False),
        ("3. IDOR", 0, True),
        ("4. Chaves /\nsupply chain", sum(1 for a in ACHADOS if a["cat"].startswith("4")), False),
        ("5. XSS", sum(1 for a in ACHADOS if a["cat"].startswith("5")), False),
    ]
    nomes = [c[0] for c in cats]
    vals = [c[1] for c in cats]
    cores = ["#C9CDD4" if c[2] else "#D97706" for c in cats]

    fig, ax = plt.subplots(figsize=(5.4, 2.7), dpi=200)
    barras = ax.bar(nomes, vals, color=cores, width=0.55, zorder=3)
    for b, (nome, v, na) in zip(barras, cats):
        txt = "N/A" if na else str(v)
        ax.text(b.get_x() + b.get_width() / 2, v + 0.06, txt,
                ha="center", va="bottom", fontsize=12,
                fontweight="bold", color="#5B6472" if na else "#1F2430")
    ax.set_ylim(0, max(vals) + 0.8)
    ax.set_ylabel("achados", fontsize=10, color="#5B6472")
    ax.tick_params(axis="x", labelsize=9.5, colors="#1F2430")
    ax.tick_params(axis="y", labelsize=9, colors="#5B6472")
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.grid(axis="y", color="#E4E7EC", zorder=0)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#D8DCE3")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


# --------------------------------------------------------------------------- #
# PDF (reportlab platypus)
# --------------------------------------------------------------------------- #

ss = getSampleStyleSheet()

def st(nome, **kw):
    kw.setdefault("fontName", "Helvetica")
    kw.setdefault("textColor", COR["tinta"])
    return ParagraphStyle(nome, parent=ss["Normal"], **kw)

S = {
    "capa_titulo": st("capa_titulo", fontName="Helvetica-Bold", fontSize=25,
                      leading=31, spaceAfter=6),
    "capa_sub": st("capa_sub", fontSize=12, leading=17, textColor=COR["mut"]),
    "h1": st("h1", fontName="Helvetica-Bold", fontSize=16, leading=20,
             spaceBefore=14, spaceAfter=8),
    "h2": st("h2", fontName="Helvetica-Bold", fontSize=12, leading=15,
             spaceBefore=10, spaceAfter=4),
    "corpo": st("corpo", fontSize=9.5, leading=13.5, spaceAfter=5),
    "corpo_mut": st("corpo_mut", fontSize=9, leading=12.5, textColor=COR["mut"],
                    spaceAfter=5),
    "cel": st("cel", fontSize=8.5, leading=11.5),
    "cel_mono": st("cel_mono", fontName="Courier", fontSize=8, leading=10.5),
    "chip": st("chip", fontName="Helvetica-Bold", fontSize=7.5, leading=9,
               textColor=colors.white, alignment=TA_CENTER),
    "mono": st("mono", fontName="Courier", fontSize=7.6, leading=9.6),
    "kpi_num": st("kpi_num", fontName="Helvetica-Bold", fontSize=20, leading=22,
                  alignment=TA_CENTER),
    "kpi_rot": st("kpi_rot", fontSize=7.5, leading=9, textColor=COR["mut"],
                  alignment=TA_CENTER),
}


def chip(sev):
    t = Table([[Paragraph(ROTULO_SEV[sev], S["chip"])]],
              colWidths=[2.15 * cm], rowHeights=[0.42 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COR[sev]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return t


def esc_xml(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def cabecalho_rodape(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setStrokeColor(COR["linha"])
    canvas.setLineWidth(0.6)
    canvas.line(2 * cm, h - 1.35 * cm, w - 2 * cm, h - 1.35 * cm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(COR["mut"])
    canvas.drawString(2 * cm, h - 1.2 * cm,
                      "Relatório de Auditoria de Segurança — Observatório de Taxas")
    canvas.drawRightString(w - 2 * cm, h - 1.2 * cm, DATA)
    canvas.line(2 * cm, 1.45 * cm, w - 2 * cm, 1.45 * cm)
    canvas.drawString(2 * cm, 1.15 * cm, "LBP Tecnologia · auditoria de código")
    canvas.drawRightString(w - 2 * cm, 1.15 * cm, f"página {doc.page}")
    canvas.restoreState()


def capa(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(colors.HexColor("#0E1210"))
    canvas.rect(0, 0, w, h, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#D9B54A"))
    canvas.rect(2 * cm, h - 4.1 * cm, 2.2 * cm, 0.14 * cm, fill=1, stroke=0)

    canvas.setFillColor(colors.HexColor("#E9E6DC"))
    canvas.setFont("Helvetica-Bold", 27)
    canvas.drawString(2 * cm, h - 6.0 * cm, "Relatório de Auditoria")
    canvas.drawString(2 * cm, h - 7.1 * cm, "de Segurança")
    canvas.setFillColor(colors.HexColor("#D9B54A"))
    canvas.setFont("Helvetica", 15)
    canvas.drawString(2 * cm, h - 8.3 * cm, "Observatório de Taxas")

    canvas.setFillColor(colors.HexColor("#9BA1A6"))
    canvas.setFont("Helvetica", 10)
    canvas.drawString(2 * cm, h - 9.4 * cm, f"Data da auditoria: {DATA}")
    canvas.drawString(2 * cm, h - 10.0 * cm,
                      "Stack: site estático (GitHub Pages) + coletores Python + GitHub Actions")

    # Escopo
    canvas.setFillColor(colors.HexColor("#E9E6DC"))
    canvas.setFont("Helvetica-Bold", 10.5)
    canvas.drawString(2 * cm, h - 12.0 * cm, "Escopo auditado")
    canvas.setFont("Helvetica", 8.8)
    canvas.setFillColor(colors.HexColor("#B9BDC2"))
    from reportlab.lib.utils import simpleSplit
    y = h - 12.6 * cm
    for linha in simpleSplit(ESCOPO, "Helvetica", 8.8, w - 4 * cm):
        canvas.drawString(2 * cm, y, linha)
        y -= 0.42 * cm

    canvas.setFont("Helvetica-Bold", 10.5)
    canvas.setFillColor(colors.HexColor("#E9E6DC"))
    canvas.drawString(2 * cm, y - 0.5 * cm, "Nota metodológica")
    canvas.setFont("Helvetica", 8.8)
    canvas.setFillColor(colors.HexColor("#B9BDC2"))
    nota = ("Cada uma das cinco categorias do protocolo foi mapeada para o equivalente "
            "desta stack antes da varredura (detalhe na página 2). Onde a categoria não "
            "se aplica — não há banco de dados, backend nem autenticação — isso é dito "
            "explicitamente, em vez de forçar achados.")
    y -= 1.1 * cm
    for linha in simpleSplit(nota, "Helvetica", 8.8, w - 4 * cm):
        canvas.drawString(2 * cm, y, linha)
        y -= 0.42 * cm

    canvas.setFillColor(colors.HexColor("#6E7885"))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(2 * cm, 1.6 * cm,
                      "Repositório iosbilario/observatorio-taxas · HEAD 4e5de0b (branch desliga-radar)")
    canvas.restoreState()


def kpis():
    ordem = ["critica", "alta", "media", "baixa", "informativa"]
    cont = {s: sum(1 for a in ACHADOS if a["sev"] == s) for s in ordem}
    celulas, cores_ = [], []
    for s in ordem:
        celulas.append([Paragraph(f'<font color="{hexc(COR[s])}">{cont[s]}</font>', S["kpi_num"]),
                        Paragraph(ROTULO_SEV[s], S["kpi_rot"])])
        cores_.append(COR[s])
    celulas.append([Paragraph(f'<font color="{hexc(COR["forte"])}">{len(PONTOS_FORTES)}</font>', S["kpi_num"]),
                    Paragraph("PONTOS FORTES", S["kpi_rot"])])
    dados = [[c[0] for c in celulas], [c[1] for c in celulas]]
    t = Table(dados, colWidths=[2.83 * cm] * 6)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COR["fundo"]),
        ("BOX", (0, 0), (-1, -1), 0.7, COR["linha"]),
        ("LINEBEFORE", (1, 0), (-1, -1), 0.7, COR["linha"]),
        ("VALIGN", (0, 0), (-1, 0), "BOTTOM"),
        ("VALIGN", (0, 1), (-1, 1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
    ]))
    return t


def tabela_achados():
    linhas = [[
        Paragraph("<b>Sev.</b>", S["cel"]),
        Paragraph("<b>Arquivo:linha</b>", S["cel"]),
        Paragraph("<b>Achado</b>", S["cel"]),
    ]]
    ordem_sev = {"critica": 0, "alta": 1, "media": 2, "baixa": 3, "informativa": 4}
    for a in sorted(ACHADOS, key=lambda x: ordem_sev[x["sev"]]):
        linhas.append([
            chip(a["sev"]),
            Paragraph(esc_xml(a["onde"]).replace(" · ", "<br/>"), S["cel_mono"]),
            Paragraph(f"<b>{a['id']} — {esc_xml(a['titulo'])}</b><br/>"
                      f"<font color='{hexc(COR['mut'])}'>{esc_xml(a['cat'])}</font>",
                      S["cel"]),
        ])
    t = Table(linhas, colWidths=[2.55 * cm, 5.1 * cm, 9.35 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COR["fundo"]),
        ("GRID", (0, 0), (-1, -1), 0.5, COR["linha"]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def bloco_achado(a):
    corpo = [
        Table([[chip(a["sev"]),
                Paragraph(f"<b>{a['id']} — {esc_xml(a['titulo'])}</b>", S["h2"])]],
              colWidths=[2.55 * cm, 14.45 * cm],
              style=TableStyle([
                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                  ("LEFTPADDING", (0, 0), (0, 0), 0),
                  ("TOPPADDING", (0, 0), (-1, -1), 0),
                  ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
              ])),
        Paragraph(f"<font name='Courier' size='8'>{esc_xml(a['onde'])}</font> · "
                  f"<font color='{hexc(COR['mut'])}'>{esc_xml(a['cat'])}</font>",
                  S["corpo_mut"]),
    ]
    trecho = esc_xml(a["trecho"]).replace("\n", "<br/>")
    corpo.append(Table([[Paragraph(trecho, S["mono"])]], colWidths=[17 * cm],
                       style=TableStyle([
                           ("BACKGROUND", (0, 0), (-1, -1), COR["fundo"]),
                           ("BOX", (0, 0), (-1, -1), 0.5, COR["linha"]),
                           ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7),
                       ])))
    corpo.append(Spacer(1, 3))
    corpo.append(Paragraph("<b>Por que é explorável:</b> " + esc_xml(a["desc"]), S["corpo"]))
    corpo.append(Paragraph("<b>Condição de explorabilidade:</b> " + esc_xml(a["cond"]),
                           S["corpo_mut"]))
    corpo.append(Spacer(1, 8))
    return corpo


def bloco_issue(nome, texto):
    linhas = [f"--- {nome} ---"] + texto.rstrip().split("\n") + [f"--- FIM {nome} ---"]
    html = "<br/>".join(esc_xml(l) if l.strip() else "&nbsp;" for l in linhas)
    return Table([[Paragraph(html, S["mono"])]], colWidths=[17 * cm],
                 style=TableStyle([
                     ("BACKGROUND", (0, 0), (-1, -1), COR["fundo"]),
                     ("BOX", (0, 0), (-1, -1), 0.5, COR["linha"]),
                     ("TOPPADDING", (0, 0), (-1, -1), 8),
                     ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                     ("LEFTPADDING", (0, 0), (-1, -1), 9),
                     ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                 ]))


def montar():
    doc = BaseDocTemplate(str(SAIDA), pagesize=A4,
                          leftMargin=2 * cm, rightMargin=2 * cm,
                          topMargin=2 * cm, bottomMargin=2 * cm,
                          title=TITULO, author="LBP Tecnologia",
                          subject="Auditoria de segurança — 31/08/2026")
    frame = Frame(2 * cm, 2 * cm, A4[0] - 4 * cm, A4[1] - 4 * cm, id="corpo")
    doc.addPageTemplates([
        PageTemplate(id="capa", frames=[frame], onPage=capa),
        PageTemplate(id="miolo", frames=[frame], onPage=cabecalho_rodape),
    ])

    el = []
    # página 1: capa (desenhada no onPage; o frame fica vazio)
    from reportlab.platypus import NextPageTemplate
    el.append(NextPageTemplate("miolo"))
    el.append(Spacer(1, 1))
    el.append(PageBreak())

    # --- metodologia -------------------------------------------------------
    el.append(Paragraph("Como cada categoria foi mapeada para esta stack", S["h1"]))
    for titulo, texto in METODOLOGIA:
        el.append(Paragraph(f"<b>{esc_xml(titulo)}</b>", S["h2"]))
        el.append(Paragraph(esc_xml(texto), S["corpo"]))
    el.append(PageBreak())

    # --- resumo executivo --------------------------------------------------
    el.append(Paragraph("Resumo executivo", S["h1"]))
    el.append(Paragraph(
        "Nenhum achado crítico ou alto. O projeto trata segurança como parte do "
        "produto — escape de saída consistente, allowlists de parâmetros, CSP por "
        "página, Actions pinadas por SHA, zero segredos no código e no histórico git — "
        "e os cinco achados são de endurecimento: dois médios (validação de esquema de "
        "URL num componente ainda não ativado; pinagem de dependências do CI), dois "
        "baixos (escopo de secrets; CSP com 'unsafe-inline') e um informativo "
        "(painel /admin/ por obscuridade, decisão já documentada no próprio código).",
        S["corpo"]))
    el.append(Spacer(1, 6))
    el.append(kpis())
    el.append(Spacer(1, 12))

    img_rosca = Image(grafico_rosca(), width=8.6 * cm, height=5.7 * cm)
    img_barras = Image(grafico_barras(), width=8.2 * cm, height=3.9 * cm)
    t = Table([[
        [Paragraph("<b>Achados por severidade</b>", S["h2"]), img_rosca],
        [Paragraph("<b>Achados por categoria</b>", S["h2"]), Spacer(1, 14), img_barras],
    ]], colWidths=[8.9 * cm, 8.1 * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    el.append(t)
    el.append(Paragraph(
        "Categorias 1 (isolamento de inquilino) e 3 (IDOR) não se aplicam: não há "
        "banco de dados, backend nem objetos por dono — todos os dados servidos são "
        "públicos por desenho (séries oficiais do BACEN).", S["corpo_mut"]))
    el.append(PageBreak())

    # --- pontos fortes -----------------------------------------------------
    el.append(Paragraph("Pontos fortes — o que está protegido", S["h1"]))
    linhas = []
    for titulo, texto in PONTOS_FORTES:
        linhas.append([
            Paragraph("✓", ParagraphStyle("ok", parent=S["cel"], textColor=COR["forte"],
                                          fontName="Helvetica-Bold", fontSize=11)),
            Paragraph(f"<b>{esc_xml(titulo)}.</b> {esc_xml(texto)}", S["cel"]),
        ])
    tf = Table(linhas, colWidths=[0.8 * cm, 16.2 * cm])
    tf.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, COR["linha"]),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
    ]))
    el.append(tf)
    el.append(Spacer(1, 10))
    el.append(Paragraph("Pontos fracos — os riscos centrais", S["h1"]))
    el.append(Paragraph(
        "<b>1. Supply chain do CI é o único caminho realista até os secrets.</b> "
        "Dependências Python sem pin num job com escrita no repo e chaves no ambiente "
        "(A2+A3): é o par a fechar primeiro.", S["corpo"]))
    el.append(Paragraph(
        "<b>2. O contrato de dados do Radar ainda não impõe URL http(s).</b> Quando o "
        "coletor real ligar, conteúdo de modelos de IA vira href sem validação de "
        "esquema (A1) — fechar antes de ativar.", S["corpo"]))
    el.append(Paragraph(
        "<b>3. A defesa anti-XSS depende de disciplina, não de política.</b> O esc() "
        "hoje cobre tudo, mas com 'unsafe-inline' na CSP (A4) um único ponto esquecido "
        "no futuro já é explorável.", S["corpo"]))
    el.append(PageBreak())

    # --- achados detalhados ------------------------------------------------
    el.append(Paragraph("Achados detalhados", S["h1"]))
    el.append(tabela_achados())
    el.append(Spacer(1, 12))
    for a in ACHADOS:
        el.extend(bloco_achado(a))
    el.append(PageBreak())

    # --- recomendações -----------------------------------------------------
    el.append(Paragraph("Recomendações priorizadas", S["h1"]))
    linhas = []
    for p, texto in RECOMENDACOES:
        linhas.append([
            Paragraph(f"<b>{p}</b>", ParagraphStyle("p", parent=S["cel"],
                                                    textColor=COR["baixa"], fontSize=10)),
            Paragraph(esc_xml(texto), S["cel"]),
        ])
    tr = Table(linhas, colWidths=[1.2 * cm, 15.8 * cm])
    tr.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, COR["linha"]),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
    ]))
    el.append(tr)
    el.append(PageBreak())

    # --- issues ------------------------------------------------------------
    el.append(Paragraph("Issues para o GitHub", S["h1"]))
    el.append(Paragraph(
        "Texto completo de cada issue em Markdown, pronto para copiar e colar, entre "
        "os delimitadores. A2 e A3 foram agrupados numa issue única (mesmo workflow, "
        "mesma correção); A5 é decisão documentada e não gera issue.", S["corpo_mut"]))
    for nome, texto in ISSUES:
        el.append(Spacer(1, 6))
        el.append(bloco_issue(nome, texto))

    doc.build(el)
    print(f"OK: {SAIDA}")


if __name__ == "__main__":
    montar()
