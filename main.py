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
            resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
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
        resp = requests.get(URL_NOTICIAS_NFSE, headers=HEADERS, timeout=30)
        resp.raise_for_status()
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
        resp = requests.get(pagina["url"], headers=HEADERS, timeout=30)
        resp.raise_for_status()
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

def enviar_whatsapp(mensagem):
    """
    Envia mensagem via Twilio WhatsApp API.
    Requer as variáveis de ambiente:
      - TWILIO_ACCOUNT_SID
      - TWILIO_AUTH_TOKEN
      - TWILIO_WHATSAPP_FROM   (ex: whatsapp:+14155238886  -> número sandbox)
      - TWILIO_WHATSAPP_TO     (ex: whatsapp:+55XXXXXXXXXXX -> seu número)
    """
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    numero_de = os.environ["TWILIO_WHATSAPP_FROM"]
    numero_para = os.environ["TWILIO_WHATSAPP_TO"]

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

    # WhatsApp tem limite de ~1600 caracteres por mensagem; se passar
    # disso, quebramos em partes.
    partes = [mensagem[i:i + 1500] for i in range(0, len(mensagem), 1500)] or [mensagem]

    for parte in partes:
        resp = requests.post(
            url,
            data={"From": numero_de, "To": numero_para, "Body": parte},
            auth=(account_sid, auth_token),
            timeout=30,
        )
        if resp.status_code >= 300:
            print(f"[ERRO] Falha ao enviar WhatsApp: {resp.status_code} - {resp.text}")
        else:
            print("[OK] Mensagem enviada com sucesso.")


# ----------------------------------------------------------------------
# MONTAGEM DA MENSAGEM
# ----------------------------------------------------------------------

def montar_mensagem(itens_novos):
    linhas = ["📋 *Atualizações - Reforma Tributária*\n"]
    for item in itens_novos:
        linhas.append(f"🔹 *{item['titulo']}* ({item['fonte']})")
        if item["ementa"]:
            linhas.append(item["ementa"])
        linhas.append(item["link"])
        linhas.append("")
    return "\n".join(linhas)


# ----------------------------------------------------------------------
# EXECUÇÃO PRINCIPAL
# ----------------------------------------------------------------------

def main():
    print("Buscando atualizações sobre a reforma tributária...")

    ids_vistos = carregar_historico()
    primeira_execucao = len(ids_vistos) == 0

    todos_encontrados = []
    todos_encontrados += buscar_proposicoes_camara()
    todos_encontrados += buscar_noticias_nfse()
    for pagina in PAGINAS_DOCUMENTOS:
        todos_encontrados += buscar_documentos(pagina)

    print(f"Total de itens encontrados nesta varredura: {len(todos_encontrados)}")

    itens_novos = [item for item in todos_encontrados if item["id"] not in ids_vistos]

    # Na primeiríssima execução, só salvamos a "foto" atual como histórico,
    # sem disparar uma enxurrada de mensagens antigas pro WhatsApp.
    if primeira_execucao:
        print(f"Primeira execução: salvando {len(todos_encontrados)} itens como linha de base, sem notificar.")
        salvar_historico({item["id"] for item in todos_encontrados})
        return

    if not itens_novos:
        print("Nenhuma atualização nova encontrada.")
        return

    print(f"{len(itens_novos)} atualização(ões) nova(s) encontrada(s). Enviando WhatsApp...")

    mensagem = montar_mensagem(itens_novos)
    enviar_whatsapp(mensagem)

    novos_ids = ids_vistos.union(item["id"] for item in itens_novos)
    salvar_historico(novos_ids)


if __name__ == "__main__":
    main()
