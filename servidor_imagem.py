from flask import Flask, jsonify, request
from GoogleNews import GoogleNews
from flask_caching import Cache
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlunparse
import re

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

def clean_url(url):
    """Limpa a URL removendo parâmetros desnecessários e fragmentos"""
    try:
        # Remove todos os parâmetros após o & se existir
        if '&' in url:
            url = url.split('&')[0]
        
        parsed = urlparse(url)
        # Remove fragmentos e query strings desnecessárias
        clean = parsed._replace(fragment='')
        return urlunparse(clean)
    except Exception as e:
        print(f"Erro ao limpar URL: {e}")
        return url

def get_main_image(soup, base_url):
    """Tenta encontrar a imagem principal da notícia usando diferentes métodos"""
    
    # 1. Tenta encontrar a imagem do OpenGraph primeiro (geralmente a mais relevante)
    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content'):
        return urljoin(base_url, og_image.get('content'))

    # 2. Tenta encontrar a imagem do Twitter Card
    twitter_image = soup.find('meta', {'name': 'twitter:image'})
    if twitter_image and twitter_image.get('content'):
        return urljoin(base_url, twitter_image.get('content'))

    # 3. Procura por classes específicas dos principais portais de notícias brasileiros
    image_classes = [
        'content-media__image',    # G1
        'bstn-fd-picture-image',   # G1
        'image-content',           # UOL
        'aligncenter',             # Diversos portais WordPress
        'featured-image',          # Padrão de diversos sites
        'article-featured-image',  # Diversos portais
        'post-thumbnail',          # Padrão WordPress
        'entry-image',            # Diversos portais
    ]
    
    for class_name in image_classes:
        img = soup.find('img', class_=class_name)
        if img:
            src = img.get('src') or img.get('data-src')
            if src:
                return urljoin(base_url, src)

    # 4. Procura pela primeira imagem dentro do article ou main
    main_content = soup.find(['article', 'main'])
    if main_content:
        first_img = main_content.find('img')
        if first_img:
            src = first_img.get('src') or first_img.get('data-src')
            if src:
                return urljoin(base_url, src)

    # 5. Procura por figure com imagem
    figure = soup.find('figure')
    if figure:
        img = figure.find('img')
        if img:
            src = img.get('src') or img.get('data-src')
            if src:
                return urljoin(base_url, src)

    return None

def fetch_image_from_html(url):
    try:
        cleaned_url = clean_url(url)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(cleaned_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        return get_main_image(soup, cleaned_url)

    except Exception as e:
        print(f"Erro ao buscar imagem para {url}: {str(e)}")
        return None

def fetch_news(query, start=0, count=3):
    googlenews = GoogleNews(lang='pt', region='BR')
    googlenews.search(query)
    results = googlenews.results()[start:start + count]

    news_list = []
    for item in results:
        news_url = item.get('link', '')
        if not news_url:
            continue

        image_url = fetch_image_from_html(news_url)
        
        news_list.append({
            "title": item.get('title', 'Título indisponível'),
            "summary": item.get('desc', 'Resumo indisponível'),
            "url": news_url,
            "date": item.get('date', 'Data não disponível'),
            "image_url": image_url or None
        })

    return news_list

@app.route('/news', methods=['GET'])
@cache.cached(timeout=300, query_string=True)
def get_news():
    query = request.args.get('query')
    start = int(request.args.get('start', 0))
    count = int(request.args.get('count', 7))

    if not query:
        return jsonify({"error": "Query not provided"}), 400

    news_batch = fetch_news(query, start=start, count=count)
    return jsonify(news_batch)

if __name__ == "__main__":
    app.run(debug=True)