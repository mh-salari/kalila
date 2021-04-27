#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Apr 19 2021
@author: MohammadHossein Salari
@email: mohammad.hossein.salari@gmail.com
@sources: - https://alexwlchan.net/2019/10/adventures-with-concurrent-futures/
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
import itertools

from normalizer import normalizer

# add database class path
database_dir_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "database",
)

sys.path.insert(0, database_dir_path)
from create_sqlite_db import DimnaDatabase


def find_courses_url(site_map_url):
    r = requests.get(site_map_url)
    if r.status_code != 200:
        raise Exception(f"Request Error: {r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")
    return [course.text for course in soup.find_all("loc")]


def scrap_comments(course_url):
    id = re.findall(r"mk(\d+)", course_url)[0]
    page_number = 1
    comments_url = f"https://maktabkhooneh.org/course/{id}/more_reviews/{page_number}/"

    ratings = list()

    r = requests.get(comments_url)
    if not "تا کنون نظری برای این دوره ثبت نشده است" in r.text:
        soup = BeautifulSoup(r.text, "html.parser")
        try:
            number_of_pages = int(
                max(
                    re.findall(
                        r"\d+", str(soup.find("div", {"class", "filler left-aligned"}))
                    )
                )
            )
        except:
            number_of_pages = 1

        for page_number in range(1, number_of_pages + 1):
            comments_url = (
                f"https://maktabkhooneh.org/course/{id}/more_reviews/{page_number}/"
            )

            r = requests.get(comments_url)
            if r.status_code != 200:
                raise Exception(f"Request Error: {r.status_code}")

            soup = BeautifulSoup(r.text, "html.parser")
            for comment_part in soup.find_all("div", class_="comments__field"):
                comment = comment_part.find(
                    "div", {"class", "comments__desc-user top-margin"}
                ).text.strip()
                comment = re.sub(r"[،؟\?\.\!]+(?=[،؟\?\.\!])", "", normalizer(comment))
                rate = len(
                    comment_part.find_all("i", {"class", "svg-icon--24 svg-icon--gold"})
                )
                ratings += [[comment, rate]]
    return ratings


if __name__ == "__main__":

    base_url = "maktabkhooneh.org"
    site_map_url = "https://maktabkhooneh.org/course.xml"

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
        print(f"Finding all courses on {base_url}🦦...")
        courses_url = find_courses_url(site_map_url)
        print(len(courses_url))
        with DimnaDatabase(db_path, logger) as db:
            db.insert_all_pages_url(base_url, courses_url)

        with DimnaDatabase(db_path, logger) as db:
            db.insert_last_scrap_time(base_url, datetime.now())

    with DimnaDatabase(db_path, logger) as db:
        courses_url = db.pages_url(base_url)
    print(f"Total Number of courses: {len(courses_url)}")

    print("Scraping all comments🦧...")
    for _, course_url, is_visited in tqdm(courses_url[:]):
        if not is_visited:
            with DimnaDatabase(db_path, logger) as db:
                db.update_page_visit_status(
                    base_url, course_url, True,
                )

                comments = scrap_comments(course_url)
                db.insert_all_rating(base_url, comments)
