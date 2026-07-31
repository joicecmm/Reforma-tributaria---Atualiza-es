# Robô de Monitoramento — Reforma Tributária

Monitora atualizações sobre a Reforma Tributária na API da Câmara dos
Deputados e envia um resumo automático para o seu WhatsApp, todos os dias.

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
4. Se tudo estiver certo, você recebe a mensagem no WhatsApp em
   poucos segundos.

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

- **Adicionar/remover termos de busca**: edite a lista `TERMOS_BUSCA`
  no início do `main.py`.
- **Mudar o horário de execução**: edite o `cron` em
  `.github/workflows/monitor.yml` (o horário é em UTC; Brasília = UTC-3).
- **Adicionar novas fontes** (Senado, DOU, Comitê Gestor do IBS): crie
  uma nova função `buscar_xxx()` em `main.py`, seguindo o mesmo padrão
  da função `buscar_proposicoes_camara()`, e chame-a dentro de `main()`.
