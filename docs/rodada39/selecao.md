# Rodada 39: os casos essenciais (2026-10-21, D97)

Pedido do usuário: "Considere todos os casos disponíveis. Alguns talvez cubram coisas que outros já cobrem. Selecione
todos que forem essenciais para testar todas as lacunas e deixe de fora os que estariam apenas repetindo algo que já
foi testado. Então, rode."

Código da D96. Uma execução de cada caso, no Studio. A cobertura de cada ramo está em
`docs/analise_erros/cobertura_ramos.md`; os casos 01 a 03 são da banca e ficam sempre.

## Entram (64)

- Treino: 01, 02, 03, 04, 05, 07, 08, 09, 10, 11, 13, 14, 15, 16, 17
- Novos: 18, 19, 20, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 50
- Teste: 43, 44, 45, 48, 51, 53, 54, 57, 58, 59, 62, 63, 64, 65, 66, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79

Além dos ramos do mapa: 18 (consulta de psiquiatria não conta como sessão, art. 35, parágrafo único), 25 (recibo de
"consulta" de psicóloga é sessão de terapia, pelo conselho), 59 (pergunta hipotética sobre outro plano), 08 e 31 (a
condição de saúde, D96).

## Ficam de fora (13), porque repetem um ramo já coberto

| Caso | Ramo | Coberto por |
|---|---|---|
| 12 | pedido próprio e de outra pessoa | 01 |
| 22 | item excluído discriminado sai do cálculo | 72 |
| 42 | vários itens, cada um com o seu teto | 54, 77 |
| 46 | procedimento excluído → negado | 32, 65 |
| 47 | situação de pedido anterior | 50, 64 |
| 49 | sessão de terapia aprovada, pergunta sobre recibo mensal | 29, 41 |
| 52 | pedido médico recebido → aprovado | 19 |
| 55 | sessão de terapia aprovada, perguntas sobre limite e relatório | 38, 02 |
| 56 | despesa de saúde marcada inválida → excluída | 65 |
| 60 | relatório exigido pela sessão e recebido depois | 02 |
| 61 | carência não cumprida | 07, 25 |
| 67 | telessaúde com o teto da consulta | 51, 75 |
| 68 | segunda consulta em 15 dias (art. 36) | 54 |
