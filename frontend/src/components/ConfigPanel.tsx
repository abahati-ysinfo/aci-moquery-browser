import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Label } from './ui/label'
import { Badge } from './ui/badge'
import { Settings, Save, RotateCcw } from 'lucide-react'
import { apiService } from '../lib/api'
import { toast } from 'sonner'

export default function ConfigPanel() {
  const [localConfig, setLocalConfig] = useState<Record<string, any>>({})
  const queryClient = useQueryClient()

  const { data: config, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: apiService.getConfig,
  })

  useEffect(() => {
    if (config) {
      setLocalConfig(config)
    }
  }, [config])

  const updateConfigMutation = useMutation({
    mutationFn: apiService.updateConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] })
      toast.success('Configuration updated successfully')
    },
    onError: (error) => {
      toast.error(`Failed to update configuration: ${error}`)
    },
  })

  const handleSave = () => {
    updateConfigMutation.mutate(localConfig)
  }

  const handleReset = () => {
    if (config) {
      setLocalConfig(config)
      toast.info('Configuration reset to current values')
    }
  }

  const handleInputChange = (key: string, value: string | number) => {
    setLocalConfig(prev => ({
      ...prev,
      [key]: value,
    }))
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          Loading configuration...
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <div>
              <Label htmlFor="max_concurrent_ingests">Max Concurrent Ingests</Label>
              <Input
                id="max_concurrent_ingests"
                type="number"
                min="1"
                max="10"
                value={localConfig.max_concurrent_ingests || 2}
                onChange={(e) => handleInputChange('max_concurrent_ingests', parseInt(e.target.value))}
                className="mt-1"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Number of files that can be processed simultaneously
              </p>
            </div>

            <div>
              <Label htmlFor="batch_size">Batch Size</Label>
              <Input
                id="batch_size"
                type="number"
                min="100"
                max="10000"
                step="100"
                value={localConfig.batch_size || 2000}
                onChange={(e) => handleInputChange('batch_size', parseInt(e.target.value))}
                className="mt-1"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Number of objects processed per database transaction
              </p>
            </div>
          </div>

          <div className="flex gap-2 pt-4">
            <Button
              onClick={handleSave}
              disabled={updateConfigMutation.isPending}
              className="flex-1"
            >
              <Save className="h-4 w-4 mr-2" />
              {updateConfigMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
            <Button
              variant="outline"
              onClick={handleReset}
              disabled={updateConfigMutation.isPending}
            >
              <RotateCcw className="h-4 w-4 mr-2" />
              Reset
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>System Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span>Data Directory:</span>
              <Badge variant="outline" className="font-mono">
                {config?.data_directory || './data'}
              </Badge>
            </div>
            <div className="flex justify-between">
              <span>Upload Chunk Size:</span>
              <Badge variant="outline">
                {config?.upload_chunk_size || '8MB'}
              </Badge>
            </div>
            <div className="flex justify-between">
              <span>Max File Size:</span>
              <Badge variant="outline">
                {config?.max_file_size || '200MB'}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
