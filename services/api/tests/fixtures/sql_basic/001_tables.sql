CREATE TABLE public.roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE public.users (
    id SERIAL PRIMARY KEY,
    role_id INT NOT NULL REFERENCES public.roles(id),
    email TEXT NOT NULL UNIQUE,
    status TEXT DEFAULT 'active',
    CONSTRAINT users_email_check CHECK (email <> '')
);

CREATE TABLE public.orders (
    id INT,
    user_id INT,
    supplier_id INT REFERENCES inventory.suppliers(id),
    total NUMERIC(10, 2) NOT NULL,
    CONSTRAINT pk_orders PRIMARY KEY (id),
    CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES public.users(id),
    UNIQUE (user_id),
    CHECK (total >= 0)
);
