import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs'
import { Button } from './ui/button'
import { Moon, Sun } from 'lucide-react'
import { useTheme } from './theme-provider'
import { apiService } from '../lib/api'
import FileUpload from './FileUpload'
import FileBrowser from './FileBrowser'
import DataBrowser from './DataBrowser'
import TenantInformation from './TenantInformation'
import ConfigPanel from './ConfigPanel'

export default function MainLayout() {
  const { theme, setTheme } = useTheme()
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null)
  const [selectedClassName, setSelectedClassName] = useState<string | null>(null)

  const { data: filesData } = useQuery({
    queryKey: ['files'],
    queryFn: apiService.getFiles,
    refetchInterval: 5000,
  })

  const selectedFile = filesData?.files?.find(file => file.file_id === selectedFileId)
  const isSelectedFileTenant = selectedFile?.file_type === 'fvTenant'

  const toggleTheme = () => {
    setTheme(theme === 'light' ? 'dark' : 'light')
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <div className="w-80 border-r bg-card">
        <div className="p-4 border-b">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold">ACI Moquery Browser</h1>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={toggleTheme}>
                {theme === 'light' ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </div>

        <div className="p-4">
          <Tabs defaultValue="files" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="files">Files</TabsTrigger>
              <TabsTrigger value="upload">Upload</TabsTrigger>
              <TabsTrigger value="config">Config</TabsTrigger>
            </TabsList>
            
            <TabsContent value="files" className="mt-4">
              <FileBrowser
                files={filesData?.files || []}
                selectedFileId={selectedFileId}
                onFileSelect={setSelectedFileId}
                onClassSelect={setSelectedClassName}
              />
            </TabsContent>
            
            <TabsContent value="upload" className="mt-4">
              <FileUpload />
            </TabsContent>
            
            <TabsContent value="config" className="mt-4">
              <ConfigPanel />
            </TabsContent>
          </Tabs>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        <div className="border-b p-4">
          <div className="flex items-center justify-between">
            <div>
              {selectedClassName && (
                <h2 className="text-lg font-semibold">Class: {selectedClassName}</h2>
              )}
              {selectedFileId && !selectedClassName && (
                <h2 className="text-lg font-semibold">
                  {isSelectedFileTenant ? 'Tenant Information' : `File ID: ${selectedFileId}`}
                </h2>
              )}
              {!selectedFileId && !selectedClassName && (
                <h2 className="text-lg font-semibold">Select a file or class to browse data</h2>
              )}
            </div>
          </div>
        </div>

        <div className="flex-1 p-4">
          {isSelectedFileTenant ? (
            <TenantInformation fileId={selectedFileId!} />
          ) : (
            <DataBrowser
              fileId={selectedFileId}
              className={selectedClassName}
            />
          )}
        </div>
      </div>
    </div>
  )
}
