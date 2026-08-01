# Robô de Monitoramento — Reforma Tributária

Monitora atualizações sobre a Reforma Tributária e mostra tudo em um
resumo visual, direto na aba **Actions** do GitHub. Não envia nada
por WhatsApp, e-mail ou qualquer outro canal — é só para
visualização.

## Fontes monitoradas

1. **Câmara dos Deputados** (API de Dados Abertos) — proposições
   sobre reforma tributária, IBS, CBS, imposto seletivo.
2. **Notícias do Portal NFS-e** (gov.br/nfse/noticias) — notícias
   institucionais, muitas relacionadas à Reforma Tributária do Consumo.
   O robô traz o **texto completo** de cada notícia, não só o resumo.
3. **Documentação Atual NFS-e** — guias, manuais e anexos oficiais;
   sinaliza quando um arquivo novo (ou uma nova versão) é publicado.
4. **RTC NFS-e** — Notas Técnicas específicas sobre as adaptações da
   NFS-e para o IBS/CBS.

---

## Passo a passo de configuração

### 1. Criar o repositório no GitHub

1. Crie um repositório novo (pode ser privado) no GitHub.
2. Suba todos os arquivos desta pasta para o repositório
   (`main.py`, `requirements.txt`, `.github/workflows/monitor.yml`,
   este `README.md`), mantendo a mesma estrutura de pastas.

### 2. Testar manualmente

1. No repositório, vá na aba **Actions**.
2. Clique no workflow **Monitor Reforma Tributária**.
3. Clique em **Run workflow** para rodar imediatamente, sem esperar o
   agendamento automático.
4. Quando terminar, clique na execução — o resumo completo aparece
   automaticamente no **topo da página** (a seção "Summary"), com
   título, texto completo de cada notícia e link para a fonte
   original, agrupado por fonte.

Pronto — a partir daí, o robô roda sozinho todos os dias às 08h
(horário de Brasília), sem precisar do seu computador ligado, e o
resultado de cada execução fica disponível na aba Actions.

---

## Onde ver os resultados

- Vá em **Actions** → clique em qualquer execução → o resumo aparece
  automaticamente no topo, formatado, agrupado por fonte, com o texto
  completo de cada notícia e o marcador 🆕 nos itens que ainda não
  tinham aparecido em execuções anteriores.
- Se quiser o log bruto (linha por linha, útil para depurar erros),
  clique em **monitorar >> Executar robô** para expandir os `print()`.
- O arquivo `seen_items.json`, salvo automaticamente na raiz do
  repositório, guarda o histórico de tudo que já foi visto — serve só
  para o robô saber o que já apareceu antes (e marcar como 🆕 o que é
  realmente novo), não precisa mexer nele.

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
seletores em `main.py` (funções `buscar_noticias_nfse`,
`buscar_texto_completo_noticia` e `buscar_documentos`). Já a fonte da
Câmara dos Deputados usa uma API oficial e estável, com menor risco
de quebrar.
