#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Apr 11 2021
@author: MohammadHossein Salari
@email: mohammad.hossein.salari@gmail.com
@sources: - https://towardsdatascience.com/do-you-know-python-has-a-built-in-database-d553989c87bd
          - https://pynative.com/
          - https://pythonexamples.org/python-sqlite3-check-if-table-exists/
          - https://stackoverflow.com/questions/37408081/write-a-database-class-in-python/37408275
          - https://stackoverflow.com/questions/38076220/python-mysqldb-connection-in-a-class/38078544
"""

import sqlite3
import os
from datetime import datetime
import logging as logger


class DimnaDatabase:
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(DimnaDatabase)
            return cls.instance
        else:
            return cls.instance

    def __init__(self, db_path="you-db-path.db", logger=None):
        self.connection = self.connect(db_path)
        self.cursor = self.connection.cursor()
        self.logger = logger

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cursor.close()
        self.connection.close()

    def log(self, state, text):
        if self.logger:
            if state == "error":
                self.logger.error(text)
            elif state == "info":
                self.logger.info(text)

    def connect(self, db_path):
        db_name = os.path.basename(db_path)
        try:
            connection = sqlite3.connect(db_path)
            # self.log("info", f"Successfully connected to {db_name}")
        except sqlite3.Error as error:
            self.log("error", f"Failed to connect to {db_name}: {error}")
        return connection

    def commit(self):
        self.connection.commit()

    def execute(self, query):
        self.cursor.execute(query)

    def fetchall(self):
        return self.cursor.fetchall()

    def fetchone(self):
        return self.cursor.fetchone()

    def close(self, commit=False):
        if commit:
            self.commit()
        self.cursor.close()
        self.connection.close()

    def check_if_table_exist(self, table_name):
        table_exist = False
        exist_query = f""" SELECT count(name) FROM sqlite_master WHERE type='table' AND name='{table_name}' """

        try:
            self.execute(exist_query)
            if self.fetchone()[0] == 1:
                table_exist = True
        except sqlite3.Error as error:
            self.log("error", f"Failed to check table exist {error}")
        return table_exist

    def create_table(self, table_name, *columns):
        table_exist = self.check_if_table_exist(table_name)
        if table_exist:
            self.log("info", f"Table {{{table_name}}} already exists")
        else:
            columns_text = ", ".join(columns)
            create_table_query = f""" CREATE TABLE {table_name} ({columns_text})"""
            try:
                self.execute(create_table_query)
                self.commit()
                self.log("info", f"Table {{{table_name}}} created successfully")
            except sqlite3.Error as error:
                self.log("error", f"Failed to create {{{table_name}}}: {error}")

    def delete_all_records(self, table_name):
        try:
            sql_create_table_query = f""" DELETE FROM {table_name};"""
            self.execute(sql_create_table_query)
            self.commit()
            self.log("info", f"All records from {{{table_name}}} deleted!")
        except sqlite3.Error as error:
            self.log("error", f"Failed to delete {{{table_name}}}: {error}")

    def insert_rating(self, site: str, comment: str, rating: float):
        try:
            insert_query = f"""INSERT INTO Ratings (site, comment, rating) VALUES ('{site}', '{comment}', {rating})"""
            self.execute(insert_query)
            self.commit()
            self.log(
                "info",
                f"{{comment='{comment}'}} inserted successfully into {{Ratings}}",
            )
        except sqlite3.Error as error:
            self.log(
                "error",
                f"Failed to insert {{comment='{comment}'}} into {{Ratings}}: {error}",
            )

    def ratings(self, site=""):

        if site:
            select_query = f"""SELECT * from Ratings WHERE site='{site}'"""
        else:
            select_query = """SELECT * from Ratings"""
        try:
            self.execute(select_query)
            records = self.fetchall()
            return records
        except sqlite3.Error as error:
            self.log(
                "error", f"Failed to read {{site='{site}'}} from {{Ratings}}: {error}"
            )

    def last_scrap_time(self, site: str):
        select_query = (
            f"""SELECT time [timestamp] FROM LastScrapTime WHERE site='{site}'"""
        )
        last_scrap_time = None
        try:
            self.execute(select_query)
            records = self.fetchall()
            if records:
                last_scrap_time = datetime.strptime(records[0][0], "%Y-%m-%d %H:%M:%S")
        except sqlite3.Error as error:
            self.log(
                "error",
                f"Failed to read {{site='{site}'}} from {{LastScrapTime}}: {error}",
            )
        return last_scrap_time

    def insert_last_scrap_time(self, site: str, time):

        saved_time = self.last_scrap_time(site)
        time = time.strftime("%Y-%m-%d %H:%M:%S")
        if saved_time:
            query = f"""UPDATE LastScrapTime SET site='{site}', time='{time}' WHERE site='{site}'"""
        else:
            query = f"""INSERT INTO LastScrapTime (site, time) VALUES ('{site}', '{time}')"""
        try:
            self.execute(query)
            self.commit()
            self.log(
                "info",
                f"Record {{time='{time}'}} Updated successfully in {{LastScrapTime}}",
            )

        except sqlite3.Error as error:
            self.log(
                "error",
                f"Failed to update {{site='{site}'}} in {{LastScrapTime}}: {error}",
            )

    def pages_url(self, site=""):

        if site:
            select_query = f"""SELECT * from Pages WHERE site='{site}'"""
        else:
            select_query = """SELECT * from Pages"""
        try:
            self.execute(select_query)
            records = self.fetchall()
            return records
        except sqlite3.Error as error:
            self.log(
                "error", f"Failed to read {{site='{site}'}} from {{Pages}}: {error}"
            )

    def insert_pages_url(self, site, page_url, is_visited):

        try:
            insert_query = f"""INSERT INTO Pages (site, page_url, is_visited) VALUES ('{site}', '{page_url}', {is_visited})"""
            self.execute(insert_query)
            self.commit()
            self.log(
                "info",
                f"Record {{page_url='{page_url}'}} inserted successfully into Pages",
            )

        except sqlite3.Error as error:
            self.log(
                "error",
                f"Failed to insert {{page_url='{page_url}'}} into {{Pages}}: {error}",
            )

    def update_page_visit_status(self, site, page_url, is_visited):
        if_exist_query = f"""SELECT page_url from Pages WHERE site='{site}' AND page_url='{page_url}'"""
        try:
            self.execute(if_exist_query)
            self.commit()
            if not self.fetchone():
                raise Exception(f"Record not found! page_url:{page_url}")
        except sqlite3.Error as error:
            self.log(
                "error",
                f"Failed to read {{page_url='{page_url}'}} from {{Pages}}: {error}",
            )

        update_query = f"""UPDATE Pages SET page_url='{page_url}', is_visited={is_visited} WHERE site='{site}' AND page_url='{page_url}'"""
        try:
            self.execute(update_query)
            self.commit()
            self.log(
                "info",
                f"Record {{page_url='{page_url}'}} Updated successfully in {{Pages}}",
            )

        except sqlite3.Error as error:
            self.log(
                "error",
                f"Failed to update {{page_url='{page_url}'}} in {{Pages}}: {error}",
            )


if __name__ == "__main__":
    db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "dimna_test.db")

    # Config logger
    logger.basicConfig(
        level=logger.INFO,
        handlers=[logger.StreamHandler()],
        format="%(asctime)s %(levelname)s %(message)s",
    )

    site = "https://www.digikala.com"

    # create Database tabels
    with DimnaDatabase(db_path, logger) as db:

        db.create_table(
            "Ratings",
            "site TEXT NOT NULL",
            "comment TEXT UNIQUE NOT NULL",
            "rating FLOAT NOT NULL",
        )

        db.create_table(
            "LastScrapTime", "site TEXT UNIQUE NOT NULL", "time TIMESTAMP NOT NULL"
        )

        db.create_table(
            "Pages",
            "site TEXT NOT NULL",
            "page_url TEXT UNIQUE NOT NULL",
            "is_visited BOOLEAN NOT NULL",
        )

    # # Insert demo data to database
    # with DimnaDatabase(db_path, logger) as db:

    #     db.insert_rating(site, "it is a very bad product", "0")
    #     db.insert_rating(site, "it is a very bad product", "2.5")
    #     db.insert_rating(site, "it really enjoyed it!", "5")

    #     records = db.ratings()
    #     print("Total number of ratings are:  ", len(records))
    #     for row in records:
    #         print("site: ", row[0])
    #         print("comment: ", row[1])
    #         print("rating: ", row[2])
    #         print("-" * 25)

    #     db.insert_last_scrap_time(site, datetime.now())
    #     saved_time = db.last_scrap_time(site)
    #     print(f"Last time we visited {site} was: {saved_time}")

    #     db.insert_pages_url(site, f"{site}/p1", False)
    #     db.insert_pages_url(site, f"{site}/p1", True)

    #     records = db.pages_url(site)
    #     print(f"Total number of pages url are:  {len(records)}")
    #     for row in records[:5]:
    #         print("site: ", row[0])
    #         print("page_url: ", row[1])
    #         print("is_visited", bool(row[2]))
    #         print("-" * 25)

    #     db.update_page_visit_status(
    #         site, f"{site}/p1", True,
    #     )
    #     # db.update_page_visit_status(
    #     #     site, f"{site}/p2", True,
    #     # )

    #     records = db.pages_url(site)
    #     print(f"Total number of pages url are:  {len(records)}")
    #     for row in records[:5]:
    #         print("site: ", row[0])
    #         print("page_url: ", row[1])
    #         print("is_visited", bool(row[2]))
    #         print("-" * 25)

    # delete all demo data
    # with DimnaDatabase(db_path, logger) as db:
    #     db.delete_all_records("Ratings")
    #     db.delete_all_records("LastScrapTime")
    #     db.delete_all_records("Pages")
