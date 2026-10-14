import type { ReactNode } from 'react';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import { MainCard } from '@c3theme/ui';
import mark from 'assets/cappycloud-mark.png';
import { APP_NAME } from 'config';

/** Moldura das telas sem menu (login e troca de senha). */
export default function AuthLayout({ title, subtitle, children }: { title: ReactNode; subtitle?: ReactNode; children: ReactNode }) {
  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center', p: 2, bgcolor: 'background.default' }}>
      <MainCard sx={{ width: '100%', maxWidth: 420 }} content={false}>
        <Stack sx={{ p: { xs: 3, sm: 4 }, gap: 3 }}>
          <Stack direction="row" sx={{ alignItems: 'center', gap: 1.5 }}>
            <Box component="img" src={mark} alt="" sx={{ width: 40, height: 40 }} />
            <Typography variant="h4">{APP_NAME}</Typography>
          </Stack>
          <Box>
            <Typography variant="h3">{title}</Typography>
            {subtitle && (
              <Typography color="text.secondary" sx={{ mt: 0.5 }}>
                {subtitle}
              </Typography>
            )}
          </Box>
          {children}
        </Stack>
      </MainCard>
    </Box>
  );
}
