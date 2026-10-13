import { useMemo } from 'react';
import { Outlet } from 'react-router';

import { DashboardLayout } from '@c3theme/ui';
import { useAuth } from 'data/auth';
import { menuFor } from 'menu-items';
import HeaderContent from './HeaderContent';
import NavUser from './NavUser';

/** Layout das telas logadas; as guardas de sessão ficam em routes/guards. */
export default function MainLayout() {
  const { state } = useAuth();
  const menu = useMemo(() => (state.status === 'ready' ? menuFor(state.user) : []), [state]);

  // Troca de senha obrigatória: só a tela, sem menu (o usuário ainda não pode navegar).
  if (state.status === 'ready' && state.user.must_change_password) return <Outlet />;

  return <DashboardLayout menu={menu} headerContent={<HeaderContent />} drawerFooter={<NavUser />} footer={null} />;
}
