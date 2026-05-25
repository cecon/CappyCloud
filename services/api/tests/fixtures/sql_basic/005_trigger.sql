CREATE TRIGGER trg_orders_audit
AFTER INSERT ON public.orders
EXECUTE FUNCTION public.audit_order();
