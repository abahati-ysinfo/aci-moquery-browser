import axios from 'axios'

const API_BASE_URL = (import.meta as any).env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
})

export interface FileInfo {
  file_id: number
  name: string
  size: number
  imported_at: string
  ingest_state: string
  file_type?: string
  classes: ClassInfo[]
}

export interface ClassInfo {
  class_id: number
  class_name: string
  object_count: number
  file_id?: number
}

export interface ObjectInfo {
  object_id: number
  class_id: number
  dn: string | null
  line_no: number
  start_byte: number
  end_byte: number
  raw_xml: string
}

export interface AttributeInfo {
  attr_id: number
  key: string
  value: string
}

export interface RelationInfo {
  rel_id: number
  object_id: number
  rel_type: string
  target_dn: string
  raw_value: string
}

export interface IngestStatus {
  file_id: number
  name: string
  size: number
  state: string
  last_offset: number
  progress_percent: number
  classes_found: number
  total_objects: number
  error_count: number
  is_active: boolean
}

export interface ConfigInfo {
  max_concurrent_ingests: number
  batch_size: number
  upload_chunk_size: number
}

export interface TenantInfo {
  tenant_id: number
  tenant_name: string
  tenant_dn: string
  description?: string
  status?: string
  last_modified?: string
  uid?: string
}

export interface TenantObject {
  object_id: number
  tenant_id: number
  object_type: string
  object_name: string
  object_dn: string
  parent_dn?: string
  description?: string
  status?: string
  last_modified?: string
}

export interface TenantSearchResult {
  search_entry: {
    search_type: string
    search_value: string
    object_reference: string
  }
  object: TenantObject
}

export const apiService = {
  uploadFile: async (file: File, onProgress?: (progress: number) => void) => {
    const chunkSize = 8 * 1024 * 1024 // 8MB chunks
    const totalChunks = Math.ceil(file.size / chunkSize)
    let uploadedChunks = 0

    for (let i = 0; i < totalChunks; i++) {
      const start = i * chunkSize
      const end = Math.min(start + chunkSize, file.size)
      const chunk = file.slice(start, end)

      const formData = new FormData()
      formData.append('file', chunk, file.name)

      const response = await api.post('/api/upload', formData, {
        params: {
          chunk_number: i,
          total_chunks: totalChunks,
        },
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      uploadedChunks++
      if (onProgress) {
        onProgress((uploadedChunks / totalChunks) * 100)
      }

      if (i === totalChunks - 1) {
        return response.data
      }
    }
  },

  completeUpload: async (fileId: number) => {
    const response = await api.post('/api/upload/complete', null, {
      params: { file_id: fileId },
    })
    return response.data
  },

  getIngestStatus: async (fileId?: number): Promise<IngestStatus | { files: IngestStatus[] }> => {
    const response = await api.get('/api/ingest/status', {
      params: fileId ? { file_id: fileId } : {},
    })
    return response.data
  },

  cancelIngest: async (fileId: number) => {
    const response = await api.post('/api/ingest/cancel', null, {
      params: { file_id: fileId },
    })
    return response.data
  },

  getFiles: async (): Promise<{ files: FileInfo[] }> => {
    const response = await api.get('/api/files')
    return response.data
  },

  getClasses: async (fileId?: number): Promise<{ classes: ClassInfo[] }> => {
    const response = await api.get('/api/classes', {
      params: fileId ? { file_id: fileId } : {},
    })
    return response.data
  },

  getObjects: async (params: {
    class_name?: string
    file_id?: number
    filter?: string
    order_by?: string
    dir?: string
    limit?: number
    offset?: number
  }) => {
    const response = await api.get('/api/objects', { params })
    return response.data
  },

  getObjectDetail: async (objectId: number) => {
    const response = await api.get(`/api/objects/${objectId}`)
    return response.data
  },

  getAttributes: async (objectIds: number[]) => {
    const response = await api.get('/api/attributes', {
      params: { object_ids: objectIds.join(',') },
    })
    return response.data
  },

  getRelations: async (params: { class_name?: string; object_ids?: number[] }) => {
    const response = await api.get('/api/relations', {
      params: {
        class_name: params.class_name,
        object_ids: params.object_ids?.join(','),
      },
    })
    return response.data
  },

  exportData: async (params: {
    class_name?: string
    file_id?: number
    format?: string
    filter?: string
  }) => {
    const response = await api.get('/api/export', {
      params,
      responseType: 'blob',
    })
    return response.data
  },

  getConfig: async (): Promise<ConfigInfo> => {
    const response = await api.get('/api/config')
    return response.data
  },

  updateConfig: async (config: Record<string, any>): Promise<ConfigInfo> => {
    const response = await api.post('/api/config', config)
    return response.data
  },

  getTenantInfo: async (fileId: number): Promise<{ tenants: TenantInfo[] }> => {
    const response = await api.get(`/api/tenant-info?file_id=${fileId}`)
    return response.data
  },

  getTenantObjects: async (params: {
    file_id: number
    object_type?: string
    tenant_id?: number
    search?: string
    limit?: number
    offset?: number
  }): Promise<{ objects: TenantObject[], total_count: number, limit: number, offset: number }> => {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.append(key, value.toString())
      }
    })
    const response = await api.get(`/api/tenant-objects?${searchParams}`)
    return response.data
  },

  searchTenantData: async (fileId: number, searchType: string, searchValue: string): Promise<{ results: TenantSearchResult[] }> => {
    const response = await api.get(`/api/tenant-search?file_id=${fileId}&search_type=${searchType}&search_value=${searchValue}`)
    return response.data
  },

  exportTenantData: async (fileId: number, objectType: string): Promise<Blob> => {
    const response = await api.get(`/api/tenant-export?file_id=${fileId}&object_type=${objectType}&format=csv`, {
      responseType: 'blob'
    })
    return response.data
  }
}
