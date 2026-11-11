# EX5 Insights

[English](README.md)

Recargas, custos, viagens, autonomia real e saúde da bateria do **Geely EX5** no Home Assistant, com um painel
pronto.

Funciona em cima da [Geely Connect](https://github.com/YossiKon/geely-connect), que é quem fala com o carro. O EX5
Insights acompanha o carro e guarda o que a Geely Connect não guarda: cada recarga e quanto custou, cada viagem e o
caminho feito, quanto o carro roda de verdade com a bateria cheia, e como a bateria se mantém com o tempo.

> Projeto não oficial da comunidade. Sem relação com a Geely nem aprovação dela.

## O que você ganha

Um painel com quatro abas:

- **Overview**: os cartões da Geely Connect já configurados para o seu carro, com a foto e a cor dele (trancar, ar,
  porta-malas, recarga, pneus, portas e a vista de cima), e um mapa de onde o carro está.
- **Uso**: mês a mês, km, recargas (AC/DC), kWh, custo, consumo (kWh/100 km), custo por km, a tabela das recargas do
  mês e gráficos mensais de km e kWh.
- **Autonomia**: a **autonomia real** pelo seu jeito de dirigir (estrada, cidade e geral), quanto a bateria atual
  ainda roda nesse ritmo, a estimativa do próprio carro, a **capacidade real da bateria** e a **saúde da bateria**,
  com gráficos ao longo do tempo.
- **Timeline**: o caminho exato das viagens de qualquer dia, colorido pela velocidade, um calendário de viagens e a
  lista das viagens do mês, cada uma com o link do mapa.

Por trás:

- **Diário de recargas.** Cada recarga é registrada sozinha: início, fim, AC ou DC, local, bateria antes e depois,
  kWh, minutos e odômetro. Continua certo mesmo se o Home Assistant reiniciar no meio: o trecho sem leituras é
  estimado pela potência e pela subida da bateria.
- **Custo por local.** Você marca seus locais de recarga no mapa, cada um com uma regra:
  - **Grátis**: energia solar, casa dos pais, trabalho que paga.
  - **Preço fixo por kWh**: ex.: o fio B que ainda se paga com energia solar.
  - **Perguntar o valor pago**: eletropostos. Tudo fora dos seus locais também pergunta.

  Informe o valor pago e os kWh do eletroposto no painel ou na notificação (o campo de texto da notificação funciona
  no iPhone). Os kWh do eletroposto viram a energia oficial da recarga, porque é o que se paga.
- **Diário de viagens.** Cada viagem de um estacionamento ao seguinte: origem, destino, km, minutos, bateria gasta,
  kWh, consumo, velocidade média e máxima, e o caminho no mapa.
- **Nome do lugar sem internet.** Fora dos seus locais de recarga e das zonas do Home Assistant, a viagem começa ou
  termina numa **cidade**, achada pelos limites oficiais dos 5.570 municípios do Brasil; no Distrito Federal, na
  **região administrativa** (Taguatinga, Plano Piloto…) em vez de "Brasília". Fora do Brasil aparece "Rua".
- **Importar** recargas antigas de uma planilha (CSV) e **exportar** o diário.
- Português (Brasil) e inglês. Fotos do carro em Branco Storm, Cinza Ash, Prata Moon e Preto Carbon.

## Requisitos

- Home Assistant 2025.10 ou mais novo.
- [Geely Connect](https://github.com/YossiKon/geely-connect) instalada e funcionando, com os sensores do carro
  ativados.
- O EX5 Insights precisa rodar **no mesmo Home Assistant da Geely Connect**. A Geely aceita uma sessão por conta:
  entrar com a mesma conta num segundo Home Assistant (uma cópia de teste, por exemplo) derruba a do primeiro.
- Para os avisos: o app do Home Assistant no celular.

## Instalação

1. Adicione o repositório:
   - **Home Assistant 2026.11 ou mais novo:** **Configurações > Marketplace** e, no alto à direita, a opção de
     adicionar um repositório por link; informe `mrslemos/ex5-insights`. Ele pede para conectar o GitHub uma vez.
   - **Até a 2026.10, com o HACS:** ⋮ > **Repositórios personalizados** > adicione
     `https://github.com/mrslemos/ex5-insights` como **Integração**.
2. Instale o **EX5 Insights** e reinicie o Home Assistant.
3. **Configurações > Dispositivos e serviços > Adicionar integração > EX5 Insights**, e escolha o carro, a cor e o
   celular.
4. Na integração, abra **Configurar > Adicionar local de recarga** para cada lugar onde você carrega.
5. Crie o painel: **Configurações > Painéis > Adicionar painel**. Abra o painel e vá em **⋮ > Editar > ⋮ > Editor de
   configuração bruta**. Cole o conteúdo de [`dashboards/ex5_insights.pt-BR.yaml`](dashboards/ex5_insights.pt-BR.yaml)
   (em inglês: [`dashboards/ex5_insights.en.yaml`](dashboards/ex5_insights.en.yaml)).

O painel usa quatro cartões pequenos que vêm com o EX5 Insights e carregam sozinhos, sem instalar mais nada:
`ex5-car-card`, `ex5-map-card`, `ex5-timeline-card` e `ex5-heading`. A aba Overview também precisa dos cartões que vêm
com a Geely Connect. Com mais de um EX5, informe nos cartões `entity:` com o sensor de bateria daquele carro
(`sensor.ex5_battery_…`) e, no cartão da Timeline, `entry:` com o id da integração dele.

A aba Autonomia se preenche conforme você roda. Enquanto as viagens não somam 100% de bateria gasta, os números são uma
prévia, e a capacidade real aparece depois da primeira recarga de 20 pontos ou mais.

## Entidades

| Entidade | O que é |
|---|---|
| `select.ex5_month` | Mês mostrado pelos sensores do mês, pela tabela de recargas e pela lista de viagens |
| `sensor.ex5_month_distance` | Km no mês |
| `sensor.ex5_month_charges` | Recargas no mês (atributos `charges_ac`, `charges_dc`) |
| `sensor.ex5_month_energy` | kWh no mês (atributos `kwh_ac`, `kwh_dc`) |
| `sensor.ex5_month_cost` | Custo no mês (atributo `pending`: recargas ainda sem valor) |
| `sensor.ex5_month_consumption` | kWh/100 km (a partir de 20 km no mês) |
| `sensor.ex5_month_cost_per_km` | Custo por km (a partir de 20 km no mês) |
| `sensor.ex5_month_table` | Número de recargas; os atributos `rows` e `total` alimentam a tabela |
| `sensor.ex5_month_trips` | Número de viagens; o atributo `trips` alimenta a lista |
| `sensor.ex5_last_charge` | Resumo da última recarga |
| `sensor.ex5_last_trip` | Resumo da última viagem |
| `sensor.ex5_session_energy` | kWh da recarga em andamento |
| `sensor.ex5_real_range` (`_highway`, `_city`) | Km por bateria cheia, pelas suas viagens (atributos `preview`, `km`, `battery_pct`, `trips`, `kwh_100km`) |
| `sensor.ex5_range_now` (`_highway`, `_city`) | Quanto a bateria atual roda nesse ritmo |
| `sensor.ex5_car_range`, `sensor.ex5_car_range_full` | Estimativa do próprio carro, agora e levada a 100% |
| `sensor.ex5_battery_capacity` | Capacidade útil real, medida nas recargas |
| `sensor.ex5_battery_health` | Capacidade real ÷ capacidade publicada |
| `sensor.ex5_battery`, `sensor.ex5_odometer` | Bateria e odômetro com nomes fixos, para o painel |
| `binary_sensor.ex5_charging` | Recarga em andamento |
| `binary_sensor.ex5_driving` | Viagem em andamento (atributo `parked_at` com o carro parado) |
| `calendar.ex5_trips` | Um evento por viagem, com horários, bateria, consumo e o link do mapa |
| `number.ex5_pending_cost` | Digite o valor pago da última recarga que espera por ele |
| `number.ex5_pending_station_kwh` | Digite os kWh do eletroposto da última recarga paga |
| `image.ex5_car` | Foto do carro na cor escolhida |

As estatísticas de longo prazo `ex5_insights:energy_ac` e `ex5_insights:energy_dc` alimentam o gráfico de kWh
(inclusive as recargas importadas); `ex5_insights:cost` fica à disposição para os seus próprios gráficos.

Eventos para as suas automações: `ex5_insights_charge_finished` (tipo, local, kWh, custo, minutos, bateria) e
`ex5_insights_trip_finished` (origem, destino, km, minutos, bateria, kWh).

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

## Como funciona

**Recargas.** A recarga começa quando o carregador informa "Charging" ou a potência passa de 0,3 kW, e termina depois
de 3 minutos (ajustável) sem potência e com o carregador parado. AC ou DC vem do atributo `supply` da Geely Connect,
ignorado nos primeiros 90 s (as primeiras leituras de uma recarga AC às vezes dizem DC). A energia é a potência de
carga somada no tempo; trechos sem leitura são estimados pela potência antes e depois, com o limite da subida da
bateria × capacidade.

**Viagens.** A viagem começa quando o odômetro ou o hodômetro parcial passa do valor do estacionamento, e termina
quando os dois ficam parados por 5 minutos com o carro estacionado (freio de mão puxado ou motor desligado), depois de
esperar até 3 minutos pelo GPS da chegada. Com o carro andando, a Geely Connect manda a posição mais ou menos a cada
minuto: esse é o caminho. Viagens de menos de 0,3 km não são registradas. Os kWh da viagem são a bateria gasta ×
capacidade.

**Autonomia real.** Os km das viagens mais recentes até somar 100% de bateria gasta, contando o que o carro gasta
parado (ar, perdas: a bateria no fim de uma viagem ou recarga menos a do começo da seguinte). Estrada são viagens de
10 km ou mais com mais da metade da distância a 70 km/h ou mais, pelo caminho do GPS (sem caminho: mais de 30 km ou
média acima de 60 km/h). As demais são cidade, e dividem o gasto parado na proporção dos km.

**Capacidade da bateria.** Em cada recarga, a energia que entrou no pack (`pack_power` da Geely Connect) entre a
primeira e a última vez que a porcentagem subiu, dividida pelos pontos ganhos. Só recargas de 20 pontos ou mais, até
95% (acima disso a bateria se equilibra e a porcentagem anda devagar), e não quando o Home Assistant reiniciou durante
a recarga. A capacidade é a média das 3 últimas medições, vezes um fator de calibração (1 por padrão; se um app de
OBD2, como o ABRP, mostrar a saúde da bateria, fator = saúde × 60,22 / 100 ÷ capacidade medida). A saúde compara com
os 60,22 kWh publicados. Até a primeira medição, os kWh usam a capacidade publicada.

## Privacidade

Tudo fica no seu Home Assistant; nada é enviado para lugar nenhum. O diário fica em `.storage/ex5_insights.<id>` e os
caminhos das viagens em `ex5_insights/paths/<id>/`, na pasta de configuração, e os dois entram nos backups do Home
Assistant. Os caminhos e os links do mapa têm posições, inclusive onde você estaciona em casa: só aparecem para quem
está logado no seu Home Assistant (a API da Timeline exige login). As coordenadas dos seus locais de recarga não
aparecem nos atributos das entidades.

## Dados do mapa

Os nomes de cidades e regiões vêm de dados públicos que acompanham a integração: os limites municipais do IBGE, a
lista [kelvins/municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros) (MIT) e as regiões
administrativas do Distrito Federal (GDF, IPE-DF). Detalhes e licenças em
[`geo/SOURCES.md`](custom_components/ex5_insights/geo/SOURCES.md).

## Desenvolvimento

`python3 -m unittest discover tests` roda os testes da lógica pura (sem precisar do Home Assistant).
`python3 scripts/make_dashboards.py` gera os painéis nas duas línguas.

## Licença

MIT. Fotos do carro: não use fotos oficiais nem o logotipo da Geely.
