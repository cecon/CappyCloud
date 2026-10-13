import type { DefaultConfigProps } from '@c3theme/ui';

export const APP_NAME = 'CappyCloud';
export const APP_DEFAULT_PATH = '/chat';
// Chave própria: preferências do tema não colidem com outros apps C3 no navegador.
export const CONFIG_STORAGE_KEY = 'cappycloud-c3-config';

const config: Partial<DefaultConfigProps> = {
  fontFamily: `'Inter', sans-serif`,
  i18n: 'pt'
};

export default config;
