CREATE INDEX idx_users_email ON public.users(email);

CREATE UNIQUE INDEX idx_orders_user_total ON public.orders(user_id, total);
