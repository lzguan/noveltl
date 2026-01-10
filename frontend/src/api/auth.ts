import client from './client'
import { setToken } from './token'
import { AuthenticationError } from './errors';

export const login = async (formData : URLSearchParams) => {
    const response = await client.post('/token', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    if (response.data.access_token) {
        setToken(response.data.access_token)
    }
    else {
        throw new AuthenticationError("No token in response.")
    }
}