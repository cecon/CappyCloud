CREATE FUNCTION public.get_user_orders(p_user_id INT)
RETURNS TABLE(order_id INT, total NUMERIC)
AS $$
    SELECT id, total FROM public.orders WHERE user_id = p_user_id;
$$ LANGUAGE sql;

CREATE PROCEDURE public.archive_user(p_user_id INT)
AS $$
BEGIN
    INSERT INTO public.orders(id, user_id, total)
    SELECT id, p_user_id, 0 FROM public.users WHERE id = p_user_id;
END;
$$ LANGUAGE plpgsql;
