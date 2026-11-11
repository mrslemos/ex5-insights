# Map data

Used to name the city (in Brazil) where a trip starts and ends, without any internet service.

| File | What | Source | License |
|---|---|---|---|
| `municipios_contornos.txt` | Boundary of each of the 5,570 Brazilian municipalities, simplified. One line per municipality: `IBGE code;lon lat,lon lat,…|ring…` | IBGE, API de malhas territoriais (malha municipal) | Public data from IBGE (Brazilian Institute of Geography and Statistics); free use with attribution |
| `municipios_br.csv` | Name, state, seat coordinates and bounding box of each municipality, plus the byte offset of its line in the boundaries file | Names and seats: [kelvins/municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros); boxes computed from the IBGE boundaries | MIT (see below) |
| `ras_df.txt` | The administrative regions (RAs) of the Federal District, simplified (~4 m). One line per RA: `Name;lon_min lat_min lon_max lat_max;ring|ring` | GDF, IPE-DF catalog, layer `regioes_administrativas` | Public domain |

In the Federal District the trip shows the administrative region instead of "Brasília". A few recent RAs are shown
together with the one they were split from: Sol Nascente/Pôr do Sol as Ceilândia, Riacho Fundo II as Riacho Fundo,
Sobradinho II as Sobradinho, and Sudoeste/Octogonal as "Sudoeste".

## kelvins/municipios-brasileiros

    MIT License
    
    Copyright (c) 2016 Kelvin S. do Prado
    
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:
    
    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.
    
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
