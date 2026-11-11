"""Testes do IndexNow (scripts/indexnow.py). Sem rede: GET e POST são falsos.

    python -m unittest tests.test_indexnow -v
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import indexnow as ix  # noqa: E402
from render_index import impressao_digital_html  # noqa: E402

B = ix.BASE_URL
CHAVE = "0123456789abcdef0123456789abcdef"
EP = "https://api.indexnow.org/indexnow"


def pagina(valor: str) -> str:
    return (f"<html><head><title>T {valor}</title></head><body>"
            f"<!-- conteudo:inicio --><p>{valor}</p><!-- conteudo:fim --></body></html>")


class Site:
    """Site publicado falso: url -> (status, html)."""

    def __init__(self, paginas: dict[str, str], chave_ok: bool = True):
        self.paginas = dict(paginas)
        self.chave_ok = chave_ok
        self.gets: list[str] = []

    def get(self, url: str) -> ix.Resposta:
        self.gets.append(url)
        if url == f"{B}/{CHAVE}.txt":
            return ix.Resposta(200, CHAVE + "\n") if self.chave_ok else ix.Resposta(404)
        for u, html in self.paginas.items():
            if ix.codificar(u) == url:
                return ix.Resposta(200, html)
        return ix.Resposta(404)


class Buscador:
    def __init__(self, respostas: list[int]):
        self.respostas = list(respostas)
        self.posts: list[dict] = []

    def post(self, url: str, payload: dict) -> ix.Resposta:
        self.posts.append(payload)
        return ix.Resposta(self.respostas.pop(0) if self.respostas else 200)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def estado_atual(self, paginas: dict[str, str], lastmod: str = "2026-11-12") -> Path:
        p = self.d / "sitemap_lastmod.json"
        p.write_text(json.dumps({u: {"hash": impressao_digital_html(h), "lastmod": lastmod}
                                 for u, h in paginas.items()}), encoding="utf-8")
        return p

    def estado_envio(self, paginas: dict[str, str]) -> Path:
        p = self.d / "anterior.json"
        p.write_text(json.dumps({"urls": {u: impressao_digital_html(h) for u, h in paginas.items()}}),
                     encoding="utf-8")
        return p

    def rodar(self, anterior, atual, site, busc, dry=False, verificar=True, desde=None):
        saida, logp = self.d / "novo.json", self.d / "envios.jsonl"
        rc = ix.executar(anterior, saida, logp, dry, verificar, desde, get=site.get, post=busc.post,
                         tentativas_deploy=2, intervalo_deploy=0, dormir=lambda s: None,
                         atual_path=atual, chave=CHAVE, endpoint=EP, commit="abc")
        novo = json.loads(saida.read_text(encoding="utf-8"))["urls"] if saida.exists() else None
        return rc, novo, busc.posts


A, Bu, C = f"{B}/reajuste/a/", f"{B}/reajuste/b/", f"{B}/reajuste/igpm-março-2026/"


class TestPlano(Base):
    def test_sem_alteracao_nao_envia_nada(self):
        pags = {A: pagina("1"), Bu: pagina("2")}
        rc, novo, posts = self.rodar(self.estado_envio(pags), self.estado_atual(pags), Site(pags), Buscador([]))
        self.assertEqual((rc, posts), (0, []))
        self.assertEqual(novo, {u: impressao_digital_html(h) for u, h in pags.items()})

    def test_nova_alterada_e_removida(self):
        antes = {A: pagina("1"), Bu: pagina("2")}
        depois = {A: pagina("1-novo"), C: pagina("3")}       # A alterada, C nova, Bu removida
        site = Site(depois)
        rc, novo, posts = self.rodar(self.estado_envio(antes), self.estado_atual(depois), site, Buscador([200]))
        self.assertEqual(rc, 0)
        self.assertEqual(len(posts), 1)
        enviadas = posts[0]["urlList"]
        self.assertEqual(sorted(enviadas), sorted([ix.codificar(A), ix.codificar(C), ix.codificar(Bu)]))
        self.assertEqual(posts[0]["host"], ix.HOST)
        self.assertEqual(posts[0]["keyLocation"], f"{B}/{CHAVE}.txt")
        self.assertEqual(set(novo), {A, C})                  # removida sai do estado
        self.assertEqual(novo[A], impressao_digital_html(depois[A]))

    def test_nao_reenvia_depois_de_aceito(self):
        antes = {A: pagina("1")}
        depois = {A: pagina("2")}
        rc, novo, posts = self.rodar(self.estado_envio(antes), self.estado_atual(depois), Site(depois), Buscador([200]))
        (self.d / "anterior.json").write_text(json.dumps({"urls": novo}), encoding="utf-8")
        rc2, _, posts2 = self.rodar(self.d / "anterior.json", self.estado_atual(depois), Site(depois), Buscador([]))
        self.assertEqual(len(posts), 1)
        self.assertEqual((rc2, posts2), (0, []), "segunda execução não deveria enviar")

    def test_url_com_cedilha_vai_escapada(self):
        antes, depois = {}, {C: pagina("x")}
        p = self.d / "anterior.json"
        p.write_text(json.dumps({"urls": {}}), encoding="utf-8")
        _, _, posts = self.rodar(p, self.estado_atual(depois), Site(depois), Buscador([200]))
        url = posts[0]["urlList"][0]
        self.assertTrue(url.isascii())
        self.assertIn("mar%C3%A7o", url)

    def test_url_de_outro_host_e_ignorada(self):
        p = self.d / "anterior.json"
        p.write_text(json.dumps({"urls": {}}), encoding="utf-8")
        depois = {"https://outro.exemplo/x/": pagina("x")}
        rc, _, posts = self.rodar(p, self.estado_atual(depois), Site(depois), Buscador([]))
        self.assertEqual((rc, posts), (0, []))


class TestDeploy(Base):
    def test_versao_antiga_no_ar_fica_pendente(self):
        antes, depois = {A: pagina("1")}, {A: pagina("2")}
        site = Site(antes)                                   # o Pages ainda serve a versão antiga
        rc, novo, posts = self.rodar(self.estado_envio(antes), self.estado_atual(depois), site, Buscador([]))
        self.assertEqual((rc, posts), (0, []))
        self.assertEqual(novo[A], impressao_digital_html(antes[A]), "estado não pode avançar")

    def test_removida_que_ainda_responde_200_fica_pendente(self):
        antes, depois = {A: pagina("1"), Bu: pagina("2")}, {A: pagina("1")}
        site = Site(antes)                                   # Bu ainda no ar
        rc, novo, posts = self.rodar(self.estado_envio(antes), self.estado_atual(depois), site, Buscador([]))
        self.assertEqual(posts, [])
        self.assertIn(Bu, novo)

    def test_sem_arquivo_de_chave_nao_envia(self):
        antes, depois = {A: pagina("1")}, {A: pagina("2")}
        rc, novo, posts = self.rodar(self.estado_envio(antes), self.estado_atual(depois),
                                     Site(depois, chave_ok=False), Buscador([]))
        self.assertEqual((rc, posts), (0, []))
        self.assertEqual(novo[A], impressao_digital_html(antes[A]))


class TestEnvio(Base):
    def test_retry_em_429_e_depois_aceita(self):
        antes, depois = {A: pagina("1")}, {A: pagina("2")}
        rc, novo, posts = self.rodar(self.estado_envio(antes), self.estado_atual(depois), Site(depois), Buscador([429, 200]))
        self.assertEqual((rc, len(posts)), (0, 2))
        self.assertEqual(novo[A], impressao_digital_html(depois[A]))

    def test_403_nao_repete_nao_avanca_e_sinaliza(self):
        antes, depois = {A: pagina("1")}, {A: pagina("2")}
        rc, novo, posts = self.rodar(self.estado_envio(antes), self.estado_atual(depois), Site(depois), Buscador([403]))
        self.assertEqual((rc, len(posts)), (1, 1))
        self.assertEqual(novo[A], impressao_digital_html(antes[A]))

    def test_falha_de_rede_esgota_tentativas_sem_avancar(self):
        antes, depois = {A: pagina("1")}, {A: pagina("2")}
        rc, novo, posts = self.rodar(self.estado_envio(antes), self.estado_atual(depois), Site(depois), Buscador([0, 0, 0]))
        self.assertEqual((rc, len(posts)), (0, 3))
        self.assertEqual(novo[A], impressao_digital_html(antes[A]))

    def test_dry_run_nao_envia_nem_grava(self):
        antes, depois = {A: pagina("1")}, {A: pagina("2")}
        rc, novo, posts = self.rodar(self.estado_envio(antes), self.estado_atual(depois), Site(depois), Buscador([]), dry=True)
        self.assertEqual((rc, posts, novo), (0, [], None))

    def test_lotes_de_ate_10000(self):
        urls = [f"{B}/x{i}/" for i in range(10_001)]
        busc = Buscador([200, 200])
        aceitas, reg = ix.enviar(urls, CHAVE, EP, busc.post, dormir=lambda s: None)
        self.assertEqual([len(p["urlList"]) for p in busc.posts], [10_000, 1])
        self.assertEqual(len(aceitas), 10_001)


class TestPrimeiraExecucao(Base):
    def test_sem_estado_semeia_e_nao_envia_em_massa(self):
        pags = {A: pagina("1"), Bu: pagina("2")}
        rc, novo, posts = self.rodar(None, self.estado_atual(pags), Site(pags), Buscador([]))
        self.assertEqual((rc, posts), (0, []))
        self.assertEqual(set(novo), {A, Bu})

    def test_desde_envia_so_o_que_mudou_a_partir_da_data(self):
        pags = {A: pagina("1"), Bu: pagina("2")}
        atual = self.d / "sitemap_lastmod.json"
        atual.write_text(json.dumps({A: {"hash": impressao_digital_html(pags[A]), "lastmod": "2026-08-14"},
                                     Bu: {"hash": impressao_digital_html(pags[Bu]), "lastmod": "2026-11-11"}}),
                         encoding="utf-8")
        rc, novo, posts = self.rodar(None, atual, Site(pags), Buscador([200]), desde="2026-11-11")
        self.assertEqual(posts[0]["urlList"], [ix.codificar(Bu)])


class TestConfiguracaoPublicada(unittest.TestCase):
    def test_chave_valida_e_arquivo_publicado_em_docs(self):
        chave, endpoint = ix.ler_config()
        self.assertRegex(chave, ix.CHAVE_RE)
        self.assertTrue(endpoint.startswith("https://"))
        arq = ROOT / "docs" / f"{chave}.txt"
        self.assertTrue(arq.is_file(), arq)
        self.assertEqual(arq.read_text(encoding="utf-8").strip(), chave)

    def test_arquivo_de_chave_fora_do_sitemap(self):
        chave, _ = ix.ler_config()
        self.assertNotIn(f"{chave}.txt", (ROOT / "docs" / "sitemap.xml").read_text(encoding="utf-8"))

    def test_sem_verificar_exige_dry_run(self):
        with self.assertRaises(SystemExit):
            ix.main(["--sem-verificar"])


if __name__ == "__main__":
    unittest.main()
