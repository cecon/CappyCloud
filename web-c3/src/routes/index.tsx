import { lazy } from 'react';
import { createBrowserRouter, Navigate, type RouteObject } from 'react-router';

import { Loadable } from '@c3theme/ui';
import MainLayout from 'layout/Dashboard';
import { GuestOnly, LegacyScreen, RequireAccess, RequireAuth } from 'routes/guards';
import { PORTED } from 'routes/ported';
import { HIDDEN_SCREENS, REDIRECTS, SCREENS, type Screen } from 'routes/screens';

const LoginPage = Loadable(lazy(() => import('pages/auth/LoginPage')));
const ChangePasswordPage = Loadable(lazy(() => import('pages/auth/ChangePasswordPage')));

/** Telas portadas: caminho → componente (preenchido no PR de cada tela). */
const PAGES: Record<string, ReturnType<typeof Loadable>> = {};

function screenRoute(screen: Screen): RouteObject {
  const Page = PAGES[screen.path];
  const element = PORTED.has(screen.path) && Page ? <Page /> : <LegacyScreen path={screen.path} />;
  return {
    path: screen.path.slice(1),
    element: <RequireAccess access={screen.access}>{element}</RequireAccess>
  };
}

export const routes: RouteObject[] = [
  {
    path: '/login',
    element: (
      <GuestOnly>
        <LoginPage />
      </GuestOnly>
    )
  },
  {
    path: '/',
    element: (
      <RequireAuth>
        <MainLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/chat" replace /> },
      { path: 'change-password', element: <ChangePasswordPage /> },
      ...[...SCREENS, ...HIDDEN_SCREENS].map(screenRoute),
      ...Object.entries(REDIRECTS).map(([from, to]) => ({ path: from.slice(1), element: <Navigate to={to} replace /> }))
    ]
  },
  { path: '*', element: <Navigate to="/chat" replace /> }
];

export default createBrowserRouter(routes, { basename: '/c3' });
