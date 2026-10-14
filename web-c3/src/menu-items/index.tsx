/* eslint-disable react-refresh/only-export-components -- monta o menu; não é módulo de componente */
import { FormattedMessage } from 'react-intl';
import {
  Book1,
  Box1,
  Category2,
  Cloud,
  Cpu,
  DocumentText1,
  Folder2,
  Link21,
  MessageText1,
  People,
  Setting2,
  Stickynote,
  Messages2,
  Code1,
  Home2
} from 'iconsax-reactjs';

import type { NavItemType } from '@c3theme/ui';
import type { CurrentUser } from 'data';
import { screenHref } from 'routes/ported';
import { SCREENS, canAccess, type Screen } from 'routes/screens';

const ICONS: Record<string, NavItemType['icon']> = {
  '/chat': MessageText1,
  '/skills': Book1,
  '/mcp': Link21,
  '/settings': Setting2,
  '/admin': Category2,
  '/admin/conversations': Messages2,
  '/admin/reports': DocumentText1,
  '/admin/users': People,
  '/admin/sandboxes': Box1,
  '/admin/models': Cpu,
  '/admin/providers': Cloud,
  '/admin/workspaces': Folder2,
  '/admin/repositories': Code1,
  '/admin/skills-global': Stickynote
};

function toItem(screen: Screen): NavItemType {
  return {
    id: screen.path,
    title: <FormattedMessage id={screen.title} />,
    type: 'item',
    url: screenHref(screen.path),
    icon: ICONS[screen.path]
  };
}

/** Menu por nível de acesso; telas pendentes abrem no frontend atual. */
export function menuFor(user: CurrentUser): NavItemType[] {
  const visible = SCREENS.filter((screen) => canAccess(user, screen.access));
  const groups: NavItemType[] = [
    {
      id: 'main',
      title: <FormattedMessage id="menu.group.main" />,
      type: 'group',
      children: [
        { id: 'home', title: <FormattedMessage id="menu.home" />, type: 'item', url: '/', icon: Home2, breadcrumbs: false },
        ...visible.filter((s) => s.group === 'main').map(toItem)
      ]
    }
  ];
  const admin = visible.filter((s) => s.group === 'admin');
  if (admin.length) {
    groups.push({ id: 'admin', title: <FormattedMessage id="menu.group.admin" />, type: 'group', children: admin.map(toItem) });
  }
  return groups;
}
