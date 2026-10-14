import type { DefaultConfigProps } from '@c3theme/ui';

export const APP_NAME = 'CappyCloud';
// Início no layout novo enquanto as telas são portadas; na virada volta a ser /chat.
export const APP_DEFAULT_PATH = '/';
// Chave própria: preferências do tema não colidem com outros apps C3 no navegador.
export const CONFIG_STORAGE_KEY = 'cappycloud-c3-config';

const config: Partial<DefaultConfigProps> = {
  fontFamily: `'Inter', sans-serif`,
  i18n: 'pt'
};

export default config;
