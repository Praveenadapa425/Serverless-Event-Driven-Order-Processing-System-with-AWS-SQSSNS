-- Database initialization script for orders database

-- Create orders table
CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    product_id VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    status VARCHAR(50) DEFAULT 'PENDING' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indices for better query performance
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);

-- Create audit table for tracking order changes
CREATE TABLE IF NOT EXISTS order_audit (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(255) NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    previous_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reason VARCHAR(500)
);

-- Create index for audit
CREATE INDEX IF NOT EXISTS idx_order_audit_order_id ON order_audit(order_id);
CREATE INDEX IF NOT EXISTS idx_order_audit_changed_at ON order_audit(changed_at);

-- Create function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update updated_at
DROP TRIGGER IF EXISTS update_orders_updated_at ON orders;

CREATE TRIGGER update_orders_updated_at
BEFORE UPDATE ON orders
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Insert sample data for testing
INSERT INTO orders (id, user_id, product_id, quantity, status)
VALUES 
    ('ORD-TEST001', 'USER-001', 'PROD-001', 5, 'PENDING'),
    ('ORD-TEST002', 'USER-002', 'PROD-002', 3, 'CONFIRMED'),
    ('ORD-TEST003', 'USER-003', 'PROD-003', 1, 'FAILED')
ON CONFLICT (id) DO NOTHING;

-- Grant permissions (if needed for different users)
GRANT SELECT, INSERT, UPDATE, DELETE ON orders TO postgres;
GRANT SELECT, INSERT, UPDATE, DELETE ON order_audit TO postgres;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO postgres;
