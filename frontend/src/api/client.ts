import axios from 'axios'
import { getToken } from './token'

const client = axios.create({
    baseURL: '/api',
    timeout: 1000,
    headers: {}
})

client.interceptors.request.use((config) => {
    const token = getToken()
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

export default client