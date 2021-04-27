#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Apr 19 2021
@author: MohammadHossein Salari
@email: mohammad.hossein.salari@gmail.com
@sources: - https://alexwlchan.net/2019/10/adventures-with-concurrent-futures/
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


def find_otaghaks_url(site_map):
    r = requests.get(site_map)
    if r.status_code != 200:
        raise Exception(f"Request Error: {r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")
    return [loc.text for loc in soup.find_all("loc")]


def scrap_comments(otaghak_url):
    comments = list()
    url = f"https://www.otaghak.com/odata/Otaghak/Comments/GetAllByRoomId(roomId={otaghak_url.split('/')[-1]})?$top=1000&$skip=0"
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"Request Error: {r.status_code}")
    context = json.loads(r.text)
    for value in context["value"]:
        if value["body"] and value["point"]:
            comment = value["body"].strip()
            comment = re.sub(r"[،؟\?\.\!]+(?=[،؟\?\.\!])", "", normalizer(comment))
            rating = value["point"]
            comments.append([comment, rating])
    return comments


def scrap_all_comments(base_url, otaghaks_url, max_workers=128):

    otaghaks_url_to_do = [
        otaghak_url for (_, otaghak_url, is_visited) in otaghaks_url if not is_visited
    ]
    otaghaks_url_to_do_iterator = iter(otaghaks_url_to_do)

    pbar = tqdm(
        initial=len(otaghaks_url) - len(otaghaks_url_to_do), total=len(otaghaks_url)
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:

        futures = {}
        for otaghak_url in itertools.islice(otaghaks_url_to_do_iterator, max_workers):
            futures_executor = executor.submit(scrap_comments, otaghak_url=otaghak_url)
            futures.update({futures_executor: otaghak_url})
        while futures:
            done, _ = concurrent.futures.wait(
                futures, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in done:
                pbar.update(1)
                otaghak_url = futures[future]
                futures.pop(future)
                try:
                    comments = future.result()
                except Exception as exc:
                    tqdm.write(f"{otaghak_url} generated an exception: {exc}")
                else:
                    with DimnaDatabase(db_path, logger) as db:
                        db.update_page_visit_status(
                            base_url, otaghak_url, True,
                        )
                        for comment, rate in comments:
                            db.insert_rating(base_url, comment, rate)
            for otaghak_url in itertools.islice(otaghaks_url_to_do_iterator, len(done)):
                futures_executor = executor.submit(
                    scrap_comments, otaghak_url=otaghak_url
                )
                futures.update({futures_executor: otaghak_url})
    pbar.close()


if __name__ == "__main__":

    base_url = "www.otaghak.com"
    site_map_urls = [
        "https://www.otaghak.com/sitemaps/room.xml",
        "https://www.otaghak.com/sitemaps/inactiveroom.xml",
    ]
    db_path = os.path.join(database_dir_path, "dimna.db",)
    dir_path = os.path.dirname(os.path.realpath(__file__))

    # Config logger
    logfile_path = os.path.join(dir_path, "logs", "otaghak_com.log")
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
        print(f"Finding all places on {base_url}🦦...")
        otaghaks_url = []
        for url in tqdm(site_map_urls):
            otaghaks_url += find_otaghaks_url(url)

        with DimnaDatabase(db_path, logger) as db:
            db.insert_all_pages_url(base_url, otaghaks_url)

        with DimnaDatabase(db_path, logger) as db:
            db.insert_last_scrap_time(base_url, datetime.now())

    with DimnaDatabase(db_path, logger) as db:
        otaghaks_url = db.pages_url(base_url)
    print(f"Total Number of places: {len(otaghaks_url)}")

    print("Scraping all comments🦧...")
    scrap_all_comments(base_url, otaghaks_url)
