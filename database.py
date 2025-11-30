import mysql.connector
from mysql.connector import pooling
from config import MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

class Database:
    def __init__(self):
        self.pool = pooling.MySQLConnectionPool(
            pool_name="carbot_pool",
            pool_size=5,
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            autocommit=True
        )

    def get_connection(self):
        return self.pool.get_connection()