import sqlite3


def connect_db():
    return sqlite3.connect('whotracksme.db')


def connect_db_top500():
    return sqlite3.connect('top500webpages.db')