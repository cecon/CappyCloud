import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import { PORTED, screenHref } from 'routes/ported';
import { HIDDEN_SCREENS, REDIRECTS, SCREENS, canAccess } from 'routes/screens';

const user = { role: 'user' as const, is_super_admin: false };
const admin = { role: 'admin' as const, is_super_admin: false };
const superAdmin = { role: 'admin' as const, is_super_admin: true };

describe('nível de acesso (igual ao RequireAdmin/RequireSuperAdmin do web/)', () => {
  it('usuário comum só vê telas de usuário', () => {
    expect(canAccess(user, 'user')).toBe(true);
    expect(canAccess(user, 'admin')).toBe(false);
    expect(canAccess(user, 'super')).toBe(false);
  });

  it('admin não vê telas de super admin', () => {
    expect(canAccess(admin, 'admin')).toBe(true);
    expect(canAccess(admin, 'super')).toBe(false);
  });

  it('super admin vê tudo', () => {
    expect(canAccess(superAdmin, 'admin')).toBe(true);
    expect(canAccess(superAdmin, 'super')).toBe(true);
  });
});

describe('tela pendente abre no frontend atual', () => {
  it('usa o endereço do web/ com a mesma origem', () => {
    const pending = SCREENS.find((s) => !PORTED.has(s.path))!;
    expect(screenHref(pending.path, 'https://cappy.example')).toBe(`https://cappy.example${pending.path}`);
  });
});

describe('cobertura de rotas do web/', () => {
  // Enquanto os dois apps convivem, toda rota do web/ precisa existir no web-c3.
  const appTsx = readFileSync(path.resolve(import.meta.dirname, '../../../web/src/App.tsx'), 'utf8');
  const legacyPaths = [...appTsx.matchAll(/<Route\s+path="([^"]+)"/g)].map((m) => m[1]);
  const covered = new Set([
    '/',
    '*',
    '/login',
    '/change-password',
    ...SCREENS.map((s) => s.path),
    ...HIDDEN_SCREENS.map((s) => s.path),
    ...Object.keys(REDIRECTS)
  ]);

  it('lê as rotas do App.tsx atual', () => {
    expect(legacyPaths.length).toBeGreaterThan(15);
  });

  it.each(legacyPaths)('%s tem equivalente no web-c3', (legacy) => {
    expect(covered.has(legacy)).toBe(true);
  });
});
