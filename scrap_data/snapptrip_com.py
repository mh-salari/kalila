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
import requests
import itertools
from tqdm import tqdm
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


def find_all_hotels_url(sitemap_url="https://www.snapptrip.com/hotels.xml"):
    r = requests.get(sitemap_url)
    if r.status_code != 200:
        raise Exception(f"Request Error: {r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")
    return [
        link["href"] + f"?{idx}" for idx, link in enumerate(soup.find_all("xhtml:link"))
    ]


def scrap_comments(url):
    cookies = {
        "route": "1619449476.736.583.641701",
        "unique-cookie": "nwRatz4P21XQoAh",
        "appid": "g*-*direct*-**-*",
        "ptpsession": "g--2212735793014068001",
        "srtest": "1",
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:87.0) Gecko/20100101 Firefox/87.0",
        "Accept": "*/*",
        "Accept-Language": "fa",
        "lang": "fa",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Connection": "keep-alive",
        "Referer": "https://www.snapptrip.com/%D8%B1%D8%B2%D8%B1%D9%88-%D9%87%D8%AA%D9%84/%D8%B4%DB%8C%D8%B1%D8%A7%D8%B2/%D9%87%D8%AA%D9%84-%D8%A8%D8%B2%D8%B1%DA%AF?date_from=2021-04-26&date_to=2021-04-27",
        "Sec-GPC": "1",
        "TE": "Trailers",
    }

    params = (("limit", "500"),)

    comments_url = "https://www.snapptrip.com/rate_review/hotel/" + url.split("?")[-1]
    r = requests.get(comments_url, headers=headers, params=params, cookies=cookies)
    soup = BeautifulSoup(r.text, "html.parser")

    comments = []
    try:
        comments_li = soup.find_all("li", {"class": "comment-item box-frame"})
        for li in comments_li:

            rating = li.find("div", {"class": "rate-badge"}).text.strip()
            comment = li.find("span", {"class": "comment-text-wrapper"})
            if comment:
                comment = comment.text.strip()
            else:
                comment = ""
            pn_comment = li.find_all("p", {"class": "mb-0"})
            if pn_comment:
                if "mt-lg-1" in str(pn_comment[0]):
                    comment += "\n" + " نقاط قوت: " + pn_comment[0].text.strip()

                else:
                    comment += "\n" + " نقاط ضعف:" + pn_comment[0].text.strip()
                try:
                    if "mt-lg-1" in str(pn_comment[1]):
                        comment += "\n" + " نقاط قوت: " + pn_comment[1].text.strip()
                    else:
                        comment += "\n" + " نقاط ضعف: " + pn_comment[1].text.strip()
                except:
                    pass

            comment = re.sub(
                r"[،؟\?\.\!]+(?=[،؟\?\.\!])", "", normalizer(comment).strip(),
            )

            comments.append([comment, rating])
    except:
        pass
    return comments


def scrap_all_comments(base_url, urls, max_workers=256):

    urls_to_do = [url for (_, url, is_visited) in urls if not is_visited]
    urls_to_do_iterator = iter(urls_to_do)

    pbar = tqdm(initial=len(urls) - len(urls_to_do), total=len(urls))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:

        futures = {}
        for url in itertools.islice(urls_to_do_iterator, max_workers):
            futures_executor = executor.submit(scrap_comments, url=url)
            futures.update({futures_executor: url})
        while futures:
            done, _ = concurrent.futures.wait(
                futures, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in done:
                pbar.update(1)
                url = futures[future]
                futures.pop(future)
                try:
                    comments = future.result()
                except Exception as exc:
                    tqdm.write(f"{url} generated an exception: {exc}")
                else:
                    with DimnaDatabase(db_path, logger) as db:
                        db.update_page_visit_status(
                            base_url, url, True,
                        )
                        if comments:
                            db.insert_all_rating(base_url, comments)
            for url in itertools.islice(urls_to_do_iterator, len(done)):
                futures_executor = executor.submit(scrap_comments, url=url)
                futures.update({futures_executor: url})
    pbar.close()


if __name__ == "__main__":

    base_url = "snapptrip.com"

    db_path = os.path.join(database_dir_path, "dimna.db",)
    dir_path = os.path.dirname(os.path.realpath(__file__))

    # Config logger
    logfile_path = os.path.join(dir_path, "logs", f"{base_url}.log")
    if not os.path.exists(os.path.dirname(logfile_path)):
        os.mkdir(os.path.dirname(logfile_path))

    logger.basicConfig(
        level=logger.INFO,
        # handlers=[logger.FileHandler(logfile_path), logger.StreamHandler()],
        handlers=[logger.FileHandler(logfile_path)],
        format="%(asctime)s %(levelname)s %(message)s",
    )

    SEARCH_FOR_NEW_URLS = False

    last_week = datetime.now() - timedelta(days=7)

    with DimnaDatabase(db_path, logger) as db:
        last_scrap_time = db.last_scrap_time(base_url)

    if last_scrap_time:
        if last_week >= last_scrap_time:
            SEARCH_FOR_NEW_URLS = True
        else:
            print(f"Loading {base_url} app url from db🦁")
    else:
        SEARCH_FOR_NEW_URLS = True
    if SEARCH_FOR_NEW_URLS:
        print(f"Finding all places on {base_url}🦦...")
        hotels_url = find_all_hotels_url()
        print(hotels_url[0])
        print(f"Saving urls of {base_url} to the database🦦...")

        with DimnaDatabase(db_path, logger) as db:
            db.insert_all_pages_url(base_url, hotels_url)

        with DimnaDatabase(db_path, logger) as db:
            db.insert_last_scrap_time(base_url, datetime.now())

    with DimnaDatabase(db_path, logger) as db:
        hotels_url = db.pages_url(base_url)
    print(f"Total Number of hotels: {len(hotels_url)}")

    print("Scraping all comments🦧...")
    scrap_all_comments(base_url, hotels_url[:])
