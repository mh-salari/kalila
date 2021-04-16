#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Apr 5 2021
@author: MohammadHossein Salari
@email: mohammad.hossein.salari@gmail.com
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from tqdm import tqdm
import concurrent.futures
import threading
import sys
import os
import logging as logger
import random
import math

from normalizer import normalizer

# add database class path
database_dir_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "database",
)

sys.path.insert(0, database_dir_path)
from create_sqlite_db import DimnaDatabase


def find_books_sitemap(site_map_url):
    r = requests.get(site_map_url)
    if r.status_code != 200:
        raise Exception(f"request error{r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")
    return [url.text for url in soup.find_all("loc") if "books" in url.text]


def find_books_url(books_xml_url):
    books_url = list()
    for url in tqdm(books_xml_url):
        r = requests.get(url, timeout=60)
        if r.status_code != 200:
            raise Exception(f"request error{r.status_code}")
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        books_url += [url.text for url in soup.find_all("loc")]
    return books_url


def find_number_of_comments(comment_url):
    r = requests.get(comment_url)
    if r.status_code == 200:
        json_data = r.json()
        num_comments = json_data["pageProps"]["bookComments"]["total"]
        num_pages = math.ceil(num_comments / 10)
    elif r.status_code == 404:
        num_pages = 0
    else:
        raise Exception(f"request error{r.status_code}")
    return num_pages


def find_all_comments_pages(pages_url):
    comments_url = list()
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        future_to_url = {}
        futures = list()
        for _, book_url, is_visited in pages_url:
            if not is_visited:
                book_id, book_name = book_url.split("/")[-2:]
                first_comment_url = f"{comments_base_url}/{book_id}/{book_name}.json"
                futures_executor = executor.submit(
                    find_number_of_comments, comment_url=first_comment_url
                )
                future_to_url.update({futures_executor: book_url})
                futures.append(futures_executor)
        for future in tqdm(
            concurrent.futures.as_completed(futures),
            initial=len(pages_url) - len(futures),
            total=len(pages_url),
        ):
            book_url = future_to_url[future]
            book_id, book_name = book_url.split("/")[-2:]
            try:
                num_pages = future.result()
            except Exception as exc:
                tqdm.write(f"{book_url} generated an exception: {exc}")
            else:
                if num_pages:
                    for page in range(1, num_pages + 1):
                        comment_url = (
                            f"{comments_base_url}/{book_id}/{book_name}.json?p={page}"
                        )
                        comments_url.append([book_url, comment_url])
    return comments_url


def scrap_comments(comment_url):
    ratings = list()
    r = requests.get(comment_url)
    if r.status_code != 200:
        raise Exception(f"request error{r.status_code}")
    json_data = r.json()
    for comment_json in json_data["pageProps"]["bookComments"]["commentsList"]:
        comment = re.sub(
            r"[،؟\?\.\!]+(?=[،؟\?\.\!])", "", normalizer(comment_json["comment"])
        )
        rate = comment_json["rate"]
        ratings.append([comment, rate])
    return ratings


def scrap_all_comments(comments_url):

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        future_to_url = {}
        futures = []
        for book_url, comment_url in comments_url:
            futures_executor = executor.submit(scrap_comments, comment_url=comment_url)
            future_to_url.update({futures_executor: book_url})
            futures.append(futures_executor)
        for future in tqdm(
            concurrent.futures.as_completed(futures),
            initial=len(comments_url) - len(futures),
            total=len(comments_url),
        ):
            book_url = future_to_url[future]
            try:
                ratings = future.result()
            except Exception as exc:
                tqdm.write(f"{book_url} generated an exception: {exc}")
            else:
                with DimnaDatabase(db_path, logger) as db:
                    db.update_page_visit_status(
                        base_url, book_url, True,
                    )
                    for comment, rate in ratings:
                        db.insert_rating(base_url, comment, rate)


if __name__ == "__main__":

    base_url = "https://taaghche.com"
    site_map_url = "https://taaghche.com/sitemap.xml"
    comments_base_url = (
        "https://taaghche.com/_next/data/bg-Dtu7JQNQAYTekmO2fK/book-review"
    )

    db_path = os.path.join(database_dir_path, "dimna.db",)

    dir_path = os.path.dirname(os.path.realpath(__file__))

    # Config logger
    logfile_path = os.path.join(dir_path, "logs", "taaghche_com.log")
    if not os.path.exists(os.path.dirname(logfile_path)):
        os.mkdir(os.path.dirname(logfile_path))

    logger.basicConfig(
        level=logger.INFO,
        # handlers=[logger.FileHandler(logfile_path), logger.StreamHandler()],
        handlers=[logger.FileHandler(logfile_path)],
        format="%(asctime)s %(levelname)s %(message)s",
    )

    SEARCH_FOR_NEW_URLS = False

    last_week = datetime.now() - timedelta(days=1)

    with DimnaDatabase(db_path, logger) as db:
        last_scrap_time = db.last_scrap_time(base_url)

    if last_scrap_time:
        if last_week >= last_scrap_time:
            SEARCH_FOR_NEW_URLS = True
        else:
            print(f"Loading {base_url} pages from db🦁")
    else:
        SEARCH_FOR_NEW_URLS = True

    if SEARCH_FOR_NEW_URLS:
        print(f"Finding all books on {base_url}🦦...")
        books_xml_url = find_books_sitemap(site_map_url)
        books_url = find_books_url(books_xml_url)

        with DimnaDatabase(db_path, logger) as db:
            for page in tqdm(books_url):
                db.insert_pages_url(base_url, page, False)

        with DimnaDatabase(db_path, logger) as db:
            db.insert_last_scrap_time(base_url, datetime.now())

    with DimnaDatabase(db_path, logger) as db:
        pages_url = db.pages_url(base_url)
    print(f"Total Number of books: {len(pages_url)}")

    print("Finding all comments pages🦥...")
    comments_url = find_all_comments_pages(pages_url[:])

    print("Scraping all comments🦧...")
    scrap_all_comments(comments_url)

