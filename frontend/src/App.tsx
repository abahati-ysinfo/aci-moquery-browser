import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from './components/theme-provider'
import { Toaster } from './components/ui/sonner'
import MainLayout from './components/MainLayout'
import './App.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="light" storageKey="aci-moquery-theme">
        <div className="min-h-screen bg-background">
          <MainLayout />
          <Toaster />
        </div>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

export default App
