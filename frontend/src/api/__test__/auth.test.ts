import { makeAxiosError } from './testUtils'
import { login } from '../auth'
import client from '../client'
import { setToken } from '../token'
import { AuthenticationError } from '../errors'
import { vi } from 'vitest'

vi.mock('../client')
vi.mock('../token')

describe('login', () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    it('should call POST /token with form data and correct headers', async () => {
        const formData = new URLSearchParams({
            username: 'testuser',
            password: 'testpassword'
        })

        vi.mocked(client.post).mockResolvedValue({
            data: { access_token: 'fake-token', token_type: 'bearer' }
        })

        await login(formData)
        
        expect(client.post).toHaveBeenCalledWith('/token', formData, {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        })
    })

    it('should set token in localStorage when access_token is present', async () => {
        const formData = new URLSearchParams({
            username: 'testuser',
            password: 'testpassword'
        })

        vi.mocked(client.post).mockResolvedValue({
            data: { access_token: 'fake-token-123', token_type: 'bearer' }
        })

        await login(formData)
        
        expect(setToken).toHaveBeenCalledWith('fake-token-123')
    })

    it('should throw AuthenticationError when response has no access_token', async () => {
        const formData = new URLSearchParams({
            username: 'testuser',
            password: 'wrongpassword'
        })

        vi.mocked(client.post).mockResolvedValue({
            data: { token_type: 'bearer' }
        })

        await expect(login(formData)).rejects.toThrow(AuthenticationError)
        await expect(login(formData)).rejects.toThrow('No token in response.')
    })

    it('should propagate Axios errors on network or server failure', async () => {
        const formData = new URLSearchParams({
            username: 'testuser',
            password: 'testpassword'
        })

        vi.mocked(client.post).mockRejectedValue(
            makeAxiosError(401, { detail: 'Invalid credentials' })
        )

        await expect(login(formData)).rejects.toThrow()
    })
})
