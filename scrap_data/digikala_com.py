#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Apr 19 2021
@author: MohammadHossein Salari
@email: mohammad.hossein.salari@gmail.com
"""
import os
import re
import sys
import json
import gzip
import requests
import itertools
from tqdm import tqdm
from io import BytesIO
import logging as logger
import concurrent.futures
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

from normalizer import normalizer

# add database class path
database_dir_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "database",
)

sys.path.insert(0, database_dir_path)
from create_sqlite_db import DimnaDatabase


def get_products_url(sitemap_gzip_url):
    # source: https://stackoverflow.com/questions/26564348/how-to-parse-compressed-sitemap-using-python-without-downloading-it-to-disk
    r = requests.get(sitemap_gzip_url)
    if r.status_code != 200:
        raise Exception(f"Request Error: {r.status_code}")

    sitemap = gzip.GzipFile(fileobj=BytesIO(r.content)).read()
    return [
        loc.text
        for loc in BeautifulSoup(sitemap, "html.parser").find_all("loc")
        if "https://www.digikala.com/product/" in loc.text
    ]


def get_all_products_url(base_sitemap_url):
    products_url = []
    r = requests.get(base_sitemap_url)
    if r.status_code != 200:
        raise Exception(f"Request Error: {r.status_code}")
    sitemaps_url = [
        loc.text for loc in BeautifulSoup(r.text, "html.parser").find_all("loc")
    ]

    pbar = tqdm(total=len(sitemaps_url))

    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
        future_to_url = {
            executor.submit(get_products_url, sitemap_gzip_url): sitemap_gzip_url
            for sitemap_gzip_url in sitemaps_url[:]
        }
        for future in concurrent.futures.as_completed(future_to_url):
            pbar.update(1)
            sitemap_gzip_url = future_to_url[future]
            try:
                data = future.result()
            except Exception as e:
                print(f"{sitemap_gzip_url} generated an exception: {e}")
            else:
                products_url += data
    pbar.close()
    return products_url


def scrap_comments(url):
    comments = []
    product_id = re.findall(r"product/\w*\-(\d+)", url)[0]

    for page_number in range(1, 101):
        page_comments = []

        url = f"https://www.digikala.com/ajax/product/comments/list/{product_id}/?page={page_number}"
        r = requests.get(url)
        if r.status_code != 200:
            raise Exception(f"Request Error: {r.status_code}")

        soup = BeautifulSoup(r.text, "html.parser")

        for item in soup.find_all(
            "div", {"class": "c-comments__item c-comments__item--pdp"}
        ):
            comments_status = item.find("div", {"class": "c-comments__status"})
            if not comments_status:
                continue
            if comments_status.text == "خرید این محصول را توصیه نمی‌کنم":
                rating = 0
            elif comments_status.text == "در مورد خرید این محصول مطمئن نیستم":
                rating = 2.5
            else:
                rating = 5

            comment_content = item.find(
                "div", {"class": "c-comments__content"}
            ).text.strip()

            comment_positive = [
                c.text.strip()
                for c in item.find_all(
                    "div", {"class": "c-comments__modal-evaluation-item--positive"}
                )
            ]
            if len(comment_positive) == 1:
                comment_positive = comment_positive[0]
            elif len(comment_positive) > 1:
                comment_positive = "، ".join(comment_positive)

            comment_negative = [
                c.text.strip()
                for c in item.find_all(
                    "div", {"class": "c-comments__modal-evaluation-item--negative"}
                )
            ]
            if len(comment_negative) == 1:
                comment_negative = comment_negative[0]
            elif len(comment_negative) > 1:
                comment_negative = "، ".join(comment_negative)

            if comment_positive:
                comment_content += "\nنقاط قوت: " + comment_positive
            if comment_negative:
                comment_content += "\nنقاط ضعف: " + comment_negative
            comment_content = re.sub(
                r"[،؟\?\.\!]+(?=[،؟\?\.\!])", "", normalizer(comment_content).strip()
            )
            page_comments.append([comment_content, rating])
        if page_comments:
            comments += page_comments
        else:
            break

    return comments


def scrap_all_comments(base_url, all_products_url, max_workers=64):
    products_url_to_do = [
        product_url
        for (_, product_url, is_visited) in all_products_url
        if not is_visited
    ]
    products_url_to_do_iterator = iter(products_url_to_do)

    pbar = tqdm(
        initial=len(all_products_url) - len(products_url_to_do),
        total=len(all_products_url),
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:

        futures = {}
        for product_url in itertools.islice(products_url_to_do_iterator, max_workers):
            futures_executor = executor.submit(scrap_comments, url=product_url)
            futures.update({futures_executor: product_url})
        while futures:
            done, _ = concurrent.futures.wait(
                futures, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in done:
                pbar.update(1)
                product_url = futures[future]
                futures.pop(future)
                try:
                    comments = future.result()
                except Exception as exc:
                    tqdm.write(f"{product_url} generated an exception: {exc}")
                else:
                    with DimnaDatabase(db_path, logger) as db:
                        db.update_page_visit_status(
                            base_url, product_url, True,
                        )
                        if comments:
                            db.insert_all_rating(base_url, comments)
            for product_url in itertools.islice(products_url_to_do_iterator, len(done)):
                futures_executor = executor.submit(
                    scrap_comments, product_url=product_url
                )
                futures.update({futures_executor: product_url})
    pbar.close()


if __name__ == "__main__":

    base_url = "https://www.digikala.com"
    base_sitemap_url = "https://www.digikala.com/sitemap.xml"

    db_path = os.path.join(database_dir_path, "dimna.db",)
    dir_path = os.path.dirname(os.path.realpath(__file__))

    # Config logger
    logfile_path = os.path.join(dir_path, "logs", "digikala_com.log")
    if not os.path.exists(os.path.dirname(logfile_path)):
        os.mkdir(os.path.dirname(logfile_path))

    logger.basicConfig(
        level=logger.INFO,
        # handlers=[logger.FileHandler(logfile_path), logger.StreamHandler()],
        handlers=[logger.FileHandler(logfile_path)],
        format="%(asctime)s %(levelname)s %(message)s",
    )

    SEARCH_FOR_NEW_URLS = False

    last_month = datetime.now() - timedelta(days=30)

    with DimnaDatabase(db_path, logger) as db:
        last_scrap_time = db.last_scrap_time(base_url)

    if last_scrap_time:
        if last_month >= last_scrap_time:
            SEARCH_FOR_NEW_URLS = True
        else:
            print(f"Loading {base_url} app url from db🦁")
    else:
        SEARCH_FOR_NEW_URLS = True
    if SEARCH_FOR_NEW_URLS:
        print(f"Finding all products on {base_url}🦦...")
        all_products_url = get_all_products_url(base_sitemap_url)

        print(f"Saving urls of {base_url} products to the database🦦...")
        with DimnaDatabase(db_path, logger) as db:
            db.insert_all_pages_url(base_url, all_products_url)

        # update last scrap time
        with DimnaDatabase(db_path, logger) as db:
            db.insert_last_scrap_time(base_url, datetime.now())

    with DimnaDatabase(db_path, logger) as db:
        all_products_url = db.pages_url(base_url)
    print(f"Total Number of product: {len(all_products_url)}")

    print("Scraping all comments🦧...")
    scrap_all_comments(base_url, all_products_url[:])
