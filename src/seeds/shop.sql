DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS order_items;

CREATE TABLE customers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  city TEXT NOT NULL
);

CREATE TABLE products (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  price REAL NOT NULL
);

CREATE TABLE orders (
  id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  ordered_at TEXT NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE order_items (
  order_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  quantity INTEGER NOT NULL,
  PRIMARY KEY (order_id, product_id),
  FOREIGN KEY (order_id) REFERENCES orders(id),
  FOREIGN KEY (product_id) REFERENCES products(id)
);

INSERT INTO customers (id, name, city) VALUES
  (1, 'Eva Sommer', 'Berlin'),
  (2, 'Jonas Berg', 'Hamburg'),
  (3, 'Lea Vogt', 'Muenchen');

INSERT INTO products (id, name, price) VALUES
  (1, 'Notebook', 1199.00),
  (2, 'Maus', 24.90),
  (3, 'Tastatur', 79.00),
  (4, 'Monitor', 249.50);

INSERT INTO orders (id, customer_id, ordered_at) VALUES
  (1, 1, '2026-01-08'),
  (2, 2, '2026-01-12'),
  (3, 1, '2026-01-21');

INSERT INTO order_items (order_id, product_id, quantity) VALUES
  (1, 1, 1),
  (1, 2, 2),
  (2, 4, 1),
  (2, 2, 1),
  (3, 3, 1),
  (3, 2, 1);
