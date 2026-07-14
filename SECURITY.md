# Política de segurança

Site 100% estático no GitHub Pages: não há servidor nem headers HTTP sob nosso
controle, então toda a superfície de segurança vive no HTML/JS. Para relatar uma
vulnerabilidade, escreva para **contato@observatoriodetaxas.tec.br**
(ver também [`/.well-known/security.txt`](docs/.well-known/security.txt)).

## Regras vigentes

### 1. Escape de saída (anti-XSS)
Toda interpolação que vá para `innerHTML` passa por `esc()` (escapa
`& < > " '`). Onde o conteúdo é texto puro, use `textContent` em vez de
`innerHTML`. `esc()` está definido em cada página que renderiza dinamicamente
(`index.html`, `var.html`, `embed.html`, `admin/index.html`) e nos geradores
Python (`scripts/render_index.py`, `scripts/build_pages.py`,
`scripts/build_correcao.py`).

### 2. Allowlist de parâmetros de URL
Nenhum valor lido de `URLSearchParams`/hash é renderizado sem validação. Em
`var.html`:

| Parâmetro | Regra |
|-----------|-------|
| `s` | tem que existir nos códigos de `docs/data/series.json` |
| `op`, `cmp`, `tema` | enum fixo |
| `a1`/`a2`/`b1`/`b2` | `^\d{4}-(0[1-9]\|1[0-2])$` (aaaa-mm, mês 01–12) |
| `sha` | `^[0-9a-f]{7,40}$` |

Parâmetro inválido é **descartado** (usa-se o default), nunca o valor recebido.

### 3. CSP e metas por página
Cada página tem `Content-Security-Policy` via `<meta http-equiv>`, construída a
partir do que ela realmente usa (`'self'` + Google Fonts, GoatCounter,
api.github.com e raw.githubusercontent.com conforme o caso), mais
`referrer: strict-origin-when-cross-origin`, guard leve contra clickjacking
(`if (top !== self) …`) e `rel="noopener noreferrer"` em todo `target="_blank"`.
**Exceção:** `embed.html` é feito para ser embutido — não leva `frame-ancestors`
nem guard anti-frame.

### 4. Supply chain
Actions de terceiros são pinadas por **SHA de commit** (não por tag). Scripts de
CDN são pinados por versão exata com `integrity` (SRI) + `crossorigin` quando há
hash estável (ex.: Chart.js no painel admin). Dependabot (`.github/dependabot.yml`)
acompanha `pip` e `github-actions` semanalmente.

## Regras para o futuro `palpite.html` (com Supabase)

Quando entrar o formulário de palpites com backend Supabase:

- **Service key só em secret do Actions** — nunca no cliente. O front usa apenas
  a chave `anon` pública.
- **RLS insert-only para `anon`**: a role anônima pode inserir, nunca ler,
  atualizar ou apagar.
- **Constraint de faixa de valor no banco** (CHECK) para rejeitar palpites fora
  de um intervalo plausível, independente do que o cliente enviar.
- **Honeypot + tempo mínimo de preenchimento** no cliente: campo invisível que,
  se preenchido, aborta o envio; e descarte de submissões instantâneas (bots).
- Todo dado de volta do banco renderizado com `esc()`/`textContent`, como acima.
