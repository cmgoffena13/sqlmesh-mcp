MODEL (
  name sushi.customers,
  kind FULL,
  description 'customer dimension'
);

WITH orders AS (
  SELECT customer_id FROM sushi.raw_orders
)
SELECT
  orders.customer_id AS customer_id
FROM orders
LEFT JOIN sushi.raw_customers AS raw_customers
  ON orders.customer_id = raw_customers.customer_id
