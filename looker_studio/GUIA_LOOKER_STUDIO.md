# Painel no Looker Studio

Os dados estão em [`dados/`](dados) (gerados por `python -m funnel.pipeline`). Duas formas de conectar:

- **Rápida:** suba os CSVs no Google Sheets (um por aba) e use o conector **Planilhas Google**.
- **Produção:** carregue no BigQuery (`bq load --autodetect funnel.sessoes_diarias dados/sessoes_diarias.csv`) ou aponte direto para as tabelas criadas por `sql/bigquery/01_stg_events.sql` + `sql/02..08`.

## Fontes de dados

| Fonte | Arquivo | Granularidade |
|---|---|---|
| Sessões diárias | `sessoes_diarias.csv` | data × canal × device × campanha |
| Funil | `funil_etapas.csv` | etapa |
| Eficiência por canal | `eficiencia_canal.csv` | canal |
| Eficiência por campanha | `eficiencia_campanha.csv` | campanha |
| Atribuição | `atribuicao.csv` | modelo × canal |
| QA de tracking | `qa_tracking.csv` | teste |
| Coortes | `coortes.csv` | semana |

## Campos calculados (na fonte "Sessões diárias")

```
Taxa de conversão     = SUM(cadastros) / SUM(sessoes)
Taxa de engajamento   = SUM(engajadas) / SUM(sessoes)
Conclusão onboarding  = SUM(cadastros) / SUM(inicios_onboarding)
CTR do CTA            = SUM(cliques_cta) / SUM(engajadas)
```

Na fonte "Eficiência por canal": `CAC = SUM(custo) / SUM(contas)` e `ROAS 12m = SUM(receita_anual_estimada) / SUM(custo)`.

## Páginas

1. **Visão geral:** scorecards (sessões, cadastros, taxa de conversão, conclusão do onboarding) com comparação ao período anterior; série temporal de cadastros por canal; controles de data, canal e dispositivo.
2. **Funil:** gráfico de funil (`funil_etapas`: etapa × volume) e tabela com conversão e abandono por etapa; barras de conversão por canal × dispositivo.
3. **Mídia:** tabela de campanhas (custo, CTR, CPC, custo por cadastro) com barras de dados; dispersão CAC × taxa de ativação por canal.
4. **Atribuição:** barras agrupadas de conversões por canal em cada modelo (filtro de modelo como controle).
5. **Qualidade dos dados:** tabela `qa_tracking` com formatação condicional por severidade e um scorecard de "% de sessões com UTM fora do padrão".

## Boas práticas
- Tema com as cores da marca e **uma** cor de destaque para o KPI principal.
- Filtros no nível do relatório (data e canal) para todas as páginas.
- Descrição de cada métrica no próprio campo, que aparece no tooltip do Looker.
- Em BigQuery, use tabelas **particionadas por data** para o painel não varrer o histórico inteiro a cada clique.
