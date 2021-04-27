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


def find_all_pages_id():
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:87.0) Gecko/20100101 Firefox/87.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/json;charset=utf-8",
        "ab-channel": "GuestDesktop,1.42.2,Ubuntu,null,undefined,5b3fb4cf-5383-4da8-9052-ae3c4fa66cf4",
        "Origin": "https://www.jabama.com",
        "Connection": "keep-alive",
        "Referer": "https://www.jabama.com/",
        "Sec-GPC": "1",
        "TE": "Trailers",
    }
    pbar = tqdm(total=75)
    pages_id = []
    for page_number in range(1, 50):
        data = '{"kind":"accommodation","page-number":%d,"page-size":100}' % (
            page_number
        )
        r = requests.post(
            "https://taraazws.jabama.com/api/v1/all-results", headers=headers, data=data
        )
        if r.status_code != 200:
            raise Exception(f"request error{r.status_code}")
        ids = re.findall(r'"room_id":"([a-zA-Z0-9_\-\_]*)_', r.text)
        pages_id += ids
        pbar.update(1)
        if len(ids) < 100:
            break

    for page_number in range(1, 25):
        data = '{"kind":"hotel","page-number":%d,"page-size":100}' % (page_number)
        r = requests.post(
            "https://taraazws.jabama.com/api/v1/all-results", headers=headers, data=data
        )
        if r.status_code != 200:
            raise Exception(f"request error{r.status_code}")
        ids = re.findall(r'place_id":"([a-zA-Z0-9_\-\_]*)"', r.text)
        pages_id += ids
        pbar.update(1)
        if len(ids) < 100:
            break
    pbar.close()
    return [page_id for page_id in pages_id if page_id]


def scrap_comments(page_id):
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:87.0) Gecko/20100101 Firefox/87.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-GPC": "1",
        "Cache-Control": "max-age=0",
        "TE": "Trailers",
    }

    comments = []
    for page_number in range(1, 25):
        url = f"https://taraazws.jabama.com/api/v1/reviews/place/{page_id}/reviews?page={page_number}"
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            raise Exception(f"request error{r.status_code}")

        page_comments = []
        for row in json.loads(r.text)["result"]:
            comment = re.sub(
                r"[،؟\?\.\!]+(?=[،؟\?\.\!])", "", normalizer(row["comment"]).strip(),
            )

            page_comments.append([comment, row["rating"]])
        if page_comments:
            comments += page_comments
        else:
            break

    return comments


def scrap_all_comments(base_url, pages_id, max_workers=5):
    pages_id_to_do = [
        page_id for (_, page_id, is_visited) in pages_id if not is_visited
    ]
    pages_id_to_do_iterator = iter(pages_id_to_do)

    pbar = tqdm(initial=len(pages_id) - len(pages_id_to_do), total=len(pages_id))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:

        futures = {}
        for page_id in itertools.islice(pages_id_to_do_iterator, max_workers):
            futures_executor = executor.submit(scrap_comments, page_id=page_id)
            futures.update({futures_executor: page_id})
        while futures:
            done, _ = concurrent.futures.wait(
                futures, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in done:
                pbar.update(1)
                page_id = futures[future]
                futures.pop(future)
                try:
                    comments = future.result()
                except Exception as exc:
                    tqdm.write(f"{page_id} generated an exception: {exc}")
                else:
                    with DimnaDatabase(db_path, logger) as db:
                        db.update_page_visit_status(
                            base_url, page_id, True,
                        )
                        if comments:
                            db.insert_all_rating(base_url, comments)
            for page_id in itertools.islice(pages_id_to_do_iterator, len(done)):
                futures_executor = executor.submit(scrap_comments, page_id=page_id)
                futures.update({futures_executor: page_id})
    pbar.close()


if __name__ == "__main__":

    base_url = "https://www.jabama.com/"

    db_path = os.path.join(database_dir_path, "dimna.db",)
    dir_path = os.path.dirname(os.path.realpath(__file__))

    # Config logger
    logfile_path = os.path.join(dir_path, "logs", "jabama_com.log")
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
        pages_id = find_all_pages_id()

        print(f"Saving urls of {base_url} to the database🦦...")

        with DimnaDatabase(db_path, logger) as db:
            db.insert_all_pages_url(base_url, pages_id)

        with DimnaDatabase(db_path, logger) as db:
            db.insert_last_scrap_time(base_url, datetime.now())

    with DimnaDatabase(db_path, logger) as db:
        pages_id = db.pages_url(base_url)
    print(f"Total Number of apps: {len(pages_id)}")

    print("Scraping all comments🦧...")
    scrap_all_comments(base_url, pages_id[:])
