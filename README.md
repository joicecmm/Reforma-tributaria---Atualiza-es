# Robô de Monitoramento — Reforma Tributária

Monitora atualizações sobre a Reforma Tributária e envia um resumo
automático para o seu WhatsApp, todos os dias.

## Fontes monitoradas

1. **Câmara dos Deputados** (API de Dados Abertos) — proposições
   sobre reforma tributária, IBS, CBS, imposto seletivo.
2. **Notícias do Portal NFS-e** (gov.br/nfse/noticias) — notícias
   institucionais, muitas relacionadas à Reforma Tributária do Consumo.
3. **Documentação Atual NFS-e** — guias, manuais e anexos oficiais;
   avisa quando um arquivo novo (ou uma nova versão) é publicado.
4. **RTC NFS-e** — Notas Técnicas específicas sobre as adaptações da
   NFS-e para o IBS/CBS.

## ⚠️ Importante: primeira execução

Na primeiríssima vez que o robô rodar, ele vai encontrar dezenas de
itens "novos" (proposições antigas, notícias antigas, documentos já
existentes) — afinal, tudo é novo para ele. Para não te inundar de
WhatsApp de uma vez só, a primeira execução **apenas salva tudo como
histórico, sem enviar mensagem nenhuma**. A partir da segunda
execução em diante, só chegam as novidades reais.

---

## Passo a passo de configuração

### 1. Criar conta no Twilio (gratuito para testar)

1. Acesse https://www.twilio.com/try-twilio e crie uma conta gratuita.
2. No painel (Console), acesse **Messaging >> Try it out >> Send a WhatsApp message**
   (ou busque por "WhatsApp Sandbox" no menu).
3. Você verá um número do tipo `+1 415 523 8886` e um código como
   `join palavra-exemplo`.
4. Pelo **seu WhatsApp**, envie esse código (`join palavra-exemplo`) para
   o número informado. Isso libera o envio de mensagens do sandbox para
   o seu número (válido por 72h — depois de esse prazo, basta reenviar
   o código caso o robô pare de te alcançar; para uso permanente sem
   precisar renovar, veja a seção "Passar para produção" abaixo).
5. Anote, no Console do Twilio:
   - **Account SID**
   - **Auth Token**
   - O número do sandbox (formato: `whatsapp:+14155238886`)
   - Seu próprio número no formato `whatsapp:+55DDXXXXXXXXX`

### 2. Criar o repositório no GitHub

1. Crie um repositório novo (pode ser privado) no GitHub.
2. Suba todos os arquivos desta pasta para o repositório
   (`main.py`, `requirements.txt`, `.github/workflows/monitor.yml`,
   este `README.md`).

### 3. Configurar as credenciais (Secrets) no GitHub

1. No repositório, vá em **Settings >> Secrets and variables >> Actions**.
2. Clique em **New repository secret** e crie os 4 secrets abaixo:

| Nome                     | Valor                                  |
|--------------------------|-----------------------------------------|
| `TWILIO_ACCOUNT_SID`     | Seu Account SID do Twilio               |
| `TWILIO_AUTH_TOKEN`      | Seu Auth Token do Twilio                |
| `TWILIO_WHATSAPP_FROM`   | `whatsapp:+14155238886` (número sandbox)|
| `TWILIO_WHATSAPP_TO`     | `whatsapp:+55DDXXXXXXXXX` (seu número)  |

### 4. Testar manualmente

1. No repositório, vá na aba **Actions**.
2. Clique no workflow **Monitor Reforma Tributária**.
3. Clique em **Run workflow** para testar imediatamente, sem esperar o
   agendamento automático.
4. **Na primeira execução, nenhuma mensagem é enviada** (o robô só
   salva a linha de base — veja a seção "Primeira execução" acima).
   Para confirmar que tudo está funcionando de ponta a ponta, rode o
   workflow uma segunda vez logo em seguida: se alguma fonte tiver
   mudado entre as duas execuções, você recebe a mensagem no WhatsApp.

Pronto — a partir daí, o robô roda sozinho todos os dias às 08h
(horário de Brasília), sem precisar do seu computador ligado.

---

## Passar para produção (opcional)

O modo sandbox do Twilio expira o vínculo do seu número a cada 72h e
tem uma marca d'água ("sent from your Twilio trial account"). Para uso
contínuo e definitivo:

1. No Console do Twilio, solicite acesso ao **WhatsApp Business API**
   (requer cadastro de um número e aprovação da Meta — leva alguns dias).
2. Após aprovado, troque o valor do secret `TWILIO_WHATSAPP_FROM` pelo
   novo número aprovado.

Isso é opcional — o modo sandbox já funciona bem para uso pessoal,
desde que você reenvie o código `join ...` a cada 72h caso o robô
pare de te alcançar.

---

## Personalizando o robô

- **Adicionar/remover termos de busca na Câmara**: edite a lista
  `TERMOS_BUSCA_CAMARA` no início do `main.py`.
- **Ajustar a janela de dias verificada**: `DIAS_JANELA_CAMARA` (padrão
  3 dias) e `DIAS_JANELA_NOTICIAS` (padrão 15 dias) no `main.py`.
- **Mudar o horário de execução**: edite o `cron` em
  `.github/workflows/monitor.yml` (o horário é em UTC; Brasília = UTC-3).
- **Adicionar novas fontes** (Senado, DOU, Comitê Gestor do IBS): crie
  uma nova função `buscar_xxx()` em `main.py`, seguindo o mesmo padrão
  das funções já existentes, e chame-a dentro de `main()`.

## Sobre a confiabilidade do scraping

As fontes do Portal NFS-e (notícias e documentação) são obtidas via
scraping de HTML, e não por uma API oficial — se o gov.br mudar o
layout dessas páginas no futuro, pode ser necessário ajustar os
seletores em `main.py` (funções `buscar_noticias_nfse` e
`buscar_documentos`). Já a fonte da Câmara dos Deputados usa uma API
oficial e estável, com menor risco de quebrar.
