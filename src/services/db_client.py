"""Database Client - All SQLite operations."""
import sqlite3
import pandas as pd
from typing import Optional, List, Tuple

from src.config import DB_PATH, TABLE_NAME, CSV_PATH


class DatabaseClient:
    """Unified client for all database operations."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.table_name = TABLE_NAME

    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        return sqlite3.connect(self.db_path)

    def query(self, sql: str, params: Optional[list] = None) -> pd.DataFrame:
        """Execute SQL query and return DataFrame."""
        conn = self._connect()
        try:
            return pd.read_sql_query(sql, conn, params=params or [])
        finally:
            conn.close()

    def execute(self, sql: str, params: Optional[list] = None) -> None:
        """Execute SQL statement without return."""
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(sql, params or [])
            conn.commit()
        finally:
            conn.close()


    def get_all_phones(self) -> List[str]:
        """Get all phones as 'Company - Model' strings."""
        sql = f'''
            SELECT DISTINCT "Company Name", "Model Name" 
            FROM "{self.table_name}" 
            ORDER BY "Company Name", "Model Name"
        '''
        df = self.query(sql)
        return [f'{row["Company Name"]} - {row["Model Name"]}' for _, row in df.iterrows()]

    def get_phone_data(self, phone_selections: List[str]) -> pd.DataFrame:
        """Fetch data for selected phones (format: 'Company - Model')."""
        if not phone_selections:
            return pd.DataFrame()

        placeholders = []
        params = []

        for phone in phone_selections:
            if phone and " - " in phone:
                company, model = phone.split(" - ", 1)
                placeholders.append(
                    '(LOWER("Company Name") = LOWER(?) AND LOWER("Model Name") = LOWER(?))'
                )
                params.extend([company, model])

        if not placeholders:
            return pd.DataFrame()

        where_clause = " OR ".join(placeholders)
        sql = f'SELECT * FROM "{self.table_name}" WHERE {where_clause}'
        return self.query(sql, params)

    def get_filtered_phones(
        self,
        company: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        camera_min: Optional[int] = None,
        camera_max: Optional[int] = None,
        battery_min: Optional[int] = None,
        battery_max: Optional[int] = None,
    ) -> List[str]:
        """Get phones filtered by criteria."""
        conditions = []
        params = []

        if company:
            conditions.append('LOWER("Company Name") = LOWER(?)')
            params.append(company)

        if price_min is not None:
            conditions.append('"Launched Price (INR)" >= ?')
            params.append(price_min)

        if price_max is not None:
            conditions.append('"Launched Price (INR)" <= ?')
            params.append(price_max)

        if camera_min is not None:
            conditions.append('"Back Camera (MP)" >= ?')
            params.append(camera_min)

        if camera_max is not None:
            conditions.append('"Back Camera (MP)" <= ?')
            params.append(camera_max)

        if battery_min is not None:
            conditions.append('"Battery Capacity (mAh)" >= ?')
            params.append(battery_min)

        if battery_max is not None:
            conditions.append('"Battery Capacity (mAh)" <= ?')
            params.append(battery_max)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f'''
            SELECT DISTINCT "Company Name", "Model Name" 
            FROM "{self.table_name}" 
            WHERE {where_clause} 
            ORDER BY "Company Name", "Model Name"
        '''

        df = self.query(sql, params)
        return [f'{row["Company Name"]} - {row["Model Name"]}' for _, row in df.iterrows()]

    # -------------------------------------------------------------------------
    # Metadata Methods
    # -------------------------------------------------------------------------

    def get_companies(self) -> List[str]:
        """Get all unique company names."""
        sql = f'SELECT DISTINCT "Company Name" FROM "{self.table_name}" ORDER BY "Company Name"'
        df = self.query(sql)
        return df["Company Name"].tolist()

    def get_price_range(self) -> Tuple[int, int]:
        """Get min and max price."""
        sql = f'''
            SELECT MIN("Launched Price (INR)") as min_val, MAX("Launched Price (INR)") as max_val 
            FROM "{self.table_name}" 
            WHERE "Launched Price (INR)" IS NOT NULL
        '''
        df = self.query(sql)
        if not df.empty and pd.notna(df.iloc[0]["min_val"]):
            return int(df.iloc[0]["min_val"]), int(df.iloc[0]["max_val"])
        return 0, 100000

    def get_camera_range(self) -> Tuple[int, int]:
        """Get min and max camera MP."""
        sql = f'''
            SELECT MIN("Back Camera (MP)") as min_val, MAX("Back Camera (MP)") as max_val 
            FROM "{self.table_name}" 
            WHERE "Back Camera (MP)" IS NOT NULL
        '''
        df = self.query(sql)
        if not df.empty and pd.notna(df.iloc[0]["min_val"]):
            return int(df.iloc[0]["min_val"]), int(df.iloc[0]["max_val"])
        return 0, 200

    def get_battery_range(self) -> Tuple[int, int]:
        """Get min and max battery capacity."""
        sql = f'''
            SELECT MIN("Battery Capacity (mAh)") as min_val, MAX("Battery Capacity (mAh)") as max_val 
            FROM "{self.table_name}" 
            WHERE "Battery Capacity (mAh)" IS NOT NULL
        '''
        df = self.query(sql)
        if not df.empty and pd.notna(df.iloc[0]["min_val"]):
            return int(df.iloc[0]["min_val"]), int(df.iloc[0]["max_val"])
        return 0, 10000

    def create_from_csv(self, csv_path: str = CSV_PATH) -> None:
        """Create database from CSV file."""
        df = pd.read_csv(csv_path)
        conn = self._connect()
        try:
            df.to_sql(self.table_name, conn, if_exists="replace", index=False)
        finally:
            conn.close()
