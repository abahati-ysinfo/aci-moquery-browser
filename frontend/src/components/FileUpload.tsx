import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from './ui/button'
import { Progress } from './ui/progress'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { Upload, File, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { apiService } from '../lib/api'

interface UploadingFile {
  file: File
  progress: number
  status: 'uploading' | 'processing' | 'complete' | 'error'
  fileId?: number
  error?: string
}

export default function FileUpload() {
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([])
  const queryClient = useQueryClient()

  const uploadMutation = useMutation({
    mutationFn: async ({ file, index }: { file: File; index: number }) => {
      try {
        setUploadingFiles(prev => 
          prev.map((f, i) => i === index ? { ...f, status: 'uploading' as const } : f)
        )

        const result = await apiService.uploadFile(file, (progress) => {
          setUploadingFiles(prev => 
            prev.map((f, i) => i === index ? { ...f, progress } : f)
          )
        })

        if (result.status === 'duplicate') {
          setUploadingFiles(prev => 
            prev.map((f, i) => i === index ? { 
              ...f, 
              status: 'complete' as const, 
              progress: 100,
              fileId: result.file_id 
            } : f)
          )
          toast.info(`File "${file.name}" already exists`)
          return result
        }

        setUploadingFiles(prev => 
          prev.map((f, i) => i === index ? { 
            ...f, 
            status: 'processing' as const, 
            progress: 100,
            fileId: result.file_id 
          } : f)
        )

        await apiService.completeUpload(result.file_id)

        setUploadingFiles(prev => 
          prev.map((f, i) => i === index ? { ...f, status: 'complete' as const } : f)
        )

        toast.success(`File "${file.name}" uploaded successfully`)
        queryClient.invalidateQueries({ queryKey: ['files'] })
        
        return result
      } catch (error) {
        setUploadingFiles(prev => 
          prev.map((f, i) => i === index ? { 
            ...f, 
            status: 'error' as const, 
            error: error instanceof Error ? error.message : 'Upload failed' 
          } : f)
        )
        toast.error(`Failed to upload "${file.name}"`)
        throw error
      }
    },
  })

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const validFiles = acceptedFiles.filter(file => {
      const validExtensions = ['.txt', '.log', '.7z', '.zip', '.tar.gz', '.tgz']
      const isValid = validExtensions.some(ext => file.name.toLowerCase().endsWith(ext))
      
      if (!isValid) {
        toast.error(`File "${file.name}" has unsupported format`)
        return false
      }
      
      if (file.size > 200 * 1024 * 1024) { // 200MB limit
        toast.error(`File "${file.name}" is too large (max 200MB)`)
        return false
      }
      
      return true
    })

    const newUploads: UploadingFile[] = validFiles.map(file => ({
      file,
      progress: 0,
      status: 'uploading',
    }))

    setUploadingFiles(prev => [...prev, ...newUploads])

    validFiles.forEach((file, index) => {
      const actualIndex = uploadingFiles.length + index
      uploadMutation.mutate({ file, index: actualIndex })
    })
  }, [uploadingFiles.length, uploadMutation])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/plain': ['.txt', '.log'],
      'application/x-7z-compressed': ['.7z'],
      'application/zip': ['.zip'],
      'application/gzip': ['.tar.gz', '.tgz'],
    },
    multiple: true,
  })

  const clearCompleted = () => {
    setUploadingFiles(prev => prev.filter(f => f.status !== 'complete'))
  }

  const retryFailed = (index: number) => {
    const file = uploadingFiles[index]
    if (file && file.status === 'error') {
      uploadMutation.mutate({ file: file.file, index })
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Upload Files
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              isDragActive
                ? 'border-primary bg-primary/5'
                : 'border-muted-foreground/25 hover:border-primary/50'
            }`}
          >
            <input {...getInputProps()} />
            <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
            {isDragActive ? (
              <p className="text-lg">Drop files here...</p>
            ) : (
              <div>
                <p className="text-lg mb-2">Drag & drop files here, or click to select</p>
                <p className="text-sm text-muted-foreground">
                  Supports: .txt, .log, .7z, .zip, .tar.gz (max 200MB each)
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {uploadingFiles.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Upload Progress</CardTitle>
              <Button variant="outline" size="sm" onClick={clearCompleted}>
                Clear Completed
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {uploadingFiles.map((upload, index) => (
                <div key={index} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <File className="h-4 w-4" />
                      <span className="text-sm font-medium truncate max-w-48">
                        {upload.file.name}
                      </span>
                      {upload.status === 'uploading' && (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      )}
                      {upload.status === 'processing' && (
                        <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                      )}
                      {upload.status === 'complete' && (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                      )}
                      {upload.status === 'error' && (
                        <XCircle className="h-4 w-4 text-red-500" />
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        {upload.status === 'uploading' && `${Math.round(upload.progress)}%`}
                        {upload.status === 'processing' && 'Processing...'}
                        {upload.status === 'complete' && 'Complete'}
                        {upload.status === 'error' && 'Failed'}
                      </span>
                      {upload.status === 'error' && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => retryFailed(index)}
                        >
                          Retry
                        </Button>
                      )}
                    </div>
                  </div>
                  {upload.status === 'uploading' && (
                    <Progress value={upload.progress} className="h-2" />
                  )}
                  {upload.error && (
                    <p className="text-xs text-red-500">{upload.error}</p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
