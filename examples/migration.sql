ALTER TABLE orders
    ADD COLUMN settled_at TIMESTAMP NULL;

UPDATE orders
   SET settled_at = paid_at
 WHERE status = 'SETTLED'
   AND settled_at IS NULL;

CREATE INDEX orders_settled_at_idx ON orders (settled_at DESC NULLS LAST);
