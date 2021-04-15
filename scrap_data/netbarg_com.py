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
import sys
import os
import logging as logger

from normalizer import normalizer

# add database class path
database_dir_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "database",
)

sys.path.insert(0, database_dir_path)
from create_sqlite_db import DimnaDatabase


def find_offers(url):
    r = requests.get(url, timeout=30)

    if r.status_code != 200:
        raise Exception(f"request error{r.status_code}")

    soup = BeautifulSoup(r.content, "html.parser")

    offers = [
        base_url + offer.a["href"]
        for offer in soup.find_all("div", {"class": "cat-deal-box-main clearfix"})
    ]
    return offers


def find_all_offers():

    with DimnaDatabase(db_path, logger) as db:
        old_offers = [row[1] for row in db.pages_url(base_url)]

    urls = list()
    for city in cities:
        for category in categories:
            urls.append(f"{base_url}/{city}/{category}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        future_to_url = {}
        futures = []
        for url in urls:
            futures_executor = executor.submit(find_offers, url=url)
            future_to_url.update({futures_executor: url})
            futures.append(futures_executor)
        for future in tqdm(
            concurrent.futures.as_completed(futures), total=len(futures)
        ):
            url = future_to_url[future]
            try:
                offers = future.result()
            except Exception as exc:
                tqdm.write(f"{url} generated an exception: {exc}")
            else:
                with DimnaDatabase(db_path, logger) as db:
                    for page in offers:
                        if page not in old_offers:
                            db.insert_pages_url(base_url, page, False)

    with DimnaDatabase(db_path, logger) as db:
        db.insert_last_scrap_time(base_url, datetime.now())


def pars_ratings(soup):
    ratings = list()
    for rating_class in soup.find_all("div", {"class": "acbr-cell pro-box"}):
        comment = rating_class.find("div", {"class": "cb-bottom"}).text.strip()
        rating_face = rating_class.find("i")["class"]
        if "icon-sad-face" in rating_face:
            rating = 0
        elif "icon-normal-face" in rating_face:
            rating = 2.5
        elif "icon-happy-face" in rating_face:
            rating = 5
        ratings.append([comment, rating])
    return ratings


def scrap_rattings(url):
    r = requests.get(url, timeout=30)

    if r.status_code != 200:
        raise Exception(f"request error{r.status_code}")

    ratings = list()
    if "acbr-cell pro-box" in r.text:
        ratings += pars_ratings(BeautifulSoup(r.text, "html.parser"))
    if "getMoreRatings" in r.text:
        _url = re.findall(r'mj-target="/rating/ratings/getMoreRatings/(.*)"', r.text)[0]
        ratings_url = base_url + "/rating/ratings/getMoreRatings/" + _url[:-1]
        page_num = 0
        while True:
            page_num += 1
            url = ratings_url + str(page_num)
            r = requests.get(url)
            if r.status_code == 404:
                break
            elif r.status_code == 200:
                ratings += pars_ratings(BeautifulSoup(r.text, "html.parser"))

    return ratings


def scrap_all_rattings(pages_url):

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        future_to_url = {}
        futures = []
        for _, url, is_visited in pages_url:
            if not is_visited:
                futures_executor = executor.submit(scrap_rattings, url=url)
                future_to_url.update({futures_executor: url})
                futures.append(futures_executor)
        for future in tqdm(
            concurrent.futures.as_completed(futures),
            initial=len(pages_url) - len(futures),
            total=len(pages_url),
        ):
            url = future_to_url[future]
            try:
                ratings = future.result()
            except Exception as exc:
                tqdm.write(f"{url} generated an exception: {exc}")
            else:
                with DimnaDatabase(db_path, logger) as db:
                    db.update_page_visit_status(
                        base_url, url, True,
                    )

                    for comment, rate in ratings:
                        # Regex replace multiple punctuations and normalize
                        comment = re.sub(
                            r"[،؟\?\.\!]+(?=[،؟\?\.\!])", "", normalizer(comment)
                        )
                        db.insert_rating(
                            base_url, comment, rate,
                        )


if __name__ == "__main__":

    base_url = "https://netbarg.com"
    db_path = os.path.join(database_dir_path, "dimna.db",)

    dir_path = os.path.dirname(os.path.realpath(__file__))

    # Config logger
    logfile_path = os.path.join(dir_path, "log.log")
    logger.basicConfig(
        level=logger.INFO,
        # handlers=[logger.FileHandler(logfile_path), logger.StreamHandler()],
        handlers=[logger.FileHandler(logfile_path)],
        format="%(asctime)s %(levelname)s %(message)s",
    )

    cities = [
        "tehran",
        "isfahan",
        "karaj",
        "mashhad",
        "ghazvin",
        "arak",
        "ardebil",
        "oroomieh",
        "ahwaz",
        "ilam",
        "bojnoord",
        "booshehr",
        "bandarabbas",
        "birjand",
        "tabriz",
        "khoramabad",
        "rasht",
        "zahedan",
        "zanjan",
        "semnan",
        "sanandaj",
        "shahrekord",
        "shiraz",
        "qom",
        "kerman",
        "kermanshah",
        "kish",
        "gorgan",
        "mazandaran",
        "hamedan",
        "yasooj",
        "yazd",
    ]

    categories = [
        "c:restaurant",
        "c:entertainment",
        "c:health",
        "c:art",
        "c:education",
        "c:beauty",
        "c:product",
        "c:traveltours",
        "c:services",
    ]

    SEARCH_FOR_NEW_URLS = False

    yesterday = datetime.now() - timedelta(days=1)

    with DimnaDatabase(db_path, logger) as db:
        last_scrap_time = db.last_scrap_time(base_url)

    if last_scrap_time:
        if yesterday >= last_scrap_time:
            SEARCH_FOR_NEW_URLS = True
        else:
            print(f"Loading {base_url} pages from db🦁")
            with DimnaDatabase(db_path, logger) as db:
                pages_url = db.pages_url(base_url)
    else:
        SEARCH_FOR_NEW_URLS = True

    if SEARCH_FOR_NEW_URLS:
        print(f"Finding all offers on {base_url}🦦...")
        find_all_offers()
        with DimnaDatabase(db_path, logger) as db:
            pages_url = db.pages_url(base_url)
    print(f"Number of offers {len(pages_url)}")

    print("Scaping ratings🦥...")
    scrap_all_rattings(pages_url)
