"""Database Client - All SQLite operations."""
import sqlite3
import pandas as pd
from typing import Optional, List, Tuple

from src.config import DB_PATH, TABLE_NAME, CSV_PATH
from src.utils.logger import log_function_call, log_timing, get_logger

logger = get_logger(__name__)


class DatabaseClient:
    """Unified client for all database operations."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.table_name = TABLE_NAME
        logger.info(f"DatabaseClient initialized with db_path: {db_path}")

    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        return sqlite3.connect(self.db_path)

    @log_function_call
    def query(self, sql: str, params: Optional[list] = None) -> pd.DataFrame:
        """Execute SQL query and return DataFrame."""
        logger.debug(f"Executing SQL query: {sql[:200]}...")
        
        with log_timing("Database query"):
            conn = self._connect()
            try:
                df = pd.read_sql_query(sql, conn, params=params or [])
                logger.info(f"Query executed successfully. Rows returned: {len(df)}")
                return df
            finally:
                conn.close()

    @log_function_call
    def execute(self, sql: str, params: Optional[list] = None) -> None:
        """Execute SQL statement without return."""
        logger.debug(f"Executing SQL statement: {sql[:200]}...")
        
        with log_timing("Database execute"):
            conn = self._connect()
            try:
                cur = conn.cursor()
                cur.execute(sql, params or [])
                conn.commit()
                logger.info("SQL statement executed successfully")
            finally:
                conn.close()


    @log_function_call
    def get_all_phones(self) -> List[str]:
        """Get all phones as 'Company - Model' strings."""
        logger.debug("Fetching all phones")
        
        with log_timing("Get all phones"):
            sql = f'''
                SELECT DISTINCT "Company Name", "Model Name" 
                FROM "{self.table_name}" 
                ORDER BY "Company Name", "Model Name"
            '''
            df = self.query(sql)
            phones = [f'{row["Company Name"]} - {row["Model Name"]}' for _, row in df.iterrows()]
            logger.info(f"Retrieved {len(phones)} phones")
            return phones

    @log_function_call
    def get_phone_data(self, phone_selections: List[str]) -> pd.DataFrame:
        """Fetch data for selected phones (format: 'Company - Model')."""
        logger.info(f"Fetching data for {len(phone_selections)} phone(s)")
        
        with log_timing("Get phone data"):
            if not phone_selections:
                logger.warning("No phone selections provided")
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
                logger.warning("No valid phone selections found")
                return pd.DataFrame()

            where_clause = " OR ".join(placeholders)
            sql = f'SELECT * FROM "{self.table_name}" WHERE {where_clause}'
            df = self.query(sql, params)
            logger.info(f"Retrieved data for {len(df)} phone record(s)")
            return df

    @log_function_call
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
        logger.debug(f"Getting filtered phones with filters: company={company}, "
                    f"price={price_min}-{price_max}, camera={camera_min}-{camera_max}, "
                    f"battery={battery_min}-{battery_max}")
        
        with log_timing("Get filtered phones"):
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
            phones = [f'{row["Company Name"]} - {row["Model Name"]}' for _, row in df.iterrows()]
            logger.info(f"Retrieved {len(phones)} filtered phones")
            return phones

    # -------------------------------------------------------------------------
    # Metadata Methods
    # -------------------------------------------------------------------------

    @log_function_call
    def get_companies(self) -> List[str]:
        """Get all unique company names."""
        logger.debug("Fetching all companies")
        
        with log_timing("Get companies"):
            sql = f'SELECT DISTINCT "Company Name" FROM "{self.table_name}" ORDER BY "Company Name"'
            df = self.query(sql)
            companies = df["Company Name"].tolist()
            logger.info(f"Retrieved {len(companies)} companies")
            return companies

    @log_function_call
    def get_price_range(self) -> Tuple[int, int]:
        """Get min and max price."""
        logger.debug("Fetching price range")
        
        with log_timing("Get price range"):
            sql = f'''
                SELECT MIN("Launched Price (INR)") as min_val, MAX("Launched Price (INR)") as max_val 
                FROM "{self.table_name}" 
                WHERE "Launched Price (INR)" IS NOT NULL
            '''
            df = self.query(sql)
            if not df.empty and pd.notna(df.iloc[0]["min_val"]):
                price_range = (int(df.iloc[0]["min_val"]), int(df.iloc[0]["max_val"]))
                logger.info(f"Price range: {price_range}")
                return price_range
            logger.warning("No price data found, returning default range")
            return 0, 100000

    @log_function_call
    def get_camera_range(self) -> Tuple[int, int]:
        """Get min and max camera MP."""
        logger.debug("Fetching camera range")
        
        with log_timing("Get camera range"):
            sql = f'''
                SELECT MIN("Back Camera (MP)") as min_val, MAX("Back Camera (MP)") as max_val 
                FROM "{self.table_name}" 
                WHERE "Back Camera (MP)" IS NOT NULL
            '''
            df = self.query(sql)
            if not df.empty and pd.notna(df.iloc[0]["min_val"]):
                camera_range = (int(df.iloc[0]["min_val"]), int(df.iloc[0]["max_val"]))
                logger.info(f"Camera range: {camera_range}")
                return camera_range
            logger.warning("No camera data found, returning default range")
            return 0, 200

    @log_function_call
    def get_battery_range(self) -> Tuple[int, int]:
        """Get min and max battery capacity."""
        logger.debug("Fetching battery range")
        
        with log_timing("Get battery range"):
            sql = f'''
                SELECT MIN("Battery Capacity (mAh)") as min_val, MAX("Battery Capacity (mAh)") as max_val 
                FROM "{self.table_name}" 
                WHERE "Battery Capacity (mAh)" IS NOT NULL
            '''
            df = self.query(sql)
            if not df.empty and pd.notna(df.iloc[0]["min_val"]):
                battery_range = (int(df.iloc[0]["min_val"]), int(df.iloc[0]["max_val"]))
                logger.info(f"Battery range: {battery_range}")
                return battery_range
            logger.warning("No battery data found, returning default range")
            return 0, 10000

    @log_function_call
    def create_from_csv(self, csv_path: str = CSV_PATH) -> None:
        """Create database from CSV file."""
        logger.info(f"Creating database from CSV: {csv_path}")
        
        with log_timing("Create database from CSV"):
            df = pd.read_csv(csv_path)
            logger.info(f"Loaded CSV with {len(df)} rows, {len(df.columns)} columns")
            
            conn = self._connect()
            try:
                df.to_sql(self.table_name, conn, if_exists="replace", index=False)
                logger.info(f"Database created successfully with table: {self.table_name}")
            finally:
                conn.close()
