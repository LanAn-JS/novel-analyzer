import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// ======== API提供商 ========
export const getProviders = () => api.get('/providers/')
export const createProvider = (data) => api.post('/providers/', data)
export const updateProvider = (id, data) => api.put(`/providers/${id}`, data)
export const deleteProvider = (id) => api.delete(`/providers/${id}`)
export const activateProvider = (id) => api.post(`/providers/${id}/activate`)
export const testProvider = (data) => api.post('/providers/test', data)

// ======== 小说 ========
export const uploadNovel = (formData, signal) => api.post('/novels/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000, signal })
export const getNovels = (params) => api.get('/novels/', { params })
export const getNovel = (id) => api.get(`/novels/${id}`)
export const deleteNovel = (id) => api.delete(`/novels/${id}`)
export const analyzeNovel = (id) => api.post(`/novels/${id}/analyze`)
export const pauseAnalysis = (id) => api.post(`/novels/${id}/analyze/pause`)
export const resumeAnalysis = (id) => api.post(`/novels/${id}/analyze/resume`)
export const getAnalysis = (id) => api.get(`/novels/${id}/analysis`)
export const exportAnalysis = (id, format) => api.get(`/novels/${id}/export`, { params: { format } })
export const openDirectory = (path) => api.post('/novels/open-directory', null, { params: { path } })
export const getCategories = () => api.get('/novels/categories/list')
export const getTags = () => api.get('/novels/tags/list')
// 注意：SSE流不通过axios，直接用 EventSource(`/api/novels/${id}/analyze/stream`)

// ======== 搜索与查询 ========
export const semanticSearch = (data) => api.post('/search', data)
export const agentQuery = (data) => api.post('/query', data)
export const getStats = () => api.get('/stats')

// ======== 系统 ========
export const healthCheck = () => api.get('/health')

export default api
