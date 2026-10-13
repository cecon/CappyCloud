import { useState, type MouseEvent } from 'react';
import { useNavigate } from 'react-router';
import { FormattedMessage } from 'react-intl';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { ArrowRight2, KeySquare, Logout } from 'iconsax-reactjs';

import { Avatar, useGetMenuMaster } from '@c3theme/ui';
import { useAuth } from 'data/auth';

function roleLabel(role: string, superAdmin: boolean): string {
  if (superAdmin) return 'role.super';
  return role === 'admin' ? 'role.admin' : 'role.user';
}

/** Rodapé do menu: usuário logado, troca de senha e sair. */
export default function NavUser() {
  const navigate = useNavigate();
  const { state, logout } = useAuth();
  const { menuMaster } = useGetMenuMaster();
  const drawerOpen = menuMaster.isDashboardDrawerOpened;
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  if (state.status !== 'ready') return null;
  const { user } = state;

  const close = () => setAnchorEl(null);
  const handleLogout = () => {
    close();
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <Box sx={{ p: 1.25, px: drawerOpen ? 2.5 : 1.25, borderTop: '1px solid', borderTopColor: 'divider' }}>
      <Stack direction="row" sx={{ alignItems: 'center', gap: 1.25 }}>
        <Avatar alt={user.email} sx={{ width: 38, height: 38 }}>
          {user.email.slice(0, 1).toUpperCase()}
        </Avatar>
        {drawerOpen && (
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography variant="subtitle2" noWrap title={user.email}>
              {user.email}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              <FormattedMessage id={roleLabel(user.role, user.is_super_admin)} />
            </Typography>
          </Box>
        )}
        <IconButton size="small" aria-label="Opções da conta" onClick={(e: MouseEvent<HTMLElement>) => setAnchorEl(e.currentTarget)}>
          <ArrowRight2 size={16} />
        </IconButton>
      </Stack>
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={close}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
        transformOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <MenuItem
          onClick={() => {
            close();
            navigate('/change-password');
          }}
        >
          <ListItemIcon>
            <KeySquare size={18} />
          </ListItemIcon>
          <FormattedMessage id="account.changePassword" />
        </MenuItem>
        <MenuItem onClick={handleLogout}>
          <ListItemIcon>
            <Logout size={18} />
          </ListItemIcon>
          <FormattedMessage id="account.logout" />
        </MenuItem>
      </Menu>
    </Box>
  );
}
