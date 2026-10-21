import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import { useIntl } from 'react-intl';
import { Moon, Sun1 } from 'iconsax-reactjs';

import { HeaderFullScreen, ThemeMode, useConfig } from '@c3theme/ui';

/** Cabeçalho: espaço livre, tela cheia e tema claro/escuro. */
export default function HeaderContent() {
  const intl = useIntl();
  const { mode, onChangeMode } = useConfig();
  const dark = mode === ThemeMode.DARK;
  const label = intl.formatMessage({ id: dark ? 'header.lightMode' : 'header.darkMode' });

  return (
    <>
      <Box sx={{ flex: 1 }} />
      <HeaderFullScreen />
      <Tooltip title={label}>
        <IconButton aria-label={label} onClick={() => onChangeMode(dark ? ThemeMode.LIGHT : ThemeMode.DARK)} sx={{ ml: 0.75 }}>
          {dark ? <Sun1 size={20} /> : <Moon size={20} />}
        </IconButton>
      </Tooltip>
    </>
  );
}
