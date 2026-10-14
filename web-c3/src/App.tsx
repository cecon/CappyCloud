import { RouterProvider } from 'react-router/dom';
import Box from '@mui/material/Box';
import { ptBR } from '@mui/material/locale';

import { C3ThemeProvider, Locales, ScrollTop, Snackbar } from '@c3theme/ui';
import mark from 'assets/cappycloud-mark.png';
import config, { APP_DEFAULT_PATH, APP_NAME, CONFIG_STORAGE_KEY } from 'config';
import { AuthProvider } from 'data/auth';
import router from 'routes';
import { loadMessages } from 'utils/locales';

const logo = (
  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, fontWeight: 700, fontSize: '1.15rem', color: 'text.primary' }}>
    <Box component="img" src={mark} alt="" sx={{ width: 32, height: 32 }} />
    {APP_NAME}
  </Box>
);
const logoIcon = <Box component="img" src={mark} alt={APP_NAME} sx={{ width: 32, height: 32 }} />;

export default function App() {
  return (
    <C3ThemeProvider
      defaultConfig={config}
      storageKey={CONFIG_STORAGE_KEY}
      branding={{ name: APP_NAME, homePath: APP_DEFAULT_PATH, logo, logoIcon }}
      themeOverrides={ptBR}
    >
      <Locales loadMessages={loadMessages}>
        <ScrollTop>
          <AuthProvider>
            <RouterProvider router={router} />
            <Snackbar />
          </AuthProvider>
        </ScrollTop>
      </Locales>
    </C3ThemeProvider>
  );
}
