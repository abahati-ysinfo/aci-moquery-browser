import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Progress } from './ui/progress'
import { ScrollArea } from './ui/scroll-area'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from './ui/collapsible'
import { 
  File, 
  ChevronDown, 
  ChevronRight, 
  Database, 
  Clock, 
  AlertCircle,
  CheckCircle,
  Loader2
} from 'lucide-react'
import { FileInfo } from '../lib/api'
import { apiService } from '../lib/api'
import { formatBytes, formatDate } from '../lib/utils'

interface FileBrowserProps {
  files: FileInfo[]
  selectedFileId: number | null
  onFileSelect: (fileId: number | null) => void
  onClassSelect: (className: string | null) => void
}

export default function FileBrowser({ 
  files, 
  selectedFileId, 
  onFileSelect, 
  onClassSelect 
}: FileBrowserProps) {
  const [expandedFiles, setExpandedFiles] = useState<Set<number>>(new Set())

  const { data: statusData } = useQuery({
    queryKey: ['ingest-status'],
    queryFn: () => apiService.getIngestStatus(),
    refetchInterval: 2000,
  })

  const toggleFileExpansion = (fileId: number) => {
    const newExpanded = new Set(expandedFiles)
    if (newExpanded.has(fileId)) {
      newExpanded.delete(fileId)
    } else {
      newExpanded.add(fileId)
    }
    setExpandedFiles(newExpanded)
  }

  const getFileStatus = (fileId: number) => {
    if (!statusData || !('files' in statusData)) return null
    return statusData.files.find(s => s.file_id === fileId)
  }

  const getStatusIcon = (state: string) => {
    switch (state) {
      case 'done':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'scanning':
      case 'parsing':
      case 'indexing':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />
    }
  }

  const getStatusColor = (state: string) => {
    switch (state) {
      case 'done':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'error':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      case 'scanning':
      case 'parsing':
      case 'indexing':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  return (
    <ScrollArea className="h-[calc(100vh-200px)]">
      <div className="space-y-2">
        {files.length === 0 ? (
          <Card>
            <CardContent className="p-6 text-center">
              <File className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
              <p className="text-muted-foreground">No files uploaded yet</p>
            </CardContent>
          </Card>
        ) : (
          files.map((file) => {
            const status = getFileStatus(file.file_id)
            const isExpanded = expandedFiles.has(file.file_id)
            const isSelected = selectedFileId === file.file_id

            return (
              <Card key={file.file_id} className={isSelected ? 'ring-2 ring-primary' : ''}>
                <Collapsible>
                  <CollapsibleTrigger asChild>
                    <CardHeader 
                      className="cursor-pointer hover:bg-muted/50 transition-colors"
                      onClick={() => toggleFileExpansion(file.file_id)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 min-w-0">
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4 flex-shrink-0" />
                          ) : (
                            <ChevronRight className="h-4 w-4 flex-shrink-0" />
                          )}
                          <File className="h-4 w-4 flex-shrink-0" />
                          <div className="min-w-0">
                            <CardTitle className="text-sm truncate">{file.name}</CardTitle>
                            <div className="flex items-center gap-2 mt-1">
                              <span className="text-xs text-muted-foreground">
                                {formatBytes(file.size)}
                              </span>
                              {file.file_type === 'fvTenant' && (
                                <Badge variant="secondary" className="text-xs">
                                  Tenant
                                </Badge>
                              )}
                              <Badge variant="outline" className={`text-xs ${getStatusColor(file.ingest_state)}`}>
                                {file.ingest_state}
                              </Badge>
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          {getStatusIcon(file.ingest_state)}
                        </div>
                      </div>
                    </CardHeader>
                  </CollapsibleTrigger>
                  
                  <CollapsibleContent>
                    <CardContent className="pt-0">
                      <div className="space-y-3">
                        {/* File Info */}
                        <div className="text-xs text-muted-foreground space-y-1">
                          <div>Imported: {formatDate(file.imported_at)}</div>
                          {status && (
                            <>
                              <div>Progress: {Math.round(status.progress_percent)}%</div>
                              {status.progress_percent > 0 && status.progress_percent < 100 && (
                                <Progress value={status.progress_percent} className="h-1" />
                              )}
                              <div>Objects: {status.total_objects.toLocaleString()}</div>
                              {status.error_count > 0 && (
                                <div className="text-red-500">
                                  Errors: {status.error_count}
                                </div>
                              )}
                            </>
                          )}
                        </div>

                        {/* Actions */}
                        <div className="flex gap-2">
                          <Button
                            variant={isSelected ? "default" : "outline"}
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation()
                              onFileSelect(isSelected ? null : file.file_id)
                              onClassSelect(null)
                            }}
                          >
                            {isSelected ? 'Selected' : 'Select File'}
                          </Button>
                        </div>

                        {/* Classes */}
                        {file.classes.length > 0 && (
                          <div className="space-y-2">
                            <div className="flex items-center gap-2">
                              <Database className="h-4 w-4" />
                              <span className="text-sm font-medium">Classes</span>
                            </div>
                            <div className="space-y-1 ml-6">
                              {file.classes.map((cls) => (
                                <div
                                  key={cls.class_id}
                                  className="flex items-center justify-between p-2 rounded hover:bg-muted/50 cursor-pointer"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    onFileSelect(file.file_id)
                                    onClassSelect(cls.class_name)
                                  }}
                                >
                                  <span className="text-sm font-mono">{cls.class_name}</span>
                                  <Badge variant="secondary" className="text-xs">
                                    {cls.object_count.toLocaleString()}
                                  </Badge>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </CollapsibleContent>
                </Collapsible>
              </Card>
            )
          })
        )}
      </div>
    </ScrollArea>
  )
}
