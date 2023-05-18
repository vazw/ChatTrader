# The BEERWARE License (BEERWARE)
#
# Copyright (c) 2022 Author. All rights reserved.
#
# Licensed under the "THE BEER-WARE LICENSE" (Revision 42):
# vazw wrote this file. As long as you retain this notice you
# can do whatever you want with this stuff. If we meet some day, and you think
# this stuff is worth it, you can buy me a beer or coffee in return
import sqlite3

import bcrypt
import pandas as pd

barsC = 1502
pwd = "vxmaBot"
id = "vxma"


def cooking(id, pwd):
    pepper = f"{id}{pwd}!{barsC}vz{id}"
    bytePwd = pepper.encode("utf-8")
    Salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(bytePwd, Salt)


dropuser = "DROP TABLE user"
dropkey = "DROP TABLE key"
# dropbot = "DROP TABLE Bot"

# 2
sql_create_users = """CREATE TABLE IF NOT EXISTS user (
                                    id text PRIMARY KEY,
                                    pass text NOT NULL
                                )"""
# 5
sql_create_key = """CREATE TABLE IF NOT EXISTS key (
                                    freeB TEXT NOT NULL,
                                    minB REAL NOT NULL,
                                    apikey TEXT PRIMARY KEY,
                                    apisec TEXT NOT NULL,
                                    notify TEXT NOT NULL
                                )"""
# 22
sql_create_tasks_table = """CREATE TABLE IF NOT EXISTS Bot (
                                    id TEXT NOT NULL PRIMARY KEY,
                                    symbol TEXT NOT NULL,
                                    timeframe TEXT NOT NULL,
                                    ATR  NOT NULL,
                                    ATR_m REAL NOT NULL,
                                    EMA INTEGER NOT NULL,
                                    subhag INTEGER NOT NULL,
                                    smooth INTEGER NOT NULL,
                                    RSI INTEGER NOT NULL,
                                    Andean INTEGER NOT NULL,
                                    Uselong TEXT NOT NULL,
                                    Useshort TEXT NOT NULL,
                                    UseTP TEXT NOT NULL,
                                    UseSL TEXT NOT NULL,
                                    Tail_SL TEXT NOT NULL,
                                    leverage INTEGER NOT NULL,
                                    Pivot INTEGER NOT NULL,
                                    RR1 REAL NOT NULL,
                                    RR2 REAL NOT NULL,
                                    TP1 INTEGER NOT NULL,
                                    TP2 INTEGER NOT NULL,
                                    Risk TEXT NOT NULL,
                                    maxMargin TEXT NOT NULL
                                )"""


def cUser():
    try:
        with sqlite3.connect("vxma.db", check_same_thread=False) as con:
            cur = con.cursor()
            cur.execute(sql_create_users)
            con.commit()
        print("success : user")
    except sqlite3.Error as e:
        print(e)
        print("Fail to create table : user")


def cKey():
    try:
        with sqlite3.connect("vxma.db", check_same_thread=False) as con:
            cur = con.cursor()
            cur.execute(sql_create_key)
            con.commit()
        print("success : key")
    except sqlite3.Error as e:
        print(e)
        print("Fail to create table : key")


def cBot():
    try:
        with sqlite3.connect("vxma.db", check_same_thread=False) as con:
            cur = con.cursor()
            cur.execute(sql_create_tasks_table)
            con.commit()
            print("success : Bot")
    except sqlite3.Error as e:
        print(e)
        print("Fail to create table : Bot")


def newUser():
    try:
        with sqlite3.connect("vxma.db", check_same_thread=False) as con:
            data = pd.DataFrame(columns=["id", "pass"])
            cook = cooking(id, pwd)
            compo = [id, cook]
            data.loc[1] = compo
            data = data.set_index("id")
            data.to_sql(
                "user",
                con=con,
                if_exists="replace",
                index=True,
                index_label="id",
            )
            print("success : RESET")
    except sqlite3.Error as e:
        print(e)
        print("fail")


def dropT():
    try:
        with sqlite3.connect("vxma.db", check_same_thread=False) as con:
            cur = con.cursor()
            cur.execute(dropuser)
            cur.execute(dropkey)
            # cur.execute(dropbot)
            con.commit()
            print("success : Drop")
    except sqlite3.Error as e:
        print(e)
        print("Fail to drop table!")


def resetdata():
    dropT()
    cUser()
    cKey()
    newUser()
    # cBot()
