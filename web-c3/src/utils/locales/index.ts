import type { LocaleMessages } from '@c3theme/ui';

// Cada *.json desta pasta vira um idioma; o app usa pt (config.ts).
const locales = import.meta.glob<{ default: LocaleMessages }>('./*.json');

export function loadMessages(locale: string): Promise<LocaleMessages> {
  const loader = locales[`./${locale}.json`] ?? locales['./pt.json'];
  return loader().then((m) => m.default);
}
