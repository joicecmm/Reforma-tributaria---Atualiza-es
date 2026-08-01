"""
Robô de monitoramento da Reforma Tributária.

O que ele faz:
1. Consulta a API de Dados Abertos da Câmara dos Deputados buscando
   proposições relacionadas à reforma tributária (IBS, CBS, LC 214, etc.)
2. Monitora o Portal da NFS-e (gov.br/nfse):
   - Notícias
   - Documentação Atual (guias, manuais, anexos)
   - RTC (Notas Técnicas sobre a Reforma Tributária do Consumo)
3. Compara tudo com o que já foi visto anteriormente (seen_items.json)
4. Envia as novidades encontradas para o WhatsApp via Twilio

Para adicionar novas fontes, crie uma função "buscar_xxx()" que devolve
uma lista de dicts com as chaves: id, fonte, titulo, ementa, link — e
chame essa função dentro de main().
"""

import os
import re
import json
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------
# CONFIGURAÇÕES GERAIS
# ----------------------------------------------------------------------

ARQUIVO_HISTORICO = "seen_items.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MonitorReformaTributaria/1.0)"
}

TENTATIVAS_MAX = 3
TIMEOUT_REQUEST = 45


def get_com_retry(url, params=None, tentativas=TENTATIVAS_MAX):
    """
    Faz um GET com novas tentativas automáticas em caso de timeout ou
    erro de conexão — útil porque APIs de governo às vezes engasgam
    momentaneamente. Levanta a última exceção se todas as tentativas falharem.
    """
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT_REQUEST)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            ultimo_erro = e
            if tentativa < tentativas:
                print(f"  [aviso] tentativa {tentativa}/{tentativas} falhou para {url} ({e}); tentando de novo...")
    raise ultimo_erro

# ----------------------------------------------------------------------
# FONTE 1 — API DA CÂMARA DOS DEPUTADOS
# ----------------------------------------------------------------------

TERMOS_BUSCA_CAMARA = [
    "reforma tributária",
    "IBS",
    "CBS",
    "imposto seletivo",
]

DIAS_JANELA_CAMARA = 3


def buscar_proposicoes_camara():
    """
    Busca proposições recentes na API da Câmara dos Deputados.
    Documentação: https://dadosabertos.camara.leg.br/swagger/api.html
    """
    data_inicio = (datetime.now() - timedelta(days=DIAS_JANELA_CAMARA)).strftime("%Y-%m-%d")
    url = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"

    encontrados = []
    ids_ja_processados = set()

    for termo in TERMOS_BUSCA_CAMARA:
        params = {
            "keywords": termo,
            "dataApresentacaoInicio": data_inicio,
            "ordem": "DESC",
            "ordenarPor": "id",
            "itens": 20,
        }
        try:
            resp = get_com_retry(url, params=params)
            dados = resp.json().get("dados", [])
        except requests.RequestException as e:
            print(f"[ERRO] Câmara - falha ao buscar termo '{termo}': {e}")
            continue

        for item in dados:
            prop_id = item.get("id")
            if prop_id in ids_ja_processados:
                continue
            ids_ja_processados.add(prop_id)

            encontrados.append({
                "id": f"camara-{prop_id}",
                "fonte": "Câmara dos Deputados",
                "titulo": f"{item.get('siglaTipo')} {item.get('numero')}/{item.get('ano')}",
                "ementa": (item.get("ementa") or "").strip(),
                "link": f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={prop_id}",
            })

    return encontrados


# ----------------------------------------------------------------------
# FONTE 2 — NOTÍCIAS DO PORTAL NFS-E
# ----------------------------------------------------------------------

URL_NOTICIAS_NFSE = "https://www.gov.br/nfse/pt-br/noticias"
DIAS_JANELA_NOTICIAS = 15  # notícias saem com menos frequência que proposições


def buscar_noticias_nfse():
    """
    Faz scraping da listagem de notícias do Portal da NFS-e.
    Cada notícia é um link para /nfse/pt-br/noticias/<slug>, seguido de
    uma data no formato DD/MM/AAAA.
    """
    encontrados = []
    try:
        resp = get_com_retry(URL_NOTICIAS_NFSE)
    except requests.RequestException as e:
        print(f"[ERRO] Notícias NFS-e - falha ao acessar página: {e}")
        return encontrados

    soup = BeautifulSoup(resp.text, "html.parser")
    data_limite = datetime.now() - timedelta(days=DIAS_JANELA_NOTICIAS)

    # Links de notícias individuais: /nfse/pt-br/noticias/<slug-com-mais-de-uma-parte>
    padrao_link = re.compile(r"^https://www\.gov\.br/nfse/pt-br/noticias/[^/]+/?$")

    vistos_nesta_pagina = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not padrao_link.match(href):
            continue
        if href in vistos_nesta_pagina:
            continue
        titulo = a.get_text(strip=True)
        if not titulo:
            continue
        vistos_nesta_pagina.add(href)

        # Tenta achar uma data (DD/MM/AAAA) próxima ao link, olhando o
        # texto do elemento "pai" (geralmente contém título + data + resumo)
        contexto = a.find_parent(["li", "article", "div"])
        texto_contexto = contexto.get_text(" ", strip=True) if contexto else titulo
        data_match = re.search(r"(\d{2})/(\d{2})/(\d{4})", texto_contexto)

        data_noticia = None
        if data_match:
            try:
                data_noticia = datetime.strptime(data_match.group(0), "%d/%m/%Y")
            except ValueError:
                pass

        # Só considera se a data estiver dentro da janela (ou se não
        # conseguimos extrair data — nesse caso deixamos passar, já que
        # o controle de duplicados pelo histórico evita reenvio)
        if data_noticia and data_noticia < data_limite:
            continue

        ementa = texto_contexto.replace(titulo, "", 1).strip(" -")
        if len(ementa) > 200:
            ementa = ementa[:200] + "..."

        encontrados.append({
            "id": f"nfse-noticia-{href}",
            "fonte": "Notícias NFS-e",
            "titulo": titulo,
            "ementa": ementa,
            "link": href,
        })

    return encontrados


def buscar_texto_completo_noticia(link):
    """
    Acessa a página de uma notícia individual do Portal NFS-e e extrai
    o texto completo da matéria (todos os parágrafos do corpo do
    conteúdo), não apenas o resumo que aparece na listagem.
    """
    try:
        resp = get_com_retry(link)
    except requests.RequestException as e:
        print(f"  [aviso] não foi possível buscar texto completo de {link}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Tenta achar o container principal do conteúdo (Plone geralmente usa
    # a tag <article> ou uma div com id/class "content-core"). Se não
    # achar, cai para o body inteiro como último recurso.
    container = (
        soup.find("article")
        or soup.find(id="content-core")
        or soup.find("div", class_=re.compile("content-core|documentContent"))
        or soup.body
    )
    if not container:
        return None

    paragrafos = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    paragrafos = [p for p in paragrafos if p]  # remove vazios

    texto_completo = "\n\n".join(paragrafos).strip()
    return texto_completo or None


# ----------------------------------------------------------------------
# FONTE 3 e 4 — PÁGINAS DE DOCUMENTAÇÃO (Documentação Atual / RTC)
# ----------------------------------------------------------------------

PAGINAS_DOCUMENTOS = [
    {
        "nome": "Documentação Atual NFS-e",
        "url": "https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual",
    },
    {
        "nome": "RTC NFS-e (Reforma Tributária)",
        "url": "https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc",
    },
]

EXTENSOES_DOCUMENTO = (".pdf", ".xlsx", ".xls", ".zip", ".doc", ".docx", ".csv")


def buscar_documentos(pagina):
    """
    Faz scraping de uma página de documentação do Portal NFS-e,
    listando todos os arquivos (PDF, XLSX, ZIP etc.) disponíveis.
    Cada arquivo novo (ainda não visto antes) é reportado como novidade
    — isso cobre tanto documentos novos quanto novas versões, já que
    o nome do arquivo normalmente muda a cada atualização (ex: v1.02 -> v1.03).
    """
    encontrados = []
    try:
        resp = get_com_retry(pagina["url"])
    except requests.RequestException as e:
        print(f"[ERRO] {pagina['nome']} - falha ao acessar página: {e}")
        return encontrados

    soup = BeautifulSoup(resp.text, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.lower().endswith(EXTENSOES_DOCUMENTO):
            continue
        if "gov.br/nfse" not in href:
            continue

        titulo = a.get_text(strip=True) or href.rsplit("/", 1)[-1]

        encontrados.append({
            "id": f"nfse-doc-{href}",
            "fonte": pagina["nome"],
            "titulo": titulo,
            "ementa": "",
            "link": href,
        })

    return encontrados


# ----------------------------------------------------------------------
# CONTROLE DE HISTÓRICO (evita notificar a mesma coisa 2x)
# ----------------------------------------------------------------------

def carregar_historico():
    if os.path.exists(ARQUIVO_HISTORICO):
        with open(ARQUIVO_HISTORICO, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def salvar_historico(ids_vistos):
    with open(ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
        json.dump(sorted(ids_vistos), f, ensure_ascii=False, indent=2)


# ----------------------------------------------------------------------
# ENVIO VIA WHATSAPP (TWILIO)
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# MONTAGEM DA MENSAGEM
# ----------------------------------------------------------------------

def gravar_resumo_actions(todos_encontrados, ids_novos):
    """
    Escreve um resumo em Markdown no "Summary" da execução do GitHub
    Actions (aba Actions >> clique na execução >> aparece no topo da
    página, sem precisar abrir os logs). Só funciona quando rodando
    dentro do GitHub Actions (variável de ambiente GITHUB_STEP_SUMMARY).

    Mostra SEMPRE todos os itens encontrados (com o texto completo das
    notícias), marcando com 🆕 os que ainda não tinham sido vistos antes.
    """
    caminho_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not caminho_summary:
        return  # rodando localmente, não há summary do Actions

    linhas = [f"## Atualizações — Reforma Tributária ({datetime.now().strftime('%d/%m/%Y %H:%M')})\n"]
    linhas.append(f"**Total de itens encontrados:** {len(todos_encontrados)}")
    linhas.append(f"**Novos desde a última execução:** {len(ids_novos)}\n")

    # Agrupa por fonte para facilitar a leitura
    fontes = {}
    for item in todos_encontrados:
        fontes.setdefault(item["fonte"], []).append(item)

    for fonte, itens in fontes.items():
        linhas.append(f"### {fonte}\n")
        for item in itens:
            marcador = "🆕 " if item["id"] in ids_novos else ""
            linhas.append(f"#### {marcador}{item['titulo']}\n")
            texto = item.get("texto_completo") or item.get("ementa")
            if texto:
                linhas.append(texto + "\n")
            linhas.append(f"[Ver original]({item['link']})\n")
            linhas.append("---\n")

    with open(caminho_summary, "a", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


# ----------------------------------------------------------------------
# EXECUÇÃO PRINCIPAL
# ----------------------------------------------------------------------

def main():
    print("Buscando atualizações sobre a reforma tributária...")

    ids_vistos = carregar_historico()

    todos_encontrados = []
    todos_encontrados += buscar_proposicoes_camara()
    todos_encontrados += buscar_noticias_nfse()
    for pagina in PAGINAS_DOCUMENTOS:
        todos_encontrados += buscar_documentos(pagina)

    print(f"Total de itens encontrados nesta varredura: {len(todos_encontrados)}")
    for item in todos_encontrados:
        print(f"  - [{item['fonte']}] {item['titulo']} -> {item['link']}")

    ids_novos = {item["id"] for item in todos_encontrados if item["id"] not in ids_vistos}

    # Busca o texto completo de TODAS as notícias (não só as novas), já
    # que o objetivo aqui é visualizar a informação completa, não só
    # receber alertas de novidade.
    for item in todos_encontrados:
        if item["fonte"] == "Notícias NFS-e":
            print(f"  Buscando texto completo: {item['titulo']}")
            texto_completo = buscar_texto_completo_noticia(item["link"])
            if texto_completo:
                item["texto_completo"] = texto_completo

    gravar_resumo_actions(todos_encontrados, ids_novos)

    salvar_historico(ids_vistos.union(item["id"] for item in todos_encontrados))
    print("Concluído. Veja o resumo completo na aba Actions (Summary desta execução).")


if __name__ == "__main__":
    main()
