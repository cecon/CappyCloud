import type React from 'react'
import { useLocation } from 'react-router-dom'
import { AppOverlay } from '@/components/layout/AppOverlay'
import { routeTitles } from '@/components/layout/navigation'

type AdminOverlayRouterProps = {
  children: React.ReactNode
}

export function AdminOverlayRouter({ children }: AdminOverlayRouterProps) {
  const { pathname } = useLocation()
  const meta = routeTitles[pathname] ?? {
    title: 'Administracao',
    subtitle: 'Console administrativo',
  }

  return (
    <div className="h-full bg-background p-3 lg:p-5">
      <AppOverlay title={meta.title} subtitle={meta.subtitle} closeTo="/chat" className="h-full">
        {children}
      </AppOverlay>
    </div>
  )
}
