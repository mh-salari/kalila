#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Apr 5 2021
@author: MohammadHossein Salari
@email: mohammad.hossein.salari@gmail.com
@sources: - https://alexwlchan.net/2019/10/adventures-with-concurrent-futures/
"""


import re
import os
import sys
import json
import random
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


def find_cities_url(base_url):
    cities_url = list()
    url = f"{base_url}/inc/nselectCity"
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"Request error: {r.status_code}")
    for city in json.loads(r.text):
        cities_url.append(f"{base_url}{city['url']}")
    return cities_url


def find_doctors_url(base_url, city_url):
    doctors_url = []
    for page_num in range(1, 11):
        url = f"{city_url}/page-{page_num}"
        r = requests.get(url)
        if r.status_code != 200:
            raise Exception(f"Request error: {r.status_code}")
        if "موردی یافت نشد" in r.text:
            break
        else:
            soup = BeautifulSoup(r.text, "html.parser")
            doctors_url += [
                f"{base_url}{a['href']}"
                for a in soup.find_all("a", {"class": "drList"})
            ]

    return doctors_url


def find_all_doctors_url(base_url, cities_url, max_workers=128):
    cities_url_iterator = iter(cities_url)
    pbar = tqdm(total=len(cities_url))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:

        futures = {}
        for city_url in itertools.islice(cities_url_iterator, max_workers):
            futures_executor = executor.submit(
                find_doctors_url, base_url=base_url, city_url=city_url
            )
            futures.update({futures_executor: city_url})
        while futures:
            done, _ = concurrent.futures.wait(
                futures, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in done:
                pbar.update(1)
                city_url = futures[future]
                futures.pop(future)
                try:
                    doctors_url = future.result()
                except Exception as exc:
                    tqdm.write(f"{city_url} generated an exception: {exc}")
                else:
                    with DimnaDatabase(db_path, logger) as db:
                        for doctor_url in doctors_url:
                            db.insert_pages_url(
                                base_url, doctor_url, False,
                            )
            for city_url in itertools.islice(cities_url_iterator, len(done)):
                futures_executor = executor.submit(
                    find_doctors_url, base_url=base_url, city_url=city_url
                )
                futures.update({futures_executor: city_url})
    pbar.close()


def scrap_ratings(doctor_url):
    comments = list()
    r = requests.get(doctor_url)
    if r.status_code != 200:
        raise Exception(f"Request error: {r.status_code}")

    soup = BeautifulSoup(r.text, "html.parser")

    try:
        section = soup.find(
            "div", {"class": "col-12 bg-white rounded-15 py-3 class-46"}
        ).find_all("div", {"class": "col-12"})
    except:
        return comments

    for row in section:
        rating = int(re.findall(r'class="red" style="width: (\d+)', str(row))[0]) / 20
        comment = normalizer(
            re.findall(r"<\/div> <\/div> <\/div> <\/div>([\s\S]+)<small", str(row))[
                0
            ].strip()
        )
        comments.append([comment, rating])
    return comments


def scrap_all_comments(base_url, doctors_url, max_workers=128):

    doctors_url_to_do = [
        doctor_url for (_, doctor_url, is_visited) in doctors_url if not is_visited
    ]
    doctors_url_to_do_iterator = iter(doctors_url_to_do)

    pbar = tqdm(
        initial=len(doctors_url) - len(doctors_url_to_do), total=len(doctors_url)
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:

        futures = {}
        for doctor_url in itertools.islice(doctors_url_to_do_iterator, max_workers):
            futures_executor = executor.submit(scrap_ratings, doctor_url=doctor_url)
            futures.update({futures_executor: doctor_url})
        while futures:
            done, _ = concurrent.futures.wait(
                futures, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in done:
                pbar.update(1)
                doctor_url = futures[future]
                futures.pop(future)
                try:
                    comments = future.result()
                except Exception as exc:
                    tqdm.write(f"{doctor_url} generated an exception: {exc}")
                else:
                    with DimnaDatabase(db_path, logger) as db:
                        db.update_page_visit_status(
                            base_url, doctor_url, True,
                        )
                        for comment, rate in comments:
                            db.insert_rating(base_url, comment, rate)
            for doctor_url in itertools.islice(doctors_url_to_do_iterator, len(done)):
                futures_executor = executor.submit(scrap_ratings, doctor_url=doctor_url)
                futures.update({futures_executor: doctor_url})
    pbar.close()


if __name__ == "__main__":

    base_url = "https://nobat.ir"

    db_path = os.path.join(database_dir_path, "dimna.db",)
    dir_path = os.path.dirname(os.path.realpath(__file__))

    # Config logger
    logfile_path = os.path.join(dir_path, "logs", "nobat_ir.log")
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
        print(f"Finding all doctors on {base_url}🦦...")
        cities_url = find_cities_url(base_url)
        find_all_doctors_url(base_url, cities_url)
        with DimnaDatabase(db_path, logger) as db:
            db.insert_last_scrap_time(base_url, datetime.now())

    with DimnaDatabase(db_path, logger) as db:
        doctors_url = db.pages_url(base_url)
    print(f"Total Number of Doctors: {len(doctors_url)}")

    print("Scraping all comments🦧...")
    scrap_all_comments(base_url, doctors_url)

