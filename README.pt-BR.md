# EX5 Insights

[English](README.md)

Diário de recargas, custos e uso mês a mês do **Geely EX5** no Home Assistant.

Funciona em cima da [Geely Connect](https://github.com/YossiKon/geely-connect), que é quem fala com o carro. O EX5
Insights acompanha o carro e guarda o que a Geely Connect não guarda: cada recarga, onde foi, quanto custou e os
números de cada mês.

> Projeto não oficial da comunidade. Sem relação com a Geely nem aprovação dela.

## O que você ganha

- **Diário de recargas.** Cada recarga é registrada sozinha: início, fim, AC ou DC, local, bateria antes e depois,
  kWh, minutos e odômetro. Continua certo mesmo se o Home Assistant reiniciar no meio: o trecho sem leituras é
  estimado pela potência e pela subida da bateria.
- **Custo por local.** Você marca seus locais de recarga no mapa, cada um com uma regra:
  - **Grátis**: energia solar, casa dos pais, trabalho que paga.
  - **Preço fixo por kWh**: ex.: o fio B que ainda se paga com energia solar.
  - **Perguntar o valor pago**: eletropostos. Tudo fora dos seus locais também pergunta.

  Para informar o valor pago e os kWh do eletroposto, use os campos do painel ou a notificação (o campo de texto da
  notificação funciona no iPhone). Os kWh do eletroposto viram a energia oficial da recarga, porque é o que se paga.
- **Visão do mês.** Um seletor de mês com km, recargas (AC/DC), kWh, custo, consumo (kWh/100 km), custo por km e
  uma tabela com as recargas do mês (dia, hora, kWh, R$/kWh, total).
- **Gráficos por mês** de kWh (AC e DC) e de custo, a partir do diário, então as recargas importadas também entram.
- **Importar** recargas antigas de uma planilha (CSV) e **exportar** o diário.
- **A foto do seu carro** na cor dele: Branco Storm, Cinza Ash, Prata Moon ou Preto Carbon.
- Português (Brasil) e inglês.

## Requisitos

- Home Assistant 2025.10 ou mais novo.
- [Geely Connect](https://github.com/YossiKon/geely-connect) instalada e funcionando, com os sensores do carro
  ativados.
- Para os avisos: o app do Home Assistant no celular.

## Instalação

1. No HACS: ⋮ > **Repositórios personalizados** > adicione `https://github.com/mrslemos/ex5-insights` como
   **Integração**.
2. Instale o **EX5 Insights** e reinicie o Home Assistant.
3. **Configurações > Dispositivos e serviços > Adicionar integração > EX5 Insights**, e escolha o carro, a cor e o
   celular.
4. Na integração, abra **Configurar > Adicionar local de recarga** para cada lugar onde você carrega.
5. Crie um painel: **Configurações > Painéis > Adicionar painel**. Abra o painel e vá em **⋮ > Editar > ⋮ > Editor
   de configuração bruta**. Cole o conteúdo de
   [`dashboards/ex5_insights.pt-BR.yaml`](dashboards/ex5_insights.pt-BR.yaml).

## Entidades

| Entidade | O que é |
|---|---|
| `select.ex5_month` | Mês mostrado pelos sensores do mês e pela tabela |
| `sensor.ex5_month_distance` | Km no mês |
| `sensor.ex5_month_charges` | Recargas no mês (atributos `charges_ac`, `charges_dc`) |
| `sensor.ex5_month_energy` | kWh no mês (atributos `kwh_ac`, `kwh_dc`) |
| `sensor.ex5_month_cost` | Custo no mês (atributo `pending`: recargas ainda sem valor) |
| `sensor.ex5_month_consumption` | kWh/100 km (a partir de 20 km no mês) |
| `sensor.ex5_month_cost_per_km` | Custo por km (a partir de 20 km no mês) |
| `sensor.ex5_month_table` | Número de recargas; os atributos `rows` e `total` alimentam a tabela |
| `sensor.ex5_last_charge` | Resumo da última recarga |
| `sensor.ex5_session_energy` | kWh da recarga em andamento |
| `binary_sensor.ex5_charging` | Recarga em andamento |
| `number.ex5_pending_cost` | Digite o valor pago da última recarga que espera por ele |
| `number.ex5_pending_station_kwh` | Digite os kWh do eletroposto da última recarga paga |
| `image.ex5_car` | Foto do carro (se houver imagem para a cor escolhida) |

As estatísticas de longo prazo `ex5_insights:energy_ac`, `ex5_insights:energy_dc` e `ex5_insights:cost` alimentam
os gráficos.

O evento `ex5_insights_charge_finished` é disparado no fim de cada recarga (tipo, local, kWh, custo, minutos,
bateria), para as suas próprias automações.

## Serviços

| Serviço | O que faz |
|---|---|
| `ex5_insights.set_charge_cost` | Valor pago numa recarga (a pendente mais recente, ou `charge_id`) |
| `ex5_insights.set_charge_energy` | kWh do eletroposto numa recarga |
| `ex5_insights.set_month_distance` | Km de um mês sem dados do odômetro (ex.: antes da instalação) |
| `ex5_insights.import_charges` | Acrescenta recargas de um CSV na pasta de configuração |
| `ex5_insights.export_charges` | Grava o diário em CSV |
| `ex5_insights.delete_charge` | Esconde uma recarga (`restore: true` traz de volta) |

### Importar recargas antigas

Salve a planilha como CSV na pasta de configuração (por exemplo com o complemento File editor) e chame
`ex5_insights.import_charges` com `file: recargas.csv`. Colunas, em português ou inglês, em qualquer ordem:

| Coluna | Obrigatória | Exemplos |
|---|---|---|
| `data` / `date` | sim | `15/01/2026`, `2026-01-15`, `15/01/2026 14:28` |
| `carga kwh` / `kwh` | sim | `42,77`, `42.77` |
| `hora` / `time` | não | `14:28` (sem ela, a tabela mostra —) |
| `tipo` / `type` | não | `AC`, `DC` (sem ela: DC acima de 22 kW de `potência kw`, senão AC) |
| `valor total` / `custo` / `cost` | não | `R$ 55,18`, `55.18` (vazio = valor a informar) |
| `local`, `minutos` / `tempo (min)`, `odômetro`, `potência kw` | não | |

Recargas no mesmo dia e com os mesmos kWh são puladas, então importar duas vezes não duplica.

## Como a recarga é detectada

- **Começa** quando o carregador informa "Charging" ou a potência passa de 0,3 kW.
- **AC ou DC** vem do atributo `supply` da Geely Connect. Ele é ignorado nos primeiros 90 s, porque as primeiras
  leituras de uma recarga AC às vezes vêm do lado da bateria e dizem DC.
- A **energia** é a potência de carga somada no tempo. Trechos sem leitura (Home Assistant reiniciando, carro que
  só avisa minutos depois de começar) são estimados pela potência antes e depois, com o limite da subida da
  bateria × capacidade. Sem nenhuma potência, usa a subida da bateria × capacidade.
- **Termina** depois de 3 minutos (ajustável) sem potência e com o carregador parado.

## Privacidade

Tudo fica no seu Home Assistant (`.storage/ex5_insights.<id>`). As coordenadas dos locais não aparecem nos
atributos das entidades. Nada é enviado para lugar nenhum.

## Licença

MIT. Imagens do carro: não use fotos oficiais nem o logotipo da Geely.
