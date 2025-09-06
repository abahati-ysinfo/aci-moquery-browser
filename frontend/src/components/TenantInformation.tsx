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
  Network,
  Shield,
  Globe
} from 'lucide-react'
import { apiService, TenantObject } from '../lib/api'
import { formatDate, downloadBlob } from '../lib/utils'
import { toast } from 'sonner'

interface TenantInformationProps {
  fileId: number
}

const OBJECT_TYPE_CONFIGS = {
  'fvTenant': { label: 'Overview', icon: Database, description: 'Tenant overview and basic information' },
  'fvAp': { label: 'Application Profiles', icon: Database, description: 'Application profiles and policies' },
  'fvAEPg': { label: 'Endpoint Groups', icon: Network, description: 'Application endpoint groups' },
  'fvBD': { label: 'Bridge Domains', icon: Network, description: 'Layer 2 bridge domains' },
  'fvCtx': { label: 'VRFs', icon: Globe, description: 'Virtual routing and forwarding contexts' },
  'vzBrCP': { label: 'Contracts', icon: Shield, description: 'Security contracts and policies' },
  'vzSubj': { label: 'Contract Subjects', icon: Shield, description: 'Contract subjects and rules' },
  'vzFilter': { label: 'Filters', icon: Shield, description: 'Traffic filters and entries' },
  'l3extOut': { label: 'L3Out', icon: Globe, description: 'Layer 3 external connectivity' },
  'ospfExtP': { label: 'OSPF', icon: Network, description: 'OSPF external profiles' },
  'fvCEp': { label: 'Client Endpoints', icon: Network, description: 'Client endpoints with MAC/IP' },
  'fvSubnet': { label: 'Subnets', icon: Network, description: 'Subnet configurations' }
}

export default function TenantInformation({ fileId }: TenantInformationProps) {
  const [activeTab, setActiveTab] = useState('fvTenant')
  const [searchFilter, setSearchFilter] = useState('')
  const [advancedSearch, setAdvancedSearch] = useState({ type: 'name', value: '' })
  const [currentPage, setCurrentPage] = useState(0)
  const [pageSize] = useState(100)
  const [visibleColumns] = useState<Set<string>>(new Set(['object_name', 'object_dn', 'description', 'status']))

  const { data: tenantInfo } = useQuery({
    queryKey: ['tenant-info', fileId],
    queryFn: () => apiService.getTenantInfo(fileId),
    enabled: !!fileId,
  })

  const { data: tenantObjects, isLoading } = useQuery({
    queryKey: ['tenant-objects', fileId, activeTab, searchFilter, currentPage, pageSize],
    queryFn: () => apiService.getTenantObjects({
      file_id: fileId,
      object_type: activeTab,
      search: searchFilter || undefined,
      limit: pageSize,
      offset: currentPage * pageSize,
    }),
    enabled: !!fileId,
  })

  const { data: _searchResults } = useQuery({
    queryKey: ['tenant-search', fileId, advancedSearch.type, advancedSearch.value],
    queryFn: () => apiService.searchTenantData(fileId, advancedSearch.type, advancedSearch.value),
    enabled: !!fileId && !!advancedSearch.value && ['mac', 'ip'].includes(advancedSearch.type),
  })

  const totalPages = useMemo(() => {
    if (!tenantObjects?.total_count) return 0
    return Math.ceil(tenantObjects.total_count / pageSize)
  }, [tenantObjects?.total_count, pageSize])

  const handleExport = async () => {
    try {
      const blob = await apiService.exportTenantData(fileId, activeTab)
      const filename = `tenant_${activeTab}_${new Date().toISOString().split('T')[0]}.csv`
      downloadBlob(blob, filename)
      toast.success('Exported CSV successfully')
    } catch (error) {
      toast.error(`Export failed: ${error}`)
    }
  }

  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage)
  }


  const getColumnHeaders = (objectType: string) => {
    const baseHeaders = {
      'object_name': 'Name',
      'object_dn': 'Distinguished Name',
      'description': 'Description',
      'status': 'Status',
      'last_modified': 'Last Modified'
    }
    
    const typeSpecificHeaders: Record<string, Record<string, string>> = {
      'fvBD': { 'arpFlood': 'ARP Flooding', 'unicastRoute': 'Unicast Routing', 'mtu': 'MTU' },
      'fvCtx': { 'seg': 'Segment ID', 'pcEnfPref': 'Policy Enforcement' },
      'vzBrCP': { 'scope': 'Contract Scope', 'prio': 'Priority' },
      'l3extOut': { 'enforceRtctrl': 'Route Control', 'targetDscp': 'DSCP Marking' },
      'fvCEp': { 'mac': 'MAC Address', 'ip': 'IP Address', 'encap': 'Encapsulation' }
    }
    
    return { ...baseHeaders, ...(typeSpecificHeaders[objectType] || {}) }
  }

  if (!fileId) {
    return (
      <Card className="h-full">
        <CardContent className="flex items-center justify-center h-full">
          <div className="text-center">
            <Database className="h-16 w-16 mx-auto mb-4 text-muted-foreground" />
            <h3 className="text-lg font-semibold mb-2">No Tenant File Selected</h3>
            <p className="text-muted-foreground">
              Upload an fvTenant file to view tenant information
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="h-full flex flex-col space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Tenant Information
              {tenantInfo?.tenants?.length && (
                <Badge variant="outline">{tenantInfo.tenants.length} tenants</Badge>
              )}
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleExport}
                disabled={!tenantObjects?.objects?.length}
              >
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 mb-4">
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
            <Select value={advancedSearch.type} onValueChange={(value) => setAdvancedSearch({ ...advancedSearch, type: value })}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="name">Name</SelectItem>
                <SelectItem value="mac">MAC</SelectItem>
                <SelectItem value="ip">IP</SelectItem>
                <SelectItem value="dn">DN</SelectItem>
              </SelectContent>
            </Select>
            <Input
              placeholder="Advanced search..."
              value={advancedSearch.value}
              onChange={(e) => setAdvancedSearch({ ...advancedSearch, value: e.target.value })}
              className="w-48"
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex-1">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full">
          <TabsList className="grid grid-cols-6 lg:grid-cols-12 w-full">
            {Object.entries(OBJECT_TYPE_CONFIGS).map(([type, config]) => (
              <TabsTrigger key={type} value={type} className="text-xs">
                <config.icon className="h-3 w-3 mr-1" />
                {config.label}
              </TabsTrigger>
            ))}
          </TabsList>
          
          {Object.entries(OBJECT_TYPE_CONFIGS).map(([type, config]) => (
            <TabsContent key={type} value={type} className="h-full">
              <Card className="h-full">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <config.icon className="h-5 w-5" />
                      {config.label}
                    </CardTitle>
                    {tenantObjects && (
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span>{tenantObjects.total_count} objects</span>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handlePageChange(currentPage - 1)}
                            disabled={currentPage === 0}
                          >
                            <ChevronLeft className="h-4 w-4" />
                          </Button>
                          <span>Page {currentPage + 1} of {totalPages}</span>
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
                  <ScrollArea className="h-[500px]">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          {Object.entries(getColumnHeaders(type)).map(([key, label]) => 
                            visibleColumns.has(key) && (
                              <TableHead key={key}>{label}</TableHead>
                            )
                          )}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {isLoading ? (
                          <TableRow>
                            <TableCell colSpan={visibleColumns.size} className="text-center py-8">
                              Loading...
                            </TableCell>
                          </TableRow>
                        ) : tenantObjects?.objects?.length === 0 ? (
                          <TableRow>
                            <TableCell colSpan={visibleColumns.size} className="text-center py-8">
                              No logs file found for this tab
                            </TableCell>
                          </TableRow>
                        ) : (
                          tenantObjects?.objects?.map((obj: TenantObject) => (
                            <TableRow key={obj.object_id}>
                              {visibleColumns.has('object_name') && (
                                <TableCell className="font-medium">{obj.object_name}</TableCell>
                              )}
                              {visibleColumns.has('object_dn') && (
                                <TableCell className="font-mono text-sm max-w-64 truncate">{obj.object_dn}</TableCell>
                              )}
                              {visibleColumns.has('description') && (
                                <TableCell className="max-w-48 truncate">{obj.description || '-'}</TableCell>
                              )}
                              {visibleColumns.has('status') && (
                                <TableCell>
                                  {obj.status && <Badge variant="outline">{obj.status}</Badge>}
                                </TableCell>
                              )}
                              {visibleColumns.has('last_modified') && (
                                <TableCell className="text-sm">
                                  {obj.last_modified ? formatDate(obj.last_modified) : '-'}
                                </TableCell>
                              )}
                            </TableRow>
                          ))
                        )}
                      </TableBody>
                    </Table>
                  </ScrollArea>
                </CardContent>
              </Card>
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </div>
  )
}
