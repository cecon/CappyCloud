import { useEffect, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router';

import { Loader } from '@c3theme/ui';
import { useAuth } from 'data/auth';
import { canAccess, type Access } from 'routes/screens';

/** Exige sessão; manda trocar a senha antes de qualquer tela quando obrigatório. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { state } = useAuth();
  const location = useLocation();

  if (state.status === 'loading') return <Loader />;
  if (state.status === 'anonymous') return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (state.user.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />;
  }
  return <>{children}</>;
}

/** Mesmo nível de acesso do frontend atual; sem permissão volta para o chat. */
export function RequireAccess({ access, children }: { access: Access; children: ReactNode }) {
  const { state } = useAuth();
  if (state.status !== 'ready') return <Loader />;
  if (!canAccess(state.user, access)) return <Navigate to="/chat" replace />;
  return <>{children}</>;
}

/** Só para quem não está logado (tela de login). */
export function GuestOnly({ children }: { children: ReactNode }) {
  const { state } = useAuth();
  if (state.status === 'loading') return <Loader />;
  if (state.status === 'ready') return <Navigate to="/chat" replace />;
  return <>{children}</>;
}

/** Tela ainda não portada: abre a mesma rota no frontend atual, com a mesma sessão. */
export function LegacyScreen({ path }: { path: string }) {
  const { search, hash } = useLocation();
  useEffect(() => {
    window.location.replace(`${path}${search}${hash}`);
  }, [path, search, hash]);
  return <Loader />;
}
