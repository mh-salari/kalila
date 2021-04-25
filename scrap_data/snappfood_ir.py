#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Apr 25 2021
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
from normalizer import normalizer
from datetime import datetime, timedelta

# add database class path
database_dir_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "database",
)

sys.path.insert(0, database_dir_path)
from create_sqlite_db import DimnaDatabase


def get_restaurants(url):

    restaurants = []

    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"Request Error: {r.status_code}")

    soup = BeautifulSoup(r.text, "html.parser")
    restaurants = [
        base_url + a["href"]
        for a in soup.find_all("a", {"class": "idn-restaurant-title"})
    ]

    return restaurants


def get_all_restaurants_url(urls_to_get):
    restaurants_url = []
    pbar = tqdm(total=len(urls_to_get))
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as executor:

        future_to_url = {
            executor.submit(get_restaurants, url): url for url in urls_to_get
        }
        for future in concurrent.futures.as_completed(future_to_url):
            pbar.update(1)
            url = future_to_url[future]
            try:
                data = future.result()
            except Exception as exc:
                tqdm.write(f"{url} generated an exception: {exc}")
            else:
                restaurants_url += data
    pbar.close()
    return restaurants_url


def get_page_comments(url, page_number):

    restaurant_id = url.replace("https://snappfood.ir/restaurant/menu/", "").split("/")[
        0
    ]

    comments_url = (
        f"https://snappfood.ir/restaurant/comment/vendor/{restaurant_id}/{page_number}"
    )

    r = requests.get(comments_url)
    if r.status_code != 200:
        raise Exception(f"Request Error: {r.status_code}")

    comments_json = json.loads(r.text)["data"]
    count = comments_json["count"]
    comments = []

    for comment_dict in comments_json["comments"]:
        comments.append(
            [normalizer(comment_dict["commentText"].strip()), comment_dict["rate"]]
        )

    page_comments = {"url": url, "count": count, "comments": comments}
    return page_comments


def get_all_comments(restaurants_url, pages_tracker={}, max_workers=64):

    restaurants_url_to_do_iterator = iter(restaurants_url)
    pages_comments = []
    pbar = tqdm(total=len(restaurants_url))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:

        futures = {}
        for restaurant_url, page_number in itertools.islice(
            restaurants_url_to_do_iterator, max_workers
        ):

            futures_executor = executor.submit(
                get_page_comments, restaurant_url, page_number
            )
            futures.update({futures_executor: restaurant_url})
        while futures:
            done, _ = concurrent.futures.wait(
                futures, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in done:
                pbar.update(1)
                restaurant_url = futures[future]
                futures.pop(future)

                if pages_tracker:

                    pages_tracker[restaurant_url][1] += 1
                    if (
                        pages_tracker[restaurant_url][1]
                        >= pages_tracker[restaurant_url][0]
                    ):
                        print(
                            restaurant_url,
                            pages_tracker[restaurant_url][1],
                            pages_tracker[restaurant_url][0],
                        )
                        with DimnaDatabase(db_path, logger) as db:
                            db.update_page_visit_status(
                                base_url, restaurant_url, True,
                            )
                try:
                    comments = future.result()
                except Exception as exc:
                    tqdm.write(f"{restaurant_url} generated an exception: {exc}")
                else:
                    pages_comments.append(comments)

                    with DimnaDatabase(db_path, logger) as db:
                        for comment, rating in comments["comments"]:
                            db.insert_rating(base_url, comment, rating)

            for restaurant_url, page_number in itertools.islice(
                restaurants_url_to_do_iterator, len(done)
            ):
                futures_executor = executor.submit(
                    get_page_comments, restaurant_url, page_number
                )
                futures.update({futures_executor: restaurant_url})

    pbar.close()
    return pages_comments


if __name__ == "__main__":

    base_url = "https://snappfood.ir"

    db_path = os.path.join(database_dir_path, "dimna.db",)
    dir_path = os.path.dirname(os.path.realpath(__file__))

    # Config logger
    logfile_path = os.path.join(dir_path, "logs", "snappfood_ir.log")
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

        urls_to_get = []
        for page_num in range(0, 850):
            urls_to_get.append(
                f"https://snappfood.ir/restaurant/city/'+item.link+'?page={page_num}"
            )

        print("Getting all restaurants urls from https://snappfood.ir🐮...")
        restaurants_url = get_all_restaurants_url(urls_to_get[:])

        with DimnaDatabase(db_path, logger) as db:
            for restaurant_url in tqdm(restaurants_url):
                db.insert_pages_url(base_url, restaurant_url, False)

        print(f"Total number of restaurants: {len(restaurants_url)}")

        with DimnaDatabase(db_path, logger) as db:
            db.insert_last_scrap_time(base_url, datetime.now())

    with DimnaDatabase(db_path, logger) as db:
        restaurants_url = db.pages_url(base_url)
    print(f"Total number of restaurants {len(restaurants_url)}")
    restaurants_url = list(
        [url, 0] for _, url, visited in restaurants_url if not visited
    )
    print(f"Total number of new restaurants to {len(restaurants_url)}")

    print("Getting first round of comments🐅...")
    comments = get_all_comments(restaurants_url[:2])

    next_comments_urls = []
    pages_tracker = {}
    for page in comments:
        count = page["count"]
        url = page["url"]
        number_of_pages = count // 10
        if number_of_pages:
            pages_tracker.update({url: [number_of_pages, 0]})
            for page_number in range(number_of_pages):
                next_comments_urls.append([url, page_number])
    print("Getting rest of comments🐆...")
    comments += get_all_comments(next_comments_urls[:], pages_tracker)

    counter = 0
    for comment in comments:
        for c in comment:
            counter += 1
    print(f"Done! {counter} comments saved 🔥")
