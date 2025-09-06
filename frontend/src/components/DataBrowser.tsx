import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Badge } from './ui/badge'
import { ScrollArea } from './ui/scroll-area'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from './ui/table'
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select'
import { 
  Search, 
  Download, 
  ChevronLeft, 
  ChevronRight, 
  Database,
  FileText,
  Link as LinkIcon
} from 'lucide-react'
import { apiService, ObjectInfo, AttributeInfo, RelationInfo } from '../lib/api'
import { formatNumber, downloadBlob } from '../lib/utils'
import { toast } from 'sonner'

interface DataBrowserProps {
  fileId: number | null
  className: string | null
}

export default function DataBrowser({ fileId, className }: DataBrowserProps) {
  const [searchFilter, setSearchFilter] = useState('')
  const [sortBy, setSortBy] = useState('object_id')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [currentPage, setCurrentPage] = useState(0)
  const [pageSize, setPageSize] = useState(100)
  const [selectedObjectId, setSelectedObjectId] = useState<number | null>(null)

  const { data: objectsData, isLoading: objectsLoading } = useQuery({
    queryKey: ['objects', fileId, className, searchFilter, sortBy, sortDir, currentPage, pageSize],
    queryFn: () => apiService.getObjects({
      file_id: fileId || undefined,
      class_name: className || undefined,
      filter: searchFilter || undefined,
      order_by: sortBy,
      dir: sortDir,
      limit: pageSize,
      offset: currentPage * pageSize,
    }),
    enabled: !!(fileId || className),
  })

  const { data: objectDetail } = useQuery({
    queryKey: ['object-detail', selectedObjectId],
    queryFn: () => apiService.getObjectDetail(selectedObjectId!),
    enabled: !!selectedObjectId,
  })

  const totalPages = useMemo(() => {
    if (!objectsData?.total_count) return 0
    return Math.ceil(objectsData.total_count / pageSize)
  }, [objectsData?.total_count, pageSize])

  const handleExport = async (format: 'csv' | 'json') => {
    try {
      const blob = await apiService.exportData({
        file_id: fileId || undefined,
        class_name: className || undefined,
        filter: searchFilter || undefined,
        format,
      })
      
      const filename = `export_${className || 'data'}_${new Date().toISOString().split('T')[0]}.${format}`
      downloadBlob(blob, filename)
      toast.success(`Exported ${format.toUpperCase()} successfully`)
    } catch (error) {
      toast.error(`Export failed: ${error}`)
    }
  }

  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage)
    setSelectedObjectId(null)
  }

  if (!fileId && !className) {
    return (
      <Card className="h-full">
        <CardContent className="flex items-center justify-center h-full">
          <div className="text-center">
            <Database className="h-16 w-16 mx-auto mb-4 text-muted-foreground" />
            <h3 className="text-lg font-semibold mb-2">No Data Selected</h3>
            <p className="text-muted-foreground">
              Select a file or class from the sidebar to browse data
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="h-full flex flex-col space-y-4">
      {/* Controls */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Data Browser
              {className && <Badge variant="outline">{className}</Badge>}
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleExport('csv')}
                disabled={!objectsData?.objects?.length}
              >
                <Download className="h-4 w-4 mr-2" />
                CSV
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleExport('json')}
                disabled={!objectsData?.objects?.length}
              >
                <Download className="h-4 w-4 mr-2" />
                JSON
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search objects..."
                  value={searchFilter}
                  onChange={(e) => {
                    setSearchFilter(e.target.value)
                    setCurrentPage(0)
                  }}
                  className="pl-10"
                />
              </div>
            </div>
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="object_id">Object ID</SelectItem>
                <SelectItem value="dn">DN</SelectItem>
                <SelectItem value="line_no">Line Number</SelectItem>
              </SelectContent>
            </Select>
            <Select value={sortDir} onValueChange={(value: 'asc' | 'desc') => setSortDir(value)}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="asc">Ascending</SelectItem>
                <SelectItem value="desc">Descending</SelectItem>
              </SelectContent>
            </Select>
            <Select value={pageSize.toString()} onValueChange={(value) => setPageSize(Number(value))}>
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="50">50</SelectItem>
                <SelectItem value="100">100</SelectItem>
                <SelectItem value="200">200</SelectItem>
                <SelectItem value="500">500</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Objects Table */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Objects</CardTitle>
              {objectsData && (
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span>
                    {formatNumber(objectsData.total_count)} total objects
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handlePageChange(currentPage - 1)}
                      disabled={currentPage === 0}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span>
                      Page {currentPage + 1} of {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handlePageChange(currentPage + 1)}
                      disabled={currentPage >= totalPages - 1}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[400px]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>DN</TableHead>
                    <TableHead>Line</TableHead>
                    <TableHead>Preview</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {objectsLoading ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center py-8">
                        Loading...
                      </TableCell>
                    </TableRow>
                  ) : objectsData?.objects?.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center py-8">
                        No objects found
                      </TableCell>
                    </TableRow>
                  ) : (
                    objectsData?.objects?.map((obj: ObjectInfo) => (
                      <TableRow
                        key={obj.object_id}
                        className={`cursor-pointer hover:bg-muted/50 ${
                          selectedObjectId === obj.object_id ? 'bg-muted' : ''
                        }`}
                        onClick={() => setSelectedObjectId(obj.object_id)}
                      >
                        <TableCell className="font-mono text-sm">
                          {obj.object_id}
                        </TableCell>
                        <TableCell className="font-mono text-sm max-w-48 truncate">
                          {obj.dn || '-'}
                        </TableCell>
                        <TableCell className="text-sm">
                          {obj.line_no}
                        </TableCell>
                        <TableCell className="text-sm max-w-64 truncate">
                          {obj.raw_xml}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Object Detail */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Object Detail
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!selectedObjectId ? (
              <div className="text-center py-8 text-muted-foreground">
                Select an object to view details
              </div>
            ) : (
              <Tabs defaultValue="attributes" className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="attributes">Attributes</TabsTrigger>
                  <TabsTrigger value="relations">Relations</TabsTrigger>
                  <TabsTrigger value="raw">Raw</TabsTrigger>
                </TabsList>
                
                <TabsContent value="attributes" className="mt-4">
                  <ScrollArea className="h-[300px]">
                    {objectDetail?.attributes?.length === 0 ? (
                      <div className="text-center py-4 text-muted-foreground">
                        No attributes found
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {objectDetail?.attributes?.map((attr: AttributeInfo) => (
                          <div key={attr.attr_id} className="border rounded p-2">
                            <div className="font-mono text-sm font-medium">
                              {attr.key}
                            </div>
                            <div className="text-sm text-muted-foreground break-all">
                              {attr.value}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </ScrollArea>
                </TabsContent>
                
                <TabsContent value="relations" className="mt-4">
                  <ScrollArea className="h-[300px]">
                    {objectDetail?.relations?.length === 0 ? (
                      <div className="text-center py-4 text-muted-foreground">
                        No relations found
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {objectDetail?.relations?.map((rel: RelationInfo) => (
                          <div key={rel.rel_id} className="border rounded p-2">
                            <div className="flex items-center gap-2 mb-1">
                              <LinkIcon className="h-4 w-4" />
                              <Badge variant="outline" className="text-xs">
                                {rel.rel_type}
                              </Badge>
                            </div>
                            <div className="font-mono text-sm">
                              {rel.target_dn}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </ScrollArea>
                </TabsContent>
                
                <TabsContent value="raw" className="mt-4">
                  <ScrollArea className="h-[300px]">
                    <pre className="text-xs bg-muted p-3 rounded whitespace-pre-wrap">
                      {objectDetail?.object?.raw_xml || 'No raw data available'}
                    </pre>
                  </ScrollArea>
                </TabsContent>
              </Tabs>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
