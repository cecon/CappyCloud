import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { TooltipProvider } from '@/components/ui/tooltip'
import { applyStoredTheme } from '@/lib/theme'
import './index.css'
import App from './App.tsx'

applyStoredTheme()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TooltipProvider delayDuration={250}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </TooltipProvider>
  </StrictMode>,
)
