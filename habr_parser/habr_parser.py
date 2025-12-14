#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер постов Habr по поисковому запросу
Автор: Habr Parser v1.0
Дата: 2025-10-23

Описание:
Этот парсер извлекает данные из постов на сайте Habr.com по заданному поисковому запросу.
Собирает заголовки, текст статей, авторов, количество реакций, просмотров, комментарии и другие метаданные.
Результаты сохраняются в JSON файл.

Зависимости:
pip install requests beautifulsoup4 lxml

Использование:
python habr_parser.py
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from urllib.parse import urljoin
from datetime import datetime
from collections import Counter


class HabrParser:
    """Класс для парсинга постов с сайта Habr.com"""

    def __init__(self):
        self.base_url = "https://habr.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        self.all_posts_data = []

    def get_page_content(self, url):
        """Получает содержимое страницы с повторными попытками"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                print(f"Попытка {attempt + 1}/{max_retries} неудачна для {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    print(f"Не удалось получить страницу после {max_retries} попыток")
                    return None

    def extract_search_results(self, search_url):
        """Извлекает ссылки на посты из страницы поиска"""
        content = self.get_page_content(search_url)
        if not content:
            return []

        soup = BeautifulSoup(content, 'html.parser')
        post_links = []

        # Различные селекторы для поиска ссылок на посты
        selectors = [
            'h2.tm-title a',
            'h1.tm-title a',
            'a[href*="/articles/"]',
            'a[href*="/posts/"]',
        ]

        for selector in selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href:
                    full_url = urljoin(self.base_url, href)
                    if full_url not in post_links:
                        post_links.append(full_url)

        # Фильтруем уникальные ссылки
        unique_links = []
        for link in post_links:
            if ('/articles/' in link or '/posts/' in link) and link not in unique_links:
                unique_links.append(link)

        return unique_links

    def parse_number_with_suffix(self, text):
        """Парсит числа с суффиксами (K, к, M, м)"""
        if not text:
            return 0

        text = text.replace(',', '.').replace(' ', '')
        match = re.search(r'(\d+(?:\.\d+)?)\s*([KkМм]?)', text)
        if match:
            number = float(match.group(1))
            suffix = match.group(2).lower()
            if suffix in ['k', 'к']:
                return int(number * 1000)
            elif suffix in ['m', 'м']:
                return int(number * 1000000)
            else:
                return int(number)
        return 0

    def extract_post_data(self, post_url):
        """Извлекает все данные из отдельного поста"""
        content = self.get_page_content(post_url)
        if not content:
            return None

        soup = BeautifulSoup(content, 'html.parser')
        post_data = {
            'url': post_url,
            'title': '',
            'author': '',
            'author_info': {},
            'content': '',
            'content_html': '',
            'views_count': 0,
            'reactions_count': 0,
            'comments_count': 0,
            'comments': [],
            'publication_date': '',
            'publication_time': '',
            'tags': [],
            'hubs': [],
            'reading_time': '',
            'difficulty': '',
            'company': ''
        }

        try:
            # Заголовок
            title_elem = soup.select_one('h1.tm-title, h1.tm-article-title__title, h1')
            if title_elem:
                post_data['title'] = title_elem.get_text(strip=True)

            # Автор
            author_elem = soup.select_one('a.tm-user-info__username, .tm-user-info__user a')
            if author_elem:
                post_data['author'] = author_elem.get_text(strip=True)
                post_data['author_info']['profile_url'] = urljoin(self.base_url, author_elem.get('href', ''))

            # Карма автора
            karma_elem = soup.select_one('.tm-user-info__stats-item_karma .tm-user-info__stats-counter')
            if karma_elem:
                post_data['author_info']['karma'] = karma_elem.get_text(strip=True)

            # Содержимое статьи
            content_elem = soup.select_one('.tm-article-body, .tm-article-presenter__body, .post__text')
            if content_elem:
                post_data['content'] = content_elem.get_text(separator='\n', strip=True)
                post_data['content_html'] = str(content_elem)

            # Просмотры
            views_elem = soup.select_one('.tm-icon-counter__value')
            if views_elem:
                views_text = views_elem.get_text(strip=True)
                post_data['views_count'] = self.parse_number_with_suffix(views_text)

            # Рейтинг
            rating_elem = soup.select_one('.tm-votes-meter__value, .tm-vote__counter')
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                rating_match = re.search(r'[+-]?(\d+)', rating_text)
                if rating_match:
                    post_data['reactions_count'] = int(rating_match.group(1))

            # Комментарии
            comments_elem = soup.select_one('a[href*="/comments/"], .tm-article-comments-counter')
            if comments_elem:
                comments_text = comments_elem.get_text(strip=True)
                comments_match = re.search(r'(\d+)', comments_text)
                if comments_match:
                    post_data['comments_count'] = int(comments_match.group(1))

            # Дата публикации
            time_elem = soup.select_one('time')
            if time_elem:
                datetime_str = time_elem.get('datetime', '')
                if datetime_str:
                    post_data['publication_date'] = datetime_str
                    try:
                        dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                        post_data['publication_time'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        post_data['publication_time'] = time_elem.get_text(strip=True)

            # Теги
            for tag_elem in soup.select('.tm-separated-list a, .tm-tags a'):
                tag_text = tag_elem.get_text(strip=True)
                if tag_text and tag_text not in post_data['tags']:
                    post_data['tags'].append(tag_text)

            # Хабы
            for hub_elem in soup.select('.tm-article-hubs a, .tm-hubs a'):
                hub_text = hub_elem.get_text(strip=True)
                if hub_text and hub_text not in post_data['hubs']:
                    post_data['hubs'].append(hub_text)

            # Время чтения
            reading_time_elem = soup.select_one('.tm-article-reading-time__label')
            if reading_time_elem:
                post_data['reading_time'] = reading_time_elem.get_text(strip=True)

            # Сложность
            difficulty_elem = soup.select_one('.tm-article-complexity')
            if difficulty_elem:
                post_data['difficulty'] = difficulty_elem.get_text(strip=True)

            # Компания
            company_elem = soup.select_one('.tm-company-info__name a')
            if company_elem:
                post_data['company'] = company_elem.get_text(strip=True)

        except Exception as e:
            print(f"Ошибка при извлечении данных поста: {e}")

        return post_data

    def extract_comments(self, post_url):
        """Извлекает комментарии к посту"""
        if '/comments/' not in post_url:
            comments_url = post_url.rstrip('/') + '/comments/'
        else:
            comments_url = post_url

        content = self.get_page_content(comments_url)
        if not content:
            return []

        soup = BeautifulSoup(content, 'html.parser')
        comments = []

        try:
            comment_items = soup.select('.tm-comment-thread__comment, .tm-comment')

            for comment_item in comment_items:
                comment_data = {
                    'author': '',
                    'content': '',
                    'timestamp': '',
                    'rating': 0,
                    'level': 0
                }

                # Автор
                author_elem = comment_item.select_one('.tm-user-info__username, .tm-comment__username a')
                if author_elem:
                    comment_data['author'] = author_elem.get_text(strip=True)

                # Содержимое
                content_elem = comment_item.select_one('.tm-comment__body-content, .tm-comment-body')
                if content_elem:
                    comment_data['content'] = content_elem.get_text(separator='\n', strip=True)

                # Время
                time_elem = comment_item.select_one('time')
                if time_elem:
                    comment_data['timestamp'] = time_elem.get('datetime', '')

                # Рейтинг
                rating_elem = comment_item.select_one('.tm-comment-thread__comment-rating, .tm-votes-meter__value')
                if rating_elem:
                    rating_text = rating_elem.get_text(strip=True)
                    rating_match = re.search(r'[+-]?(\d+)', rating_text)
                    if rating_match:
                        comment_data['rating'] = int(rating_match.group(1))

                if comment_data['content'] or comment_data['author']:
                    comments.append(comment_data)

        except Exception as e:
            print(f"Ошибка при извлечении комментариев: {e}")

        return comments

    def parse_search_page(self, search_url, max_posts=None):
        """Парсит страницу поиска и все найденные посты"""
        print(f"🔍 Начинаем парсинг: {search_url}\n")

        post_links = self.extract_search_results(search_url)
        print(f"📊 Найдено {len(post_links)} постов\n")

        if not post_links:
            print("⚠️  Не удалось найти посты")
            return []

        if max_posts:
            post_links = post_links[:max_posts]
            print(f"ℹ️  Ограничиваемся {max_posts} постами\n")

        for i, post_url in enumerate(post_links, 1):
            print(f"[{i}/{len(post_links)}] {post_url}")

            post_data = self.extract_post_data(post_url)
            if post_data and post_data['title']:
                post_data['comments'] = self.extract_comments(post_url)
                self.all_posts_data.append(post_data)
                print(f"    ✓ {post_data['title'][:60]}...")
                print(f"    📝 Комментариев: {len(post_data['comments'])}\n")
            else:
                print(f"    ✗ Не удалось извлечь данные\n")

            time.sleep(1)

        return self.all_posts_data

    def save_to_json(self, filename='habr_posts_data.json'):
        """Сохраняет данные в JSON файл"""
        try:
            output_data = {
                'metadata': {
                    'parsing_date': datetime.now().isoformat(),
                    'total_posts': len(self.all_posts_data),
                    'total_comments': sum(len(post['comments']) for post in self.all_posts_data),
                    'parser_version': '1.0'
                },
                'posts': self.all_posts_data
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)

            print(f"\n✅ Данные сохранены: {filename}")
            print(f"   Постов: {len(self.all_posts_data)}")
            print(f"   Комментариев: {sum(len(post['comments']) for post in self.all_posts_data)}")

            return filename
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
            return None

    def print_statistics(self):
        """Выводит детальную статистику"""
        if not self.all_posts_data:
            print("Нет данных")
            return

        print("\n" + "="*60)
        print("СТАТИСТИКА ПАРСИНГА")
        print("="*60)

        total_posts = len(self.all_posts_data)
        total_comments = sum(len(post['comments']) for post in self.all_posts_data)
        total_views = sum(post['views_count'] for post in self.all_posts_data)
        total_reactions = sum(post['reactions_count'] for post in self.all_posts_data)

        print(f"Постов обработано: {total_posts}")
        print(f"Комментариев собрано: {total_comments}")
        print(f"Просмотров всего: {total_views:,}")
        print(f"Реакций всего: {total_reactions}")

        if total_posts > 0:
            print(f"\nСреднее на пост:")
            print(f"  Комментариев: {total_comments/total_posts:.1f}")
            print(f"  Просмотров: {total_views/total_posts:,.0f}")
            print(f"  Реакций: {total_reactions/total_posts:.1f}")

        # Популярные теги
        all_tags = []
        for post in self.all_posts_data:
            all_tags.extend(post['tags'])

        if all_tags:
            popular_tags = Counter(all_tags).most_common(5)
            print(f"\nТоп-5 тегов:")
            for tag, count in popular_tags:
                print(f"  • {tag}: {count}")

        # Активные авторы
        authors = [post['author'] for post in self.all_posts_data if post['author']]
        if authors:
            popular_authors = Counter(authors).most_common(3)
            print(f"\nТоп-3 авторов:")
            for author, count in popular_authors:
                print(f"  • {author}: {count} постов")

        print("="*60)


def main():
    """Основная функция запуска парсера"""
    # URL страницы поиска
    search_url = "https://habr.com/ru/search/?q=поиск+работы+&target_type=posts&order=relevance&hf=similar_posts_202412_B"

    # Создаем парсер
    parser = HabrParser()

    # НАСТРОЙКИ ПАРСИНГА
    # Установите max_posts=None для парсинга всех постов
    # или укажите число для ограничения (например, max_posts=10)
    MAX_POSTS = 40  # Можно изменить на нужное количество

    # Парсим
    parser.parse_search_page(search_url, max_posts=MAX_POSTS)

    # Сохраняем результаты
    parser.save_to_json('habr_posts_data.json')

    # Выводим статистику
    parser.print_statistics()


if __name__ == "__main__":
    main()
