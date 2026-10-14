import { FormattedMessage } from 'react-intl';
import Chip from '@mui/material/Chip';
import Grid from '@mui/material/Grid';
import Link from '@mui/material/Link';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import { MainCard } from '@c3theme/ui';
import { useAuth } from 'data/auth';
import { PORTED, screenHref } from 'routes/ported';
import { SCREENS, canAccess, type Screen } from 'routes/screens';

function ScreenList({ title, screens }: { title: string; screens: Screen[] }) {
  if (!screens.length) return null;
  return (
    <Grid size={{ xs: 12, md: 6 }}>
      <MainCard title={<FormattedMessage id={title} />} content={false}>
        <List disablePadding>
          {screens.map((screen) => {
            const ported = PORTED.has(screen.path);
            return (
              <ListItem key={screen.path} divider>
                <ListItemText
                  primary={
                    <Link href={ported ? `/c3${screen.path}` : screenHref(screen.path)} underline="hover" color="text.primary">
                      <FormattedMessage id={screen.title} />
                    </Link>
                  }
                />
                <Chip
                  size="small"
                  color={ported ? 'success' : 'default'}
                  variant={ported ? 'filled' : 'outlined'}
                  label={<FormattedMessage id={ported ? 'home.ported' : 'home.pending'} />}
                />
              </ListItem>
            );
          })}
        </List>
      </MainCard>
    </Grid>
  );
}

/**
 * Início durante a migração: fica no layout novo e mostra o que já foi portado.
 * Telas pendentes abrem no frontend atual só quando o usuário clica.
 */
export default function HomePage() {
  const { state } = useAuth();
  if (state.status !== 'ready') return null;
  const visible = SCREENS.filter((screen) => canAccess(state.user, screen.access));

  return (
    <Stack sx={{ gap: 3 }}>
      <MainCard>
        <Typography variant="h3">
          <FormattedMessage id="home.title" />
        </Typography>
        <Typography color="text.secondary" sx={{ mt: 1 }}>
          <FormattedMessage id="home.subtitle" />
        </Typography>
      </MainCard>
      <Grid container spacing={3}>
        <ScreenList title="menu.group.main" screens={visible.filter((s) => s.group === 'main')} />
        <ScreenList title="menu.group.admin" screens={visible.filter((s) => s.group === 'admin')} />
      </Grid>
    </Stack>
  );
}
