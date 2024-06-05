import sqlite3
import typing


class WorkspaceData:
    def __init__(self):

        self.conn = sqlite3.connect("database.db")
        # Makes the data retrived from the database accessible by their column name
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self.cursor.execute("CREATE TABLE IF NOT EXISTS watchlist (symbol TEXT, exchange TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS strategies (strategy_type TEXT, contract TEXT, timeframe TEXT,"
                            "balance_pct REAL, take_profit REAL, stop_loss REAL, extra_params TEXT)")
        # Saves the changes
        self.conn.commit()

    def save(self, table: str, data: typing.List[typing.Tuple]):

        # Erase the previous table content and record new data to it
        self.cursor.execute(f"DELETE FROM {table}")

        # "INSERT INTO watchlist (symbol, exchange) VALUE (?, ?)"

        table_data = self.cursor.execute(f"SELECT * FROM {table}")

        # Lists the columns of the table
        columns = [description[0] for description in table_data.description]

        # Creates the SQL insert statment dynamically
        sql_statement = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(['?'] * len(columns))})"

        self.cursor.executemany(sql_statement, data)
        self.conn.commit()

    def get(self, table: str) -> typing.List[sqlite3.Row]:

        # Get all the rows recorded for the table
        self.cursor.execute(f"SELECT * FROM {table}")
        data = self.cursor.fetchall()

        return data
