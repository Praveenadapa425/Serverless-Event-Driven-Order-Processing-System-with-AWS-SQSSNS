"""Database connection and utilities for order management."""
import psycopg2
from psycopg2 import sql, extras
import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages database connections and operations."""
    
    def __init__(self):
        self.host = os.environ.get('DB_HOST', 'localhost')
        self.port = int(os.environ.get('DB_PORT', '5432'))
        self.database = os.environ.get('DB_NAME', 'orders_db')
        self.user = os.environ.get('DB_USER', 'postgres')
        self.password = os.environ.get('DB_PASSWORD', 'postgres')
        self.conn = None
    
    def connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                connect_timeout=5
            )
            logger.info("Database connection established")
            return self.conn
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            raise
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def get_connection(self):
        """Get active connection or create new one."""
        if self.conn is None:
            self.connect()
        return self.conn
    
    def create_orders_table(self):
        """Create orders table if it doesn't exist."""
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            create_table_query = """
            CREATE TABLE IF NOT EXISTS orders (
                id VARCHAR(255) PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                product_id VARCHAR(255) NOT NULL,
                quantity INTEGER NOT NULL,
                status VARCHAR(50) DEFAULT 'PENDING' NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
            
            cur.execute(create_table_query)
            conn.commit()
            logger.info("Orders table created or already exists")
            cur.close()
        except Exception as e:
            logger.error(f"Failed to create orders table: {str(e)}")
            raise
    
    def insert_order(self, order_id: str, user_id: str, product_id: str, quantity: int) -> bool:
        """Insert a new order into the database."""
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            insert_query = """
            INSERT INTO orders (id, user_id, product_id, quantity, status)
            VALUES (%s, %s, %s, %s, 'PENDING')
            """
            
            cur.execute(insert_query, (order_id, user_id, product_id, quantity))
            conn.commit()
            logger.info(f"Order {order_id} inserted successfully")
            cur.close()
            return True
        except psycopg2.IntegrityError as e:
            logger.warning(f"Order {order_id} already exists: {str(e)}")
            conn.rollback()
            cur.close()
            return False
        except Exception as e:
            logger.error(f"Failed to insert order: {str(e)}")
            if conn:
                conn.rollback()
            raise
    
    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an order by ID."""
        try:
            conn = self.get_connection()
            cur = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            query = "SELECT * FROM orders WHERE id = %s"
            cur.execute(query, (order_id,))
            result = cur.fetchone()
            cur.close()
            
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to retrieve order {order_id}: {str(e)}")
            raise
    
    def update_order_status(self, order_id: str, new_status: str) -> bool:
        """Update order status."""
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            update_query = """
            UPDATE orders 
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """
            
            cur.execute(update_query, (new_status, order_id))
            conn.commit()
            
            if cur.rowcount > 0:
                logger.info(f"Order {order_id} status updated to {new_status}")
                cur.close()
                return True
            else:
                logger.warning(f"Order {order_id} not found for status update")
                cur.close()
                return False
        except Exception as e:
            logger.error(f"Failed to update order status: {str(e)}")
            if conn:
                conn.rollback()
            raise


def get_db_connection() -> DatabaseConnection:
    """Factory function to get database connection."""
    db = DatabaseConnection()
    db.connect()
    return db
