CREATE VIEW public.active_users AS
SELECT u.id, u.email, r.name AS role_name
FROM public.users u
JOIN public.roles r ON r.id = u.role_id
WHERE u.status = 'active';

CREATE MATERIALIZED VIEW public.order_totals AS
SELECT u.id AS user_id, SUM(o.total) AS total
FROM public.users u
JOIN public.orders o ON o.user_id = u.id
GROUP BY u.id;
