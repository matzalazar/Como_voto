import requests, re
from bs4 import BeautifulSoup

for year in [2015, 2023]:
    url=f'https://www.senado.gob.ar/votaciones/actas?periodo={year}&page=1'
    r=requests.get(url)
    soup=BeautifulSoup(r.text, 'lxml')
    ids=[re.search(r'/votaciones/detalleActa/(\d+)', l['href']).group(1)
         for l in soup.find_all('a', href=re.compile(r'/votaciones/detalleActa/'))]
    print(year, ids[:10])
