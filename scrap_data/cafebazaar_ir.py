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


def find_all_apps_url():

    apps_url = []

    # Find apps sitemaps
    print(f"Finding url of all apps in {base_url}")
    app_sitemaps_url = "https://cafebazaar.ir/app-sitemap.xml"
    r = requests.get(app_sitemaps_url)
    if r.status_code != 200:
        raise Exception(f"Request Error: {r.status_code}")
    all_apps_sitemaps_url = [
        loc.text for loc in BeautifulSoup(r.text, "html.parser").find_all("loc")
    ]

    # Scrap url of all apps
    for app_sitemap_url in tqdm(all_apps_sitemaps_url[:]):
        r = requests.get(app_sitemap_url)
        if r.status_code != 200:
            raise Exception(f"Request Error: {r.status_code}")

        apps_url += [
            loc.text for loc in BeautifulSoup(r.text, "html.parser").find_all("loc")
        ]

    return apps_url


def scrap_comments(url):

    comments = []

    package_name = url.split("/")[-1]

    cafebazaar_api_url = "https://api.cafebazaar.ir/rest-v1/process/ReviewRequest"

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:87.0) Gecko/20100101 Firefox/87.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/json;charset=utf-8",
        "Origin": "https://cafebazaar.ir",
        "Connection": "keep-alive",
        "Referer": "https://cafebazaar.ir/",
        "Sec-GPC": "1",
        "TE": "Trailers",
    }

    for start in range(0, 2_500, 100):
        page_comments = []
        data = f'{{"properties":{{"language":2,"clientID":"m7dywtvvb5z3kph88shahoou39y8w5jw","deviceID":"m7dywtvvb5z3kph88shahoou39y8w5jw","clientVersion":"web"}},"singleRequest":{{"reviewRequest":{{"packageName":"{package_name}","start":{start},"end":{start+100}}}}}}}'
        for retry in range(10):
            r = requests.post(cafebazaar_api_url, headers=headers, data=data)
            if r.status_code == 200:

                commnets_json = json.loads(r.text)

                for review in commnets_json["singleReply"]["reviewReply"]["reviews"]:
                    comment = re.sub(
                        r"[،؟\?\.\!]+(?=[،؟\?\.\!])",
                        "",
                        normalizer(review["comment"]).strip(),
                    )

                    page_comments.append([comment, review["rate"]])
                break
            elif r.status_code == 504:
                pass
            else:
                raise Exception(f"Request Error: {r.status_code}")
        if page_comments:
            comments += page_comments
        else:
            break
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

    base_url = "cafebazaar.ir"

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
        print(f"Finding all apps on {base_url}🦦...")
        apps_url = find_all_apps_url()

        print(f"Saving urls of {base_url} to the database🦦...")

        with DimnaDatabase(db_path, logger) as db:
            db.insert_all_pages_url(base_url, apps_url)

        with DimnaDatabase(db_path, logger) as db:
            db.insert_last_scrap_time(base_url, datetime.now())

    with DimnaDatabase(db_path, logger) as db:
        apps_url = db.pages_url(base_url)
    print(f"Total Number of apps: {len(apps_url)}")

    print("Scraping all comments🦧...")
    scrap_all_comments(base_url, apps_url[:])
