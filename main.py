"""
Robô de monitoramento da Reforma Tributária.

O que ele faz:
1. Consulta a API de Dados Abertos da Câmara dos Deputados buscando
   proposições relacionadas à reforma tributária (IBS, CBS, LC 214, etc.)
2. Compara com o que já foi visto anteriormente (arquivo seen_items.json)
3. Envia as novidades encontradas para o WhatsApp via Twilio

Fontes monitoradas:
- API da Câmara dos Deputados (dadosabertos.camara.leg.br) — pública, sem
  necessidade de chave de API.

Para adicionar novas fontes (DOU, Senado, Comitê Gestor do IBS etc.),
basta criar uma nova função "buscar_xxx()" seguindo o mesmo padrão e
chamá-la dentro de main().
"""

import os
import json
import requests
from datetime import datetime, timedelta

# ----------------------------------------------------------------------
# CONFIGURAÇÕES
# ----------------------------------------------------------------------

# Termos de busca na API da Câmara. Pode adicionar/remover livremente.
TERMOS_BUSCA = [
    "reforma tributária",
    "IBS",
    "CBS",
    "imposto seletivo",
]

ARQUIVO_HISTORICO = "seen_items.json"

# Quantos dias para trás verificar (evita pegar histórico antigo na
# primeira execução e mantém a busca sempre "fresca")
DIAS_JANELA = 3


# ----------------------------------------------------------------------
# BUSCA NA API DA CÂMARA DOS DEPUTADOS
# ----------------------------------------------------------------------

def buscar_proposicoes_camara():
    """
    Busca proposições recentes na API da Câmara dos Deputados
    relacionadas aos termos de busca definidos.
    Documentação: https://dadosabertos.camara.leg.br/swagger/api.html
    """
    data_inicio = (datetime.now() - timedelta(days=DIAS_JANELA)).strftime("%Y-%m-%d")
    url = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"

    encontrados = []
    ids_ja_processados = set()

    for termo in TERMOS_BUSCA:
        params = {
            "keywords": termo,
            "dataApresentacaoInicio": data_inicio,
            "ordem": "DESC",
            "ordenarPor": "id",
            "itens": 20,
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            dados = resp.json().get("dados", [])
        except requests.RequestException as e:
            print(f"[ERRO] Falha ao buscar termo '{termo}': {e}")
            continue

        for item in dados:
            prop_id = item.get("id")
            if prop_id in ids_ja_processados:
                continue
            ids_ja_processados.add(prop_id)

            encontrados.append({
                "id": str(prop_id),
                "fonte": "Câmara dos Deputados",
                "titulo": f"{item.get('siglaTipo')} {item.get('numero')}/{item.get('ano')}",
                "ementa": item.get("ementa", "").strip(),
                "link": f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={prop_id}",
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
            ementa_resumida = item["ementa"]
            if len(ementa_resumida) > 200:
                ementa_resumida = ementa_resumida[:200] + "..."
            linhas.append(ementa_resumida)
        linhas.append(item["link"])
        linhas.append("")
    return "\n".join(linhas)


# ----------------------------------------------------------------------
# EXECUÇÃO PRINCIPAL
# ----------------------------------------------------------------------

def main():
    print("Buscando atualizações sobre a reforma tributária...")

    ids_vistos = carregar_historico()
    todos_encontrados = buscar_proposicoes_camara()

    itens_novos = [item for item in todos_encontrados if item["id"] not in ids_vistos]

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
